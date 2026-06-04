"""
Realtime WebSocket Manager — Redis Pub/Sub → WebSocket broadcast.

Architecture:
  Browser connects → ws://.../risk/ws/{project_id}
  Alert Engine publishes → Redis channel "alerts:{project_id}"
  Subscriber loop picks up → broadcasts to all connected clients
  Heartbeat keeps connections alive
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.database import get_pubsub_redis
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections per project.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self) -> None:
        # project_id → set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, project_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            if project_id not in self._connections:
                self._connections[project_id] = set()
            self._connections[project_id].add(websocket)
        logger.info(
            "WebSocket connected",
            project_id=project_id,
            total_connections=len(self._connections[project_id]),
        )

    async def disconnect(self, websocket: WebSocket, project_id: str) -> None:
        async with self._lock:
            if project_id in self._connections:
                self._connections[project_id].discard(websocket)
                if not self._connections[project_id]:
                    del self._connections[project_id]
        logger.info("WebSocket disconnected", project_id=project_id)

    async def broadcast(self, project_id: str, message: dict[str, Any]) -> None:
        """Send a message to all clients watching this project."""
        conns = self._connections.get(project_id, set()).copy()
        if not conns:
            return

        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.get(project_id, set()).discard(ws)

    def active_project_ids(self) -> list[str]:
        return list(self._connections.keys())

    def connection_count(self, project_id: str) -> int:
        return len(self._connections.get(project_id, set()))


# Singleton — shared across all routes
manager = ConnectionManager()


# ── WebSocket endpoint handler ────────────────────────────────────────────────

async def handle_ws_connection(
    websocket: WebSocket,
    project_id: str,
    risk_service: Any,
) -> None:
    """
    Full WebSocket lifecycle for a single client connection.

    Concurrently runs:
      1. Redis subscriber — pushes alerts/updates to client
      2. Heartbeat — pings every 30s to keep connection alive
      3. Client message handler — receives ACKs / custom requests
    """
    await manager.connect(websocket, project_id)

    # Send the current risk state immediately on connect
    try:
        snapshot = await risk_service.get_project_snapshot(UUID(project_id))
        await websocket.send_json(
            {
                "event": "snapshot",
                "project_id": project_id,
                "payload": snapshot,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        logger.warning("Failed to send initial snapshot", error=str(exc))

    redis = await get_pubsub_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"alerts:{project_id}")
    await pubsub.subscribe(f"risk_updates:{project_id}")

    try:
        await asyncio.gather(
            _redis_subscriber(pubsub, project_id),
            _heartbeat(websocket, project_id),
            _client_message_handler(websocket, project_id),
        )
    except WebSocketDisconnect:
        logger.info("Client disconnected gracefully", project_id=project_id)
    except Exception as exc:
        logger.error("WebSocket error", project_id=project_id, error=str(exc))
    finally:
        await pubsub.unsubscribe()
        await manager.disconnect(websocket, project_id)


async def _redis_subscriber(pubsub: Any, project_id: str) -> None:
    """Listen to Redis channels and broadcast to all connected clients."""
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            channel = message["channel"]

            # Determine event type from channel name
            if channel.startswith("alerts:"):
                event = "alert"
            elif channel.startswith("risk_updates:"):
                event = "risk_update"
            else:
                event = "event"

            await manager.broadcast(
                project_id,
                {
                    "event": event,
                    "project_id": project_id,
                    "payload": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.warning("Failed to process Redis message", error=str(exc))


async def _heartbeat(websocket: WebSocket, project_id: str) -> None:
    """Send periodic pings to keep the connection alive."""
    while True:
        await asyncio.sleep(settings.ws_heartbeat_interval)
        try:
            await websocket.send_json(
                {
                    "event": "heartbeat",
                    "project_id": project_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception:
            break  # Connection dead — let the outer handler clean up


async def _client_message_handler(websocket: WebSocket, project_id: str) -> None:
    """Handle incoming messages from the client (ACKs, custom requests)."""
    async for data in websocket.iter_json():
        event = data.get("event")
        logger.debug("Client message", project_id=project_id, event=event)
        # Extensible: handle "ack_alert", "request_refresh", etc.
