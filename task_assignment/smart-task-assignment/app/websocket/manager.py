"""
WebSocket Connection Manager
Handles multiple concurrent WebSocket clients with topic-based broadcasting.
"""
import asyncio
import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections grouped by task_id (topic).
    Supports:
      - per-task channels  (broadcast to all clients watching a specific task)
      - global channel     (broadcast to ALL connected clients)
    """

    def __init__(self):
        # task_id → set of WebSocket connections
        self._task_connections: Dict[str, Set[WebSocket]] = {}
        # All active connections (for global broadcasts)
        self._all_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket, task_id: str = "global") -> None:
        await websocket.accept()
        async with self._lock:
            self._all_connections.add(websocket)
            self._task_connections.setdefault(task_id, set()).add(websocket)
        logger.info(f"WS connected  task_id={task_id}  total={len(self._all_connections)}")

    async def disconnect(self, websocket: WebSocket, task_id: str = "global") -> None:
        async with self._lock:
            self._all_connections.discard(websocket)
            if task_id in self._task_connections:
                self._task_connections[task_id].discard(websocket)
                if not self._task_connections[task_id]:
                    del self._task_connections[task_id]
        logger.info(f"WS disconnected  task_id={task_id}  total={len(self._all_connections)}")

    # ── Send helpers ──────────────────────────────────────────────────────────

    async def _send_safe(self, websocket: WebSocket, message: dict) -> bool:
        """Send JSON to a single socket; return False if the socket is dead."""
        try:
            await websocket.send_json(message)
            return True
        except Exception as exc:
            logger.warning(f"Send failed, dropping connection: {exc}")
            return False

    async def send_to_task(self, task_id: str, message: dict) -> None:
        """Broadcast a message to all clients subscribed to `task_id`."""
        async with self._lock:
            targets = list(self._task_connections.get(task_id, set()))

        dead: List[WebSocket] = []
        for ws in targets:
            ok = await self._send_safe(ws, message)
            if not ok:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._all_connections.discard(ws)
                    self._task_connections.get(task_id, set()).discard(ws)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to ALL connected clients."""
        async with self._lock:
            targets = list(self._all_connections)

        dead: List[WebSocket] = []
        for ws in targets:
            ok = await self._send_safe(ws, message)
            if not ok:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._all_connections.discard(ws)

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def total_connections(self) -> int:
        return len(self._all_connections)

    def task_connections(self, task_id: str) -> int:
        return len(self._task_connections.get(task_id, set()))


# Singleton — imported everywhere
manager = ConnectionManager()
