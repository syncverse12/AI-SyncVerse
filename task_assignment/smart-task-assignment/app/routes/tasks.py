"""
Task routes
  POST /analyze-task          – submit a task, get task_id back; pipeline runs async
  WS   /ws/task-updates/{id}  – subscribe to live updates for a specific task
  WS   /ws/global             – subscribe to all system-wide events
"""
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from app.models.schemas import TaskInput
from app.models.employee_store import employee_store
from app.websocket.manager import manager
from app.services.task_pipeline import run_task_pipeline
from app.utils.helpers import generate_task_id

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tasks"])


# ── HTTP: Submit task ─────────────────────────────────────────────────────────

@router.post("/analyze-task", summary="Submit a task for real-time AI analysis")
async def analyze_task(task: TaskInput, background_tasks: BackgroundTasks):
    """
    Accepts a task description and immediately returns a task_id.
    The multi-agent pipeline runs in the background and streams
    results to any WebSocket clients subscribed to that task_id.
    """
    employees = await employee_store.get_all()
    if not employees:
        raise HTTPException(status_code=400, detail="No employees in the system.")

    task_id = generate_task_id()

    # Fire the pipeline as a background task so this endpoint returns instantly
    background_tasks.add_task(run_task_pipeline, task, task_id)

    return {
        "task_id": task_id,
        "status": "processing",
        "message": "Pipeline started. Connect to WebSocket to receive live updates.",
        "ws_url": f"/ws/task-updates/{task_id}",
    }


# ── HTTP: Analyse & await (synchronous variant for REST clients) ──────────────

@router.post("/analyze-task/sync", summary="Submit task and wait for final result (no streaming)")
async def analyze_task_sync(task: TaskInput):
    """
    Synchronous variant – waits for the full pipeline and returns the result.
    Useful for REST clients that do not support WebSockets.
    """
    employees = await employee_store.get_all()
    if not employees:
        raise HTTPException(status_code=400, detail="No employees in the system.")

    task_id = generate_task_id()
    result = await run_task_pipeline(task, task_id)
    return result.dict()


# ── WebSocket: per-task updates ───────────────────────────────────────────────

@router.websocket("/ws/task-updates/{task_id}")
async def ws_task_updates(websocket: WebSocket, task_id: str):
    """
    Clients connect here BEFORE or immediately AFTER calling POST /analyze-task.
    They receive every agent event + the final ranking in real time.
    """
    await manager.connect(websocket, task_id)
    logger.info(f"WS client subscribed  task_id={task_id}")
    try:
        while True:
            # Keep the connection alive; we only push, but still receive pings
            data = await websocket.receive_text()
            logger.debug(f"WS received from client  task_id={task_id}  data={data}")
    except WebSocketDisconnect:
        logger.info(f"WS client disconnected  task_id={task_id}")
    finally:
        await manager.disconnect(websocket, task_id)


# ── WebSocket: global system events ──────────────────────────────────────────

@router.websocket("/ws/global")
async def ws_global(websocket: WebSocket):
    """
    Receive all system-wide events:
      - employee_updated
      - heartbeat
    """
    await manager.connect(websocket, "global")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket, "global")
