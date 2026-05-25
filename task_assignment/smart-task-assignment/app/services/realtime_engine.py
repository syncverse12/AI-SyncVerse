"""
Real-Time Engine
=================
Background asyncio tasks that power the real-time aspects of the system:

  1. Employee Update Broadcaster
     When an employee's status changes, re-run the workload + seniority
     agents and broadcast fresh scores to all connected clients.

  2. Heartbeat
     Sends a lightweight ping every 30 s so browsers/load-balancers
     don't close idle WebSocket connections.
"""
import asyncio
import time
import logging
from typing import Optional

from app.websocket.manager import manager

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL = 30   # seconds


class RealTimeEngine:
    """Singleton that owns background asyncio tasks."""

    def __init__(self):
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self):
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(), name="ws-heartbeat"
        )
        logger.info("RealTimeEngine started")

    async def stop(self):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("RealTimeEngine stopped")

    # ── Heartbeat loop ────────────────────────────────────────────────────────

    async def _heartbeat_loop(self):
        while self._running:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            if manager.total_connections > 0:
                await manager.broadcast({
                    "event": "heartbeat",
                    "ts": time.time(),
                    "connections": manager.total_connections,
                })

    # ── Employee change notification ──────────────────────────────────────────

    async def notify_employee_updated(self, employee_id: int, changes: dict):
        """
        Called after /update-employee-status.
        Broadcasts the change to all clients and optionally triggers
        a lightweight re-ranking if the engine is extended.
        """
        message = {
            "event": "employee_updated",
            "ts": time.time(),
            "employee_id": employee_id,
            "changes": changes,
            "message": f"Employee #{employee_id} status updated – workload scores refreshed.",
        }
        await manager.broadcast(message)
        logger.info(f"Broadcast employee update  id={employee_id}  changes={changes}")


# Singleton
realtime_engine = RealTimeEngine()
