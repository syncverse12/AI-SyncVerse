"""
WebSocket endpoint for employee dashboard real-time updates.
Employees connect here to receive:
- Their personal task assignments (pushed only to them)
- Meeting summary when the meeting ends (broadcast)
- Live transcript updates if they're in the meeting
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from AI_services.app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Dashboard WebSocket"])


@router.websocket("/dashboard")
async def dashboard_ws(
    websocket: WebSocket,
    employee_id: str = Query(...),
    meeting_id: str = Query(default=""),
):
    """
    Employee dashboard WebSocket.
    Sends:
      {event: "task_extracted", payload: Task}      — personal task delivery
      {event: "summary_ready", payload: Summary}    — meeting summary
      {event: "meeting_ended"}                      — cleanup signal
      {event: "transcript_chunk", payload: ...}     — if subscribed to a meeting
    """
    effective_meeting = meeting_id or f"__solo_{employee_id}"
    await manager.connect(websocket, effective_meeting, employee_id)

    try:
        await websocket.send_text(json.dumps({
            "event": "connected",
            "employee_id": employee_id,
            "meeting_id": meeting_id or None,
        }))

        while True:
            try:
                msg = await websocket.receive_text()
                data = json.loads(msg)
                if data.get("action") == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except WebSocketDisconnect:
                break
            except Exception:
                break

    finally:
        manager.disconnect(websocket)
        logger.info(f"Dashboard WS closed for employee {employee_id}")
