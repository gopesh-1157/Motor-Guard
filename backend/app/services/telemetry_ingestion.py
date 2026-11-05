"""
MotorGuard — Telemetry Ingestion Service

Handles validated telemetry payload persistence into MongoDB with
idempotent deduplication via compound unique index on (device_id, event_id).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from pymongo.errors import DuplicateKeyError, OperationFailure
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.config import settings

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
        # TTL index on server_received_at for automatic retention cleanup (MG-F08)
        retention_seconds = int(settings.TELEMETRY_RETENTION_DAYS * 86400)
        try:
            if hasattr(self.collection, "index_information"):
                info_res = self.collection.index_information()
                if asyncio.isfuture(info_res) or asyncio.iscoroutine(info_res):
                    existing_indexes = await info_res
                elif asyncio.iscoroutinefunction(self.collection.index_information):
                    existing_indexes = await self.collection.index_information()
                else:
                    existing_indexes = info_res

                if isinstance(existing_indexes, dict) and "idx_ttl_retention" in existing_indexes:
                    curr_expire = existing_indexes["idx_ttl_retention"].get("expireAfterSeconds")
                    if curr_expire != retention_seconds:
                        logger.info(
                            "Migrating idx_ttl_retention: dropping existing index with expireAfterSeconds=%s to apply %d",
                            curr_expire,
                            retention_seconds,
                        )
                        drop_res = self.collection.drop_index("idx_ttl_retention")
                        if asyncio.isfuture(drop_res) or asyncio.iscoroutine(drop_res):
                            await drop_res
        except Exception as exc:
            logger.debug("TTL index check/migration note: %s", exc)

        try:
            await self.collection.create_index(
                [("server_received_at", 1)],
                name="idx_ttl_retention",
                expireAfterSeconds=retention_seconds,
            )
        except OperationFailure as exc:
            if exc.code == 85:  # IndexOptionsConflict
                logger.warning(
                    "IndexOptionsConflict on idx_ttl_retention (code 85); dropping and recreating index with expireAfterSeconds=%d",
                    retention_seconds,
                )
                try:
                    drop_res = self.collection.drop_index("idx_ttl_retention")
                    if asyncio.isfuture(drop_res) or asyncio.iscoroutine(drop_res):
                        await drop_res
                    await self.collection.create_index(
                        [("server_received_at", 1)],
                        name="idx_ttl_retention",
                        expireAfterSeconds=retention_seconds,
                    )
                except Exception as drop_exc:
                    logger.error("Failed to drop and recreate idx_ttl_retention: %s", drop_exc)
            else:
                logger.warning("create_index idx_ttl_retention note: %s", exc)

        logger.info("Telemetry collection indexes ensured (TTL retention: %d seconds / %d days)", retention_seconds, settings.TELEMETRY_RETENTION_DAYS)

    async def ingest(self, payload: Dict[str, Any]) -> bool:
        """
        Insert a validated telemetry document into MongoDB.

        Returns True if inserted successfully, False if duplicate was safely dropped.
        Raises on unexpected errors.
        """
        # Stamp server-side receipt time. Device clocks are untrusted for liveness:
        # malformed or materially delayed packets remain available for audit but are
        # quarantined from live state and alert recovery.
        received_at = datetime.now(timezone.utc)
        payload["server_received_at"] = received_at
        payload["liveness_eligible"] = self._is_liveness_eligible(payload.get("timestamp"), received_at)

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

    @staticmethod
    def _is_liveness_eligible(timestamp: Any, received_at: datetime) -> bool:
        if not isinstance(timestamp, str):
            return False
        try:
            event_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return False
        if event_at.tzinfo is None:
            return False
        # Existing offline timeout is 35 seconds. A larger tolerance avoids
        # rejecting ordinary transport jitter while preventing stale replay from
        # reviving a device.
        age_seconds = (received_at - event_at.astimezone(timezone.utc)).total_seconds()
        return -300.0 <= age_seconds <= 60.0
