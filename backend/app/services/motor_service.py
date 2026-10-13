"""
MotorGuard — Motor Specification & Configuration Service
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException, status

from backend.app.schemas.motor import (
    MotorCreate,
    MotorUpdate,
    MotorOut,
    ElectricalSpecs,
    MechanicalSpecs,
    SensorsConfig,
    HealthThresholds,
    EdgeImpulseConfig,
)

logger = logging.getLogger("motorguard.motor_service")


class MotorService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["motors"]
        self.devices_collection = db["devices"]
        self.audit_collection = db["audit_events"]
        self.telemetry_collection = db["telemetry"]

    async def ensure_indexes(self) -> None:
        """Create indexes for motor registry."""
        await self.collection.create_index("motor_id", unique=True)
        await self.collection.create_index("assigned_device_id")
        await self.collection.create_index("site_id")
        logger.info("Motors collection indexes verified")

    async def _audit(self, action: str, user: str, target_id: str, details: Dict[str, Any]) -> None:
        """Record administrative action into immutable audit trail."""
        await self.audit_collection.insert_one({
            "event_id": str(uuid.uuid4()),
            "action": action,
            "user": user,
            "target_type": "motor",
            "target_id": target_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc),
        })

    async def create_motor(self, data: MotorCreate, username: str) -> MotorOut:
        """Register a new industrial motor asset."""
        existing = await self.collection.find_one({"motor_id": data.motor_id})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Motor ID '{data.motor_id}' is already registered in the plant registry",
            )

        now = datetime.now(timezone.utc)

        # Handle device assignment if requested
        if data.assigned_device_id:
            device = await self.devices_collection.find_one({"device_id": data.assigned_device_id})
            if not device:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Device '{data.assigned_device_id}' not found in registry. Enroll the device first.",
                )
            if device.get("assigned_motor_id") and device.get("assigned_motor_id") != data.motor_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Device '{data.assigned_device_id}' is already actively assigned to motor '{device.get('assigned_motor_id')}'. Unassign first.",
                )

            # Update device record
            await self.devices_collection.update_one(
                {"device_id": data.assigned_device_id},
                {"$set": {"assigned_motor_id": data.motor_id, "updated_at": now}},
            )

        doc = data.model_dump()
        doc["configuration_version"] = 1
        doc["health_status"] = "unknown"
        doc["operational_state"] = "OFFLINE"
        doc["created_at"] = now
        doc["updated_at"] = now
        doc["created_by"] = username

        await self.collection.insert_one(doc)
        await self._audit("CREATE_MOTOR", username, data.motor_id, {
            "name": data.name,
            "type": data.motor_type,
            "device": data.assigned_device_id,
            "site": data.site_id,
        })

        logger.info("Created motor '%s' (%s) by '%s'", data.motor_id, data.name, username)
        return MotorOut(**doc)

    async def get_motor(self, motor_id: str) -> Optional[MotorOut]:
        """Retrieve single motor asset by ID with live telemetry state."""
        doc = await self.collection.find_one({"motor_id": motor_id}, {"_id": 0})
        if not doc:
            return None

        # Enhance with live telemetry state if available
        last_telem = await self.telemetry_collection.find_one(
            {"motor_id": motor_id},
            {"_id": 0},
            sort=[("timestamp", -1)],
        )
        if last_telem:
            inf = last_telem.get("inference", {})
            doc["health_status"] = inf.get("health_status", doc.get("health_status", "unknown"))
            doc["operational_state"] = "RUNNING" if doc.get("status") == "active" else "OFFLINE"

        return MotorOut(**self._normalize_doc(doc))

    async def list_motors(self, site_id: Optional[str] = None) -> List[MotorOut]:
        """List all registered motor assets."""
        query = {}
        if site_id:
            query["site_id"] = site_id

        cursor = self.collection.find(query, {"_id": 0})
        docs = await cursor.to_list(length=200)

        results = []
        for d in docs:
            # Sync health state with latest telemetry
            last_telem = await self.telemetry_collection.find_one(
                {"motor_id": d["motor_id"]},
                {"_id": 0},
                sort=[("timestamp", -1)],
            )
            if last_telem:
                inf = last_telem.get("inference", {})
                d["health_status"] = inf.get("health_status", d.get("health_status", "unknown"))
                d["operational_state"] = "RUNNING" if d.get("status") == "active" else "OFFLINE"

            results.append(MotorOut(**self._normalize_doc(d)))

        return results

    async def update_motor_config(self, motor_id: str, data: MotorUpdate, username: str) -> MotorOut:
        """Update motor parameters, thresholds, and device associations."""
        existing = await self.collection.find_one({"motor_id": motor_id})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found")

        now = datetime.now(timezone.utc)
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}

        # Device assignment handling
        if "assigned_device_id" in update_dict:
            new_dev = update_dict["assigned_device_id"]
            old_dev = existing.get("assigned_device_id")

            if new_dev != old_dev:
                if new_dev:
                    device = await self.devices_collection.find_one({"device_id": new_dev})
                    if not device:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{new_dev}' not found")
                    if device.get("assigned_motor_id") and device.get("assigned_motor_id") != motor_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Device '{new_dev}' is already assigned to motor '{device.get('assigned_motor_id')}'",
                        )
                    await self.devices_collection.update_one(
                        {"device_id": new_dev},
                        {"$set": {"assigned_motor_id": motor_id, "updated_at": now}},
                    )

                if old_dev:
                    await self.devices_collection.update_one(
                        {"device_id": old_dev},
                        {"$set": {"assigned_motor_id": None, "updated_at": now}},
                    )

        new_version = existing.get("configuration_version", 1) + 1
        update_dict["configuration_version"] = new_version
        update_dict["updated_at"] = now

        await self.collection.update_one({"motor_id": motor_id}, {"$set": update_dict})
        await self._audit("UPDATE_CONFIG", username, motor_id, {
            "version": new_version,
            "fields": list(update_dict.keys()),
        })

        logger.info("Updated motor config for '%s' to version %d", motor_id, new_version)
        updated_doc = await self.collection.find_one({"motor_id": motor_id}, {"_id": 0})
        return MotorOut(**self._normalize_doc(updated_doc))

    async def disable_motor(self, motor_id: str, username: str) -> MotorOut:
        """Mark motor inactive and disable real-time dispatch."""
        existing = await self.collection.find_one({"motor_id": motor_id})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found")

        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"motor_id": motor_id},
            {"$set": {"status": "inactive", "operational_state": "OFFLINE", "updated_at": now}},
        )

        await self._audit("DISABLE_MOTOR", username, motor_id, {"previous_status": existing.get("status")})
        logger.info("Disabled motor '%s' by '%s'", motor_id, username)
        updated_doc = await self.collection.find_one({"motor_id": motor_id}, {"_id": 0})
        return MotorOut(**self._normalize_doc(updated_doc))

    async def get_audit_trail(self, limit: int = 50) -> List[dict]:
        """Fetch audit log events."""
        cursor = self.audit_collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        events = await cursor.to_list(length=limit)
        for e in events:
            if "timestamp" in e and hasattr(e["timestamp"], "isoformat"):
                e["timestamp"] = e["timestamp"].isoformat() + "Z"
        return events

    def _normalize_doc(self, doc: dict) -> dict:
        """Ensure all nested fields have expected defaults if loaded from older records."""
        if "motor_type" not in doc or not doc["motor_type"]:
            doc["motor_type"] = doc.get("model", "RS-775 Brushed DC")
        if "name" not in doc or not doc["name"]:
            doc["name"] = doc.get("motor_id", "Motor Unit")
        if "site_id" not in doc or not doc["site_id"]:
            doc["site_id"] = "SITE-PLANT-A"
        if "electrical_specs" not in doc:
            doc["electrical_specs"] = {
                "motor_type": doc.get("motor_type", "RS-775 Brushed DC"),
                "rated_voltage_v": doc.get("rated_voltage_v", 12.0),
                "rated_current_a": doc.get("rated_current_a", 2.5),
                "no_load_current_a": 0.5,
                "rated_speed_rpm": 12000,
                "max_speed_rpm": 18000,
                "rated_power_w": 30.0,
                "motor_supply_type": "External DC supply",
                "application_load": "Conveyor Feed Actuator",
            }
        if "mechanical_specs" not in doc or doc["mechanical_specs"] is None:
            doc["mechanical_specs"] = {
                "shaft_diameter_mm": 5.0,
                "weight_grams": 350.0,
                "mounting_type": "Face Mount (M4)",
                "cooling_type": "Internal Centrifugal Fan",
            }
        if "sensors_config" not in doc:
            doc["sensors_config"] = SensorsConfig().model_dump()
        if "thresholds" not in doc:
            doc["thresholds"] = HealthThresholds().model_dump()
        if "edge_impulse_config" not in doc:
            doc["edge_impulse_config"] = EdgeImpulseConfig().model_dump()
        if "status" not in doc:
            doc["status"] = "active"
        if "configuration_version" not in doc:
            doc["configuration_version"] = 1
        if "created_at" not in doc:
            doc["created_at"] = datetime.now(timezone.utc)
        if "updated_at" not in doc:
            doc["updated_at"] = datetime.now(timezone.utc)
        return doc

    async def seed_default_motors(self) -> None:
        """Seed rich motor specifications for baseline motors if missing."""
        now = datetime.now(timezone.utc)
        defaults = [
            {
                "motor_id": "MTR-775-001",
                "name": "Line 3 Conveyor Feed Actuator",
                "motor_type": "RS-775 Brushed DC",
                "manufacturer": "Johnson Electric",
                "model_number": "RS-775-12V-150W",
                "serial_number": "SN-775-2026-001A",
                "site_id": "SITE-PLANT-A",
                "installation_date": "2026-01-15",
                "description": "Primary material intake conveyor motor with active vibration damping.",
                "status": "active",
                "assigned_device_id": "esp32-node-001",
                "electrical_specs": {
                    "motor_type": "RS-775 Brushed DC",
                    "rated_voltage_v": 12.0,
                    "rated_current_a": 2.5,
                    "no_load_current_a": 0.45,
                    "rated_speed_rpm": 12000,
                    "max_speed_rpm": 18000,
                    "rated_power_w": 30.0,
                    "motor_supply_type": "External DC supply",
                    "application_load": "Conveyor Feed Drive",
                },
                "mechanical_specs": {
                    "shaft_diameter_mm": 5.0,
                    "weight_grams": 350.0,
                    "mounting_type": "Face Mount (M4)",
                    "cooling_type": "Internal Centrifugal Fan",
                },
                "sensors_config": SensorsConfig().model_dump(),
                "thresholds": HealthThresholds().model_dump(),
                "edge_impulse_config": EdgeImpulseConfig().model_dump(),
                "configuration_version": 1,
                "created_at": now,
                "updated_at": now,
                "created_by": "system_admin",
            },
            {
                "motor_id": "MTR-775-002",
                "name": "Spindle Cooling Fan Motor",
                "motor_type": "RS-775 Brushed DC",
                "manufacturer": "Mabuchi Motor",
                "model_number": "RS-775-WC-8515",
                "serial_number": "SN-775-2026-002B",
                "site_id": "SITE-PLANT-A",
                "installation_date": "2026-02-10",
                "description": "Secondary cooling airflow blower for main CNC spindle.",
                "status": "active",
                "assigned_device_id": "esp32-node-002",
                "electrical_specs": {
                    "motor_type": "RS-775 Brushed DC",
                    "rated_voltage_v": 12.0,
                    "rated_current_a": 2.8,
                    "no_load_current_a": 0.50,
                    "rated_speed_rpm": 11500,
                    "max_speed_rpm": 17500,
                    "rated_power_w": 33.6,
                    "motor_supply_type": "External DC supply",
                    "application_load": "Centrifugal Blower",
                },
                "mechanical_specs": {
                    "shaft_diameter_mm": 5.0,
                    "weight_grams": 350.0,
                    "mounting_type": "Face Mount (M4)",
                    "cooling_type": "Internal Centrifugal Fan",
                },
                "sensors_config": SensorsConfig().model_dump(),
                "thresholds": HealthThresholds().model_dump(),
                "edge_impulse_config": EdgeImpulseConfig().model_dump(),
                "configuration_version": 1,
                "created_at": now,
                "updated_at": now,
                "created_by": "system_admin",
            },
            {
                "motor_id": "MTR-775-003",
                "name": "High-Pressure Hydraulic Actuator",
                "motor_type": "RS-775 Brushed DC",
                "manufacturer": "Johnson Electric",
                "model_number": "RS-775-12V-150W",
                "serial_number": "SN-775-2026-003C",
                "site_id": "SITE-PLANT-A",
                "installation_date": "2026-03-01",
                "description": "Hydraulic booster drive. Subject to high mechanical vibration load.",
                "status": "active",
                "assigned_device_id": "esp32-node-003",
                "electrical_specs": {
                    "motor_type": "RS-775 Brushed DC",
                    "rated_voltage_v": 12.0,
                    "rated_current_a": 3.2,
                    "no_load_current_a": 0.60,
                    "rated_speed_rpm": 10800,
                    "max_speed_rpm": 16500,
                    "rated_power_w": 38.4,
                    "motor_supply_type": "External DC supply",
                    "application_load": "Hydraulic Pump",
                },
                "mechanical_specs": {
                    "shaft_diameter_mm": 5.0,
                    "weight_grams": 350.0,
                    "mounting_type": "Face Mount (M4)",
                    "cooling_type": "Internal Centrifugal Fan",
                },
                "sensors_config": SensorsConfig().model_dump(),
                "thresholds": HealthThresholds().model_dump(),
                "edge_impulse_config": EdgeImpulseConfig().model_dump(),
                "configuration_version": 1,
                "created_at": now,
                "updated_at": now,
                "created_by": "system_admin",
            },
        ]

        for m in defaults:
            await self.collection.update_one(
                {"motor_id": m["motor_id"]},
                {"$set": m},
                upsert=True,
            )
        logger.info("Baseline motor specifications verified in registry")
