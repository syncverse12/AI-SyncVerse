"""
transcriber.py
==============
Core real-time speech-to-text engine.

Reuses the AssemblyAI integration from the original repository
(sentry_app/services/task_extraction/audio_processor.py) but strips
everything unrelated to transcription: no task extraction, no LLM calls,
no speaker diarization, no DB writes.

Two operating modes
-------------------
1. File mode  – upload a complete audio file, get back a full transcript
   with optional word-level timestamps.

2. Real-time streaming mode – connect a WebSocket; the engine opens an
   AssemblyAI real-time transcription session and forwards partial +
   final transcript events as they arrive.

Audio requirements (file mode)
-------------------------------
AssemblyAI accepts: MP3, WAV, M4A, FLAC, OGG, WEBM, MP4 (audio track),
and most other common formats directly – no client-side conversion needed.

Audio requirements (streaming / WebSocket mode)
-----------------------------------------------
• Encoding  : PCM signed 16-bit little-endian (LINEAR16)
• Sample rate: 16 000 Hz  (required by AssemblyAI real-time)
• Channels  : mono
• Chunk size : 1 600 – 8 000 bytes per send (100 – 500 ms worth of audio)

Environment variable required
------------------------------
ASSEMBLYAI_API_KEY  – obtain at https://www.assemblyai.com
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import AsyncGenerator, Optional

import assemblyai as aai  # assemblyai>=0.35.0  (same version as repo)
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Initialisation (mirrors audio_processor._initialize_assemblyai)
# ---------------------------------------------------------------------------

def _init() -> None:
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ASSEMBLYAI_API_KEY is not set. "
            "Export it or add it to your .env file."
        )
    aai.settings.api_key = api_key


# ---------------------------------------------------------------------------
# FILE / BATCH MODE
# ---------------------------------------------------------------------------

def transcribe_file(
    audio_path: str,
    *,
    language_detection: bool = True,
    language_code: Optional[str] = None,
    word_timestamps: bool = False,
) -> dict:
    """
    Transcribe a complete audio file and return the transcript.

    Parameters
    ----------
    audio_path : str
        Local path to the audio file.
    language_detection : bool
        Auto-detect the spoken language (100+ languages). Mutually
        exclusive with ``language_code``.
    language_code : str, optional
        Force a specific BCP-47 language code, e.g. ``"ar"`` or ``"en"``.
        When set, ``language_detection`` is ignored.
    word_timestamps : bool
        Include per-word start/end timestamps in the response.

    Returns
    -------
    dict  ::
        {
            "text": str,            # full transcript
            "language": str | None,
            "confidence": float,
            "duration_seconds": float,
            "words": list[dict]     # only when word_timestamps=True
        }
    """
    _init()

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    config = aai.TranscriptionConfig(
        speech_model=aai.SpeechModel.best,
        language_detection=language_detection if not language_code else False,
        language_code=language_code,
        punctuate=True,
        format_text=True,
        # word-level timestamps (set_audio_end_at not needed here)
    )

    logger.info("Uploading %s to AssemblyAI …", audio_path)
    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(audio_path)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI transcription error: {transcript.error}")

    result: dict = {
        "text": transcript.text,
        "language": getattr(transcript, "language_code", None),
        "confidence": transcript.confidence,
        "duration_seconds": transcript.audio_duration,
    }

    if word_timestamps and hasattr(transcript, "words") and transcript.words:
        result["words"] = [
            {
                "text": w.text,
                "start_ms": w.start,
                "end_ms": w.end,
                "confidence": w.confidence,
            }
            for w in transcript.words
        ]

    logger.info(
        "Transcription complete – %d chars, lang=%s, confidence=%.2f",
        len(transcript.text or ""),
        result["language"],
        result["confidence"],
    )
    return result


# ---------------------------------------------------------------------------
# REAL-TIME STREAMING MODE
# ---------------------------------------------------------------------------

class RealtimeTranscriber:
    """
    Wraps AssemblyAI's real-time transcription SDK.

    Usage
    -----
    async with RealtimeTranscriber(sample_rate=16_000) as rt:
        async for event in rt.events():
            print(event)           # {"type": "partial"|"final", "text": str}
        # Feed raw PCM chunks via:
        await rt.send_audio(chunk: bytes)

    The caller is responsible for sending LINEAR16 / 16 kHz / mono PCM.
    """

    def __init__(self, sample_rate: int = 16_000):
        _init()
        self._sample_rate = sample_rate
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._rt: Optional[aai.RealtimeTranscriber] = None

    # -- callbacks forwarded into the async queue ---------------------------

    def _on_open(self, session_opened: aai.RealtimeSessionOpened) -> None:
        logger.info("AssemblyAI real-time session opened: %s", session_opened.session_id)

    def _on_data(self, transcript: aai.RealtimeTranscript) -> None:
        if not transcript.text:
            return
        is_final = isinstance(transcript, aai.RealtimeFinalTranscript)
        event = {
            "type": "final" if is_final else "partial",
            "text": transcript.text,
        }
        # Put on the queue (thread-safe bridge: SDK uses a background thread)
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except Exception as exc:
            logger.warning("Event queue error: %s", exc)

    def _on_error(self, error: aai.RealtimeError) -> None:
        logger.error("AssemblyAI real-time error: %s", error)
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                self._queue.put_nowait,
                {"type": "error", "text": str(error)},
            )
        except Exception:
            pass

    def _on_close(self) -> None:
        logger.info("AssemblyAI real-time session closed.")
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, {"type": "closed", "text": ""})
        except Exception:
            pass

    # -- context manager / lifecycle ----------------------------------------

    async def __aenter__(self) -> "RealtimeTranscriber":
        self._rt = aai.RealtimeTranscriber(
            sample_rate=self._sample_rate,
            on_open=self._on_open,
            on_data=self._on_data,
            on_error=self._on_error,
            on_close=self._on_close,
            encoding=aai.AudioEncoding.pcm_s16le,
        )
        await asyncio.get_event_loop().run_in_executor(None, self._rt.connect)
        return self

    async def __aexit__(self, *_) -> None:
        if self._rt:
            await asyncio.get_event_loop().run_in_executor(None, self._rt.close)

    # -- public API ---------------------------------------------------------

    async def send_audio(self, chunk: bytes) -> None:
        """Push a raw PCM chunk (LINEAR16, 16 kHz, mono) to AssemblyAI."""
        if self._rt is None:
            raise RuntimeError("RealtimeTranscriber is not connected.")
        await asyncio.get_event_loop().run_in_executor(
            None, self._rt.send_audio, chunk
        )

    async def events(self) -> AsyncGenerator[dict, None]:
        """
        Yield transcript events until the session closes.

        Each yielded dict::
            {"type": "partial" | "final" | "error" | "closed", "text": str}
        """
        while True:
            event = await self._queue.get()
            yield event
            if event["type"] in ("closed", "error"):
                break
