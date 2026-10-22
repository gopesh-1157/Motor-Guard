"""
MotorGuard — WebSocket Hub

Manages real-time WebSocket connections for live telemetry broadcasting.
Connected dashboard clients receive validated telemetry events as they
are ingested from the MQTT pipeline, scoped by user authorization (MG-F01).
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger("motorguard.websocket")


class WebSocketManager:
    """
    Manages active WebSocket connections and broadcasts telemetry and alert events
    with RBAC and site/motor authorization scoping (MG-F01).
    """

    def __init__(self):
        self._connections: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(
        self,
        websocket: WebSocket,
        subprotocol: Optional[str] = None,
        user: Optional[Any] = None,
    ) -> None:
        await websocket.accept(subprotocol=subprotocol)
        metadata = {
            "user": user,
            "username": getattr(user, "username", "anonymous") if user else "anonymous",
            "role": getattr(user, "role", "Operator") if user else "Operator",
            "assigned_sites": set(getattr(user, "assigned_sites", []) or []),
            "assigned_motors": set(getattr(user, "assigned_motors", []) or []),
        }
        async with self._lock:
            self._connections[websocket] = metadata
        logger.info(
            "WebSocket client connected (%d total) [user=%s role=%s sites=%s motors=%s]",
            self.connection_count,
            metadata["username"],
            metadata["role"],
            list(metadata["assigned_sites"]),
            list(metadata["assigned_motors"]),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(websocket, None)
        logger.info("WebSocket client disconnected (%d remaining)", self.connection_count)

    def is_authorized_for_event(self, metadata: Dict[str, Any], data: dict) -> bool:
        """
        Check if a connected user is authorized to receive this event based on role,
        assigned motors, and assigned sites.
        """
        role = metadata.get("role", "Operator")
        assigned_sites = metadata.get("assigned_sites", set())
        assigned_motors = metadata.get("assigned_motors", set())

        # Admin has fleet-wide visibility
        if role == "Admin":
            return True

        # Extract event payload and attributes
        payload = data.get("data") if isinstance(data, dict) and "data" in data else data
        if not isinstance(payload, dict):
            return True

        motor_id = payload.get("motor_id")
        site_id = payload.get("site_id")

        if role == "Manager":
            from backend.app.config import settings
            allow_unscoped = getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False)
            is_prod = settings.ENVIRONMENT.strip().lower() == "production"
            if is_prod and not assigned_sites and not allow_unscoped:
                return False

            # If user has explicit assigned sites, check site scope
            if assigned_sites:
                if not site_id:
                    # Never broadcast an alert fleet-wide merely because site_id is absent.
                    # Withhold the event when site authorization cannot be established.
                    return False
                if site_id not in assigned_sites:
                    return False

            # If manager has explicit assigned motors, check motor scope
            if assigned_motors and motor_id:
                if motor_id not in assigned_motors:
                    return False

            return True

        if role == "Technician":
            # Technician receives alerts assigned directly to them
            if payload.get("assigned_to") == metadata.get("username"):
                return True
            # Or events for their explicitly authorized motors
            if assigned_motors and motor_id and motor_id in assigned_motors:
                return True
            # Empty assignment list, unassigned motors, or missing asset scope -> fail closed
            return False

        return False

    async def broadcast(self, data: dict) -> None:
        """Broadcast a telemetry or alert event to authorized connected dashboard clients."""
        if not self._connections:
            return

        message = json.dumps(data, default=str)
        disconnected = set()

        async with self._lock:
            for ws, meta in list(self._connections.items()):
                if not self.is_authorized_for_event(meta, data):
                    continue
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.add(ws)

        # Clean up broken connections
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._connections.pop(ws, None)
            logger.info("Cleaned up %d broken WebSocket connections", len(disconnected))


ws_manager = WebSocketManager()

