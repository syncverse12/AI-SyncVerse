"""
main.py
=======
Standalone Real-Time Speech-to-Text Service
============================================

Exposes two transport layers on a single FastAPI app:

  POST /transcribe/file
      Upload a complete audio file → receive full transcript JSON.

  WebSocket /transcribe/stream
      Stream raw PCM audio frames → receive incremental transcript events.

Run
---
    uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload

Authentication
--------------
No auth is wired here (auth was stripped per requirements).
Add your preferred middleware before deploying to production.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import os
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .transcriber import RealtimeTranscriber, transcribe_file

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Real-Time Speech-to-Text Service",
    description=(
        "Standalone transcription microservice extracted from the Sentry AI repository.\n\n"
        "Uses AssemblyAI for both file-based and real-time streaming transcription.\n\n"
        "**Audio requirements for streaming mode (WebSocket)**:\n"
        "- Encoding: PCM signed 16-bit little-endian (LINEAR16)\n"
        "- Sample rate: 16 000 Hz\n"
        "- Channels: Mono\n"
        "- Chunk size: 1 600 – 8 000 bytes (100 – 500 ms of audio)"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health():
    """Returns service status and API key presence."""
    key_set = bool(os.getenv("ASSEMBLYAI_API_KEY"))
    return {
        "status": "ok",
        "api_key_configured": key_set,
        "endpoints": {
            "file_transcription": "POST /transcribe/file",
            "streaming_transcription": "WS  /transcribe/stream",
        },
    }


# ---------------------------------------------------------------------------
# File-based transcription (REST)
# ---------------------------------------------------------------------------

@app.post("/transcribe/file", tags=["Transcription"])
async def transcribe_audio_file(
    file: UploadFile = File(..., description="Audio file (MP3, WAV, M4A, FLAC, OGG, WEBM …)"),
    language_detection: bool = Form(True, description="Auto-detect spoken language"),
    language_code: Optional[str] = Form(None, description="Force BCP-47 code, e.g. 'ar' or 'en'"),
    word_timestamps: bool = Form(False, description="Include per-word start/end timestamps"),
):
    """
    **File transcription endpoint.**

    Upload any supported audio file and receive the full transcript.

    | Field | Description |
    |---|---|
    | `text` | Full transcript string |
    | `language` | Detected/forced BCP-47 language code |
    | `confidence` | Average word confidence (0–1) |
    | `duration_seconds` | Audio duration |
    | `words` | Per-word timestamps *(only when `word_timestamps=true`)* |

    Supported formats: MP3, WAV, M4A, FLAC, OGG, WEBM, MP4 (audio) and more.
    """
    if not file.filename:
        return JSONResponse(status_code=400, content={"error": "No file provided."})

    suffix = os.path.splitext(file.filename)[-1] or ".audio"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: transcribe_file(
                tmp.name,
                language_detection=language_detection,
                language_code=language_code or None,
                word_timestamps=word_timestamps,
            ),
        )
        return JSONResponse(status_code=200, content=result)

    except FileNotFoundError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except RuntimeError as exc:
        logger.exception("Transcription error")
        return JSONResponse(status_code=502, content={"error": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error")
        return JSONResponse(status_code=500, content={"error": str(exc)})
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Real-time streaming transcription (WebSocket)
# ---------------------------------------------------------------------------

@app.websocket("/transcribe/stream")
async def transcribe_stream(websocket: WebSocket):
    """
    **Real-time streaming transcription via WebSocket.**

    ### Protocol

    **Client → Server**: binary frames containing raw PCM audio
    - Encoding: LINEAR16 (signed 16-bit little-endian)
    - Sample rate: 16 000 Hz
    - Channels: Mono
    - Recommended chunk size: 3 200 bytes = 100 ms at 16 kHz

    **Server → Client**: JSON text frames
    ```json
    {"type": "partial", "text": "hello wor"}
    {"type": "final",   "text": "Hello world."}
    {"type": "error",   "text": "<description>"}
    {"type": "closed",  "text": ""}
    ```

    - `partial` — incremental hypothesis, may change with more audio
    - `final`   — committed sentence segment, will not change
    - `error`   — AssemblyAI reported an error (session continues if possible)
    - `closed`  — session ended; client should close its side

    ### Closing
    Close the WebSocket from the client side when done sending audio.
    The server will forward any remaining buffered events and then close.

    ### JavaScript example
    ```javascript
    const ws = new WebSocket("ws://localhost:8010/transcribe/stream");
    ws.binaryType = "arraybuffer";

    ws.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.type === "final") console.log("FINAL:", event.text);
      else if (event.type === "partial") console.log("partial:", event.text);
    };

    // Feed from MediaRecorder / AudioWorklet at 16 kHz mono LINEAR16
    function sendChunk(pcmBuffer) { ws.send(pcmBuffer); }
    ```
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted from %s", websocket.client)

    import json

    async def send(event: dict) -> None:
        try:
            await websocket.send_text(json.dumps(event))
        except Exception:
            pass

    try:
        async with RealtimeTranscriber(sample_rate=16_000) as rt:
            # Consume transcript events in the background
            async def _forward_events():
                async for event in rt.events():
                    await send(event)
                    if event["type"] in ("closed", "error"):
                        break

            forward_task = asyncio.create_task(_forward_events())

            try:
                while True:
                    # Receive raw PCM chunk from the client
                    chunk = await websocket.receive_bytes()
                    await rt.send_audio(chunk)
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected.")
            finally:
                # Let the event forwarder drain
                await forward_task

    except EnvironmentError as exc:
        await send({"type": "error", "text": str(exc)})
        await websocket.close(code=1011)
    except Exception as exc:
        logger.exception("Streaming error")
        await send({"type": "error", "text": str(exc)})
        await websocket.close(code=1011)
