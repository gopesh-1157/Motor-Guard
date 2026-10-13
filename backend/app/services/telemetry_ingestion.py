"""
MotorGuard — Telemetry Ingestion Service

Handles validated telemetry payload persistence into MongoDB with
idempotent deduplication via compound unique index on (device_id, event_id).
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from pymongo.errors import DuplicateKeyError
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("motorguard.ingestion")


class TelemetryIngestionService:
    """Persists validated telemetry documents to MongoDB with deduplication."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["telemetry"]

    async def ensure_indexes(self) -> None:
        """Create compound indexes required for deduplication and query performance."""
        # Idempotent deduplication index
        await self.collection.create_index(
            [("device_id", 1), ("event_id", 1)],
            unique=True,
            name="idx_dedup_device_event",
        )
        # Time-series query optimization
        await self.collection.create_index(
            [("motor_id", 1), ("timestamp", -1)],
            name="idx_motor_time_desc",
        )
        # TTL index on server_received_at for automatic retention cleanup
        await self.collection.create_index(
            [("server_received_at", 1)],
            name="idx_ttl_retention",
            # TTL value configured externally; 0 means no auto-delete until set
        )
        logger.info("Telemetry collection indexes ensured")

    async def ingest(self, payload: Dict[str, Any]) -> bool:
        """
        Insert a validated telemetry document into MongoDB.

        Returns True if inserted successfully, False if duplicate was safely dropped.
        Raises on unexpected errors.
        """
        # Stamp server-side receipt time
        payload["server_received_at"] = datetime.now(timezone.utc)

        try:
            result = await self.collection.insert_one(payload)
            logger.debug(
                "Inserted telemetry event_id=%s device_id=%s _id=%s",
                payload.get("event_id"),
                payload.get("device_id"),
                result.inserted_id,
            )
            return True
        except DuplicateKeyError:
            logger.info(
                "Duplicate telemetry safely dropped: event_id=%s device_id=%s",
                payload.get("event_id"),
                payload.get("device_id"),
            )
            return False
