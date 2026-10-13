"""
MotorGuard — Maintenance Records Database Service

Manages persistence and queries for the 'maintenance_records' collection.
"""

from datetime import datetime, timezone
import logging
import uuid
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.schemas.maintenance import MaintenanceRecordCreate, MaintenanceRecordOut
from backend.app.schemas.user import UserOut

logger = logging.getLogger("motorguard.maintenance_service")


class MaintenanceService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["maintenance_records"]

    async def ensure_indexes(self) -> None:
        """Create indexes for maintenance records."""
        await self.collection.create_index([("record_id", 1)], unique=True)
        await self.collection.create_index([("motor_id", 1), ("timestamp", -1)])
        await self.collection.create_index([("technician_id", 1)])
        logger.info("Maintenance records collection indexes verified")

    async def create_record(
        self, record_in: MaintenanceRecordCreate, user: UserOut
    ) -> MaintenanceRecordOut:
        """Insert a maintenance work log entry."""
        now = datetime.now(timezone.utc)
        record_id = f"MAINT-{now.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

        doc = record_in.model_dump()
        doc["record_id"] = record_id
        doc["technician_id"] = user.username
        doc["technician_name"] = user.username
        doc["timestamp"] = now

        result = await self.collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        logger.info("Created maintenance record %s for %s by %s", record_id, record_in.motor_id, user.username)
        return MaintenanceRecordOut(**doc)

    async def list_records(
        self, motor_id: Optional[str] = None, limit: int = 50
    ) -> List[MaintenanceRecordOut]:
        """Query maintenance records for a motor or entire fleet."""
        query: dict = {}
        if motor_id:
            query["motor_id"] = motor_id

        cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)
        records: List[MaintenanceRecordOut] = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id", ""))
            records.append(MaintenanceRecordOut(**doc))
        return records
