"""
MotorGuard — WebSocket Hub

Manages real-time WebSocket connections for live telemetry broadcasting.
Connected dashboard clients receive validated telemetry events as they
are ingested from the MQTT pipeline.
"""

import asyncio
import json
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("motorguard.websocket")


class WebSocketManager:
    """Manages active WebSocket connections and broadcasts telemetry events."""

    def __init__(self):
        self._active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket, subprotocol: str = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        async with self._lock:
            self._active_connections.add(websocket)
        logger.info("WebSocket client connected (%d total)", self.connection_count)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._active_connections.discard(websocket)
        logger.info("WebSocket client disconnected (%d remaining)", self.connection_count)

    async def broadcast(self, data: dict) -> None:
        """Broadcast a telemetry event to all connected dashboard clients."""
        if not self._active_connections:
            return

        message = json.dumps(data, default=str)
        disconnected = set()

        async with self._lock:
            for ws in self._active_connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.add(ws)

        # Clean up broken connections
        if disconnected:
            async with self._lock:
                self._active_connections -= disconnected
            logger.info("Cleaned up %d broken WebSocket connections", len(disconnected))


ws_manager = WebSocketManager()
