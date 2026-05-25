import json
import asyncio
from datetime import datetime
from typing import Dict, Set, Any
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections grouped by meeting_id and employee_id.
    Supports:
    - Broadcasting to all connections in a meeting (transcript/summary)
    - Targeting a single employee connection (task delivery)
    """

    def __init__(self):
        self._meeting_connections: Dict[str, Set[WebSocket]] = {}
        self._employee_connections: Dict[str, Set[WebSocket]] = {}
        self._ws_meta: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, meeting_id: str, employee_id: str):
        await websocket.accept()
        self._meeting_connections.setdefault(meeting_id, set()).add(websocket)
        self._employee_connections.setdefault(employee_id, set()).add(websocket)
        self._ws_meta[websocket] = {"meeting_id": meeting_id, "employee_id": employee_id}
        logger.info(f"WS connected: employee={employee_id} meeting={meeting_id}")

    def disconnect(self, websocket: WebSocket):
        meta = self._ws_meta.pop(websocket, {})
        meeting_id = meta.get("meeting_id")
        employee_id = meta.get("employee_id")
        if meeting_id and meeting_id in self._meeting_connections:
            self._meeting_connections[meeting_id].discard(websocket)
            if not self._meeting_connections[meeting_id]:
                del self._meeting_connections[meeting_id]
        if employee_id and employee_id in self._employee_connections:
            self._employee_connections[employee_id].discard(websocket)
            if not self._employee_connections[employee_id]:
                del self._employee_connections[employee_id]
        logger.info(f"WS disconnected: employee={employee_id} meeting={meeting_id}")

    async def broadcast_to_meeting(self, meeting_id: str, event: str, payload: Any):
        message = json.dumps({
            "event": event,
            "meeting_id": meeting_id,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        })
        connections = self._meeting_connections.get(meeting_id, set()).copy()
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_to_employee(self, employee_id: str, event: str, payload: Any):
        message = json.dumps({
            "event": event,
            "employee_id": employee_id,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        })
        connections = self._employee_connections.get(employee_id, set()).copy()
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def meeting_has_connections(self, meeting_id: str) -> bool:
        return bool(self._meeting_connections.get(meeting_id))

    def connection_count(self, meeting_id: str) -> int:
        return len(self._meeting_connections.get(meeting_id, set()))


manager = ConnectionManager()
