"""
WebSocket endpoint for live meeting audio streaming.
Clients connect, stream raw PCM audio bytes, and receive:
- partial transcript chunks
- final transcript segments
- real-time Arabic translations

Audio format expected: 16kHz, 16-bit PCM, mono (little-endian)
"""
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from AI_services.app.database.session import get_db
from AI_services.app.database.redis_client import publish
from AI_services.app.models.models import Meeting, MeetingStatus, Transcript
from AI_services.app.realtime.transcriber import RealtimeTranscriber
from AI_services.app.realtime.translator import TranslationPipeline, detect_language
from AI_services.app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/meeting/stream")
async def meeting_audio_stream(
    websocket: WebSocket,
    meeting_id: str = Query(...),
    employee_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket for real-time audio streaming.

    Protocol:
    - Client sends raw PCM audio bytes (16kHz, 16-bit, mono)
    - Client may also send JSON control messages:
        {"action": "end_stream"} — signals end of meeting
        {"action": "ping"} — keepalive
    - Server pushes JSON events:
        {event: "transcript_chunk", payload: {text, type: "partial"|"final"}}
        {event: "translation_chunk", payload: {en, ar}}
        {event: "stream_started"}
    """
    await manager.connect(websocket, meeting_id, employee_id)

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        await websocket.send_text(json.dumps({"event": "error", "detail": "Meeting not found"}))
        await websocket.close()
        manager.disconnect(websocket)
        return

    if meeting.status == MeetingStatus.COMPLETED:
        await websocket.send_text(json.dumps({"event": "error", "detail": "Meeting already completed"}))
        await websocket.close()
        manager.disconnect(websocket)
        return

    meeting.status = MeetingStatus.ACTIVE
    await db.commit()

    transcript_row = Transcript(meeting_id=meeting_id, full_text_en="", full_text_ar="")
    db.add(transcript_row)
    await db.commit()

    translator = TranslationPipeline(meeting_id)

    async def on_partial(payload: dict):
        await manager.broadcast_to_meeting(meeting_id, "transcript_chunk", {
            **payload, "final": False
        })

    async def on_final(payload: dict):
        await manager.broadcast_to_meeting(meeting_id, "transcript_chunk", {
            **payload, "final": True
        })
        text = payload.get("text", "")
        lang = await detect_language(text)
        translation = await translator.process_segment(text, source_lang=lang)
        await manager.broadcast_to_meeting(meeting_id, "translation_chunk", translation)

    transcriber = RealtimeTranscriber(
        meeting_id=meeting_id,
        on_partial=on_partial,
        on_final=on_final,
    )

    try:
        await transcriber.connect()
        await websocket.send_text(json.dumps({"event": "stream_started", "meeting_id": meeting_id}))

        listen_task = asyncio.create_task(transcriber.listen())

        while True:
            try:
                data = await websocket.receive()
            except WebSocketDisconnect:
                logger.info(f"Client disconnected from meeting {meeting_id}")
                break

            if "bytes" in data:
                await transcriber.send_audio(data["bytes"])

            elif "text" in data:
                try:
                    control = json.loads(data["text"])
                    action = control.get("action")
                    if action == "end_stream":
                        logger.info(f"End stream signal for meeting {meeting_id}")
                        break
                    elif action == "ping":
                        await websocket.send_text(json.dumps({"event": "pong"}))
                except json.JSONDecodeError:
                    pass

        listen_task.cancel()
        full_text = await transcriber.terminate()

        await publish(f"meeting:end:{meeting_id}", {"meeting_id": meeting_id})
        await websocket.send_text(json.dumps({
            "event": "stream_ended",
            "meeting_id": meeting_id,
            "transcript_length": len(full_text),
        }))

    except Exception as e:
        logger.error(f"WebSocket error in meeting {meeting_id}: {e}")
        try:
            await websocket.send_text(json.dumps({"event": "error", "detail": str(e)}))
        except Exception:
            pass
    finally:
        manager.disconnect(websocket)
