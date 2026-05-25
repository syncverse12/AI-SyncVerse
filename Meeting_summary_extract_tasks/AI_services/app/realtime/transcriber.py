"""
Real-time transcription via AssemblyAI streaming WebSocket.
Receives raw PCM audio chunks, streams them to AssemblyAI,
and yields partial + final transcript segments.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Callable, Optional
import websockets
from AI_services.app.config import settings
from AI_services.app.database.redis_client import append_to_list, set_value

logger = logging.getLogger(__name__)

ASSEMBLYAI_WS_URL = "wss://api.assemblyai.com/v2/realtime/ws"


class RealtimeTranscriber:
    """
    Wraps the AssemblyAI real-time WebSocket transcription API.
    """

    def __init__(
        self,
        meeting_id: str,
        sample_rate: int = 16000,
        on_partial: Optional[Callable] = None,
        on_final: Optional[Callable] = None,
    ):
        self.meeting_id = meeting_id
        self.sample_rate = sample_rate
        self.on_partial = on_partial
        self.on_final = on_final
        self._ws = None
        self._running = False
        self._full_transcript: list[str] = []

    async def connect(self):
        url = (
            f"{ASSEMBLYAI_WS_URL}"
            f"?sample_rate={self.sample_rate}"
            f"&token={settings.ASSEMBLYAI_API_KEY}"
            f"&language_detection=true"
            f"&speaker_labels=true"
        )
        self._ws = await websockets.connect(url, ping_interval=5, ping_timeout=20)
        self._running = True
        logger.info(f"AssemblyAI WS connected for meeting {self.meeting_id}")

    async def send_audio(self, pcm_chunk: bytes):
        if self._ws and self._running:
            try:
                await self._ws.send(pcm_chunk)
            except Exception as e:
                logger.error(f"Error sending audio chunk: {e}")

    async def listen(self):
        """
        Continuously read messages from AssemblyAI.
        Calls on_partial for interim results, on_final for completed utterances.
        """
        if not self._ws:
            raise RuntimeError("Not connected. Call connect() first.")

        async for raw_message in self._ws:
            try:
                msg = json.loads(raw_message)
                msg_type = msg.get("message_type")

                if msg_type == "PartialTranscript":
                    text = msg.get("text", "").strip()
                    if text and self.on_partial:
                        await self.on_partial({
                            "type": "partial",
                            "text": text,
                            "meeting_id": self.meeting_id,
                        })

                elif msg_type == "FinalTranscript":
                    text = msg.get("text", "").strip()
                    if text:
                        utterance = {
                            "type": "final",
                            "text": text,
                            "speaker": msg.get("words", [{}])[0].get("speaker", "Unknown") if msg.get("words") else "Unknown",
                            "start_ms": msg.get("audio_start", 0),
                            "end_ms": msg.get("audio_end", 0),
                            "confidence": msg.get("confidence", 1.0),
                            "meeting_id": self.meeting_id,
                        }
                        self._full_transcript.append(text)
                        await append_to_list(
                            f"transcript:{self.meeting_id}:utterances",
                            utterance,
                        )
                        if self.on_final:
                            await self.on_final(utterance)

                elif msg_type == "SessionBegins":
                    logger.info(f"AssemblyAI session started: {msg.get('session_id')}")

                elif msg_type == "SessionTerminated":
                    logger.info("AssemblyAI session terminated")
                    break

            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f"Transcription listen error: {e}")

    async def terminate(self) -> str:
        """Stop the session and return full transcript."""
        self._running = False
        if self._ws:
            try:
                await self._ws.send(json.dumps({"terminate_session": True}))
                await self._ws.close()
            except Exception:
                pass
        full_text = " ".join(self._full_transcript)
        await set_value(f"transcript:{self.meeting_id}:full_en", full_text, ttl=86400)
        return full_text

    def get_full_transcript(self) -> str:
        return " ".join(self._full_transcript)
