"""
mic_client.py
=============
Command-line microphone client for the real-time STT WebSocket endpoint.

Captures audio from the default microphone and streams it to the server,
printing partial and final transcripts as they arrive.

Requirements (beyond the service requirements.txt):
    pip install pyaudio websockets

Usage:
    python mic_client.py [--url ws://localhost:8010/transcribe/stream]

Press Ctrl+C to stop recording.

Audio format sent:
    Encoding   : PCM signed 16-bit little-endian (LINEAR16)
    Sample rate: 16 000 Hz
    Channels   : 1 (mono)
    Chunk size : 3 200 bytes = 100 ms per frame
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import threading

try:
    import pyaudio
except ImportError:
    sys.exit("pyaudio is required: pip install pyaudio")

try:
    import websockets
except ImportError:
    sys.exit("websockets is required: pip install websockets")

# ── audio constants ──────────────────────────────────────────────────────────
SAMPLE_RATE   = 16_000   # Hz  — required by AssemblyAI real-time
CHANNELS      = 1        # mono
FORMAT        = pyaudio.paInt16  # LINEAR16 / PCM signed 16-bit
CHUNK_FRAMES  = 1_600    # frames per chunk  → 100 ms at 16 kHz
CHUNK_BYTES   = CHUNK_FRAMES * CHANNELS * 2  # 2 bytes per int16 sample


async def stream(url: str) -> None:
    print(f"Connecting to {url} …")
    async with websockets.connect(url) as ws:
        print("Connected. Speak into your microphone. Press Ctrl+C to stop.\n")

        # ── Audio capture in a background thread ──────────────────────────
        audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        loop = asyncio.get_event_loop()

        pa = pyaudio.PyAudio()
        stream_in = pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_FRAMES,
        )

        stop_event = threading.Event()

        def _capture():
            try:
                while not stop_event.is_set():
                    chunk = stream_in.read(CHUNK_FRAMES, exception_on_overflow=False)
                    loop.call_soon_threadsafe(audio_queue.put_nowait, chunk)
            finally:
                loop.call_soon_threadsafe(audio_queue.put_nowait, None)  # sentinel

        capture_thread = threading.Thread(target=_capture, daemon=True)
        capture_thread.start()

        # ── Sender coroutine ──────────────────────────────────────────────
        async def _send():
            while True:
                chunk = await audio_queue.get()
                if chunk is None:
                    break
                await ws.send(chunk)

        # ── Receiver coroutine ────────────────────────────────────────────
        async def _receive():
            async for message in ws:
                event = json.loads(message)
                t = event.get("type", "")
                text = event.get("text", "")

                if t == "partial":
                    # Overwrite the current line with the latest hypothesis
                    print(f"\r\033[K[partial] {text}", end="", flush=True)
                elif t == "final":
                    print(f"\r\033[K[FINAL]   {text}")
                elif t == "error":
                    print(f"\n[ERROR]   {text}", file=sys.stderr)
                elif t == "closed":
                    print("\n[INFO] Session closed by server.")
                    break

        try:
            await asyncio.gather(_send(), _receive())
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            stop_event.set()
            stream_in.stop_stream()
            stream_in.close()
            pa.terminate()
            capture_thread.join(timeout=2)
            print("\n\nRecording stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time STT microphone client")
    parser.add_argument(
        "--url",
        default="ws://localhost:8010/transcribe/stream",
        help="WebSocket URL of the STT service (default: ws://localhost:8010/transcribe/stream)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(stream(args.url))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
