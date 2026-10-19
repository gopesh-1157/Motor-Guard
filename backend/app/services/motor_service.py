"""
MotorGuard — Motor Specification & Configuration Service
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
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

    async def get_effective_thresholds(self, motor_doc: Union[dict, str, None] = None) -> dict:
        """
        Resolves operational thresholds in priority order:
        1. Motor-specific thresholds in motor_doc (if configured).
        2. Gateway operational limits saved in 'system_settings' collection.
        3. Built-in defaults.
        """
        from backend.app.config import settings
        defaults = {
            "current_warning_a": getattr(settings, "DEFAULT_OVERCURRENT_LIMIT_A", 4.0) * 0.85,
            "current_critical_a": getattr(settings, "DEFAULT_OVERCURRENT_LIMIT_A", 4.0),
            "temperature_warning_c": getattr(settings, "DEFAULT_MAX_TEMP_C", 50.0),
            "temperature_critical_c": 75.0,
            "vibration_warning_g": getattr(settings, "DEFAULT_MAX_VIBRATION_G", 0.100),
            "vibration_critical_g": 0.400,
            "peak_vibration_g": getattr(settings, "DEFAULT_MAX_PEAK_VIBRATION_G", 0.350),
            "stale_timeout_sec": getattr(settings, "DEVICE_STALE_TIMEOUT_SEC", 15),
            "offline_timeout_sec": getattr(settings, "DEVICE_OFFLINE_TIMEOUT_SEC", 35),
            "provenance": "builtin_config_default",
            "calibration_status": "provisional",
        }

        if self.db is not None:
            try:
                sys_doc = await self.db["system_settings"].find_one({"_id": "gateway_operational_limits"})
                if isinstance(sys_doc, dict):
                    defaults["provenance"] = "gateway_system_settings"
                    for k in [
                        "current_warning_a", "current_critical_a",
                        "temperature_warning_c", "temperature_critical_c",
                        "vibration_warning_g", "vibration_critical_g",
                        "peak_vibration_g", "stale_timeout_sec", "offline_timeout_sec"
                    ]:
                        if k in sys_doc and sys_doc[k] is not None:
                            defaults[k] = float(sys_doc[k])
            except Exception as e:
                logger.debug("Could not fetch gateway operational limits: %s", e)

        # If motor_doc is a string motor_id, query collection
        if isinstance(motor_doc, str):
            motor_id_str = motor_doc
            if self.collection is not None:
                motor_doc = await self.collection.find_one({"motor_id": motor_id_str}, {"_id": 0})
            elif self.db is not None:
                motor_doc = await self.db["motors"].find_one({"motor_id": motor_id_str}, {"_id": 0})

        if isinstance(motor_doc, dict) and "thresholds" in motor_doc and isinstance(motor_doc["thresholds"], dict):
            m_th = motor_doc["thresholds"]
            overridden = False
            for k in [
                "current_warning_a", "current_critical_a",
                "temperature_warning_c", "temperature_critical_c",
                "vibration_warning_g", "vibration_critical_g",
                "peak_vibration_g",
            ]:
                if k in m_th and m_th[k] is not None:
                    defaults[k] = float(m_th[k])
                    overridden = True
            if "device_offline_timeout_sec" in m_th and m_th["device_offline_timeout_sec"] is not None:
                defaults["offline_timeout_sec"] = float(m_th["device_offline_timeout_sec"])
            if "calibration_status" in m_th and m_th["calibration_status"]:
                defaults["calibration_status"] = m_th["calibration_status"]
            defaults["provenance"] = m_th.get("provenance") or ("motor_asset_override" if overridden else defaults["provenance"])

        return defaults

    async def calculate_motor_health(
        self,
        motor_id: str,
        motor_doc: dict,
        last_telem: Optional[dict] = None,
        effective_thresholds: Optional[dict] = None,
    ) -> str:
        """
        Calculates motor health status ('healthy', 'warning', 'critical', 'unknown'):
        1. Active alerts in 'alerts' collection (if CRITICAL -> critical, if WARNING -> warning).
        2. Physical sensors in latest telemetry evaluated against effective operational thresholds.
        3. TinyML Edge Impulse inference health_status.
        """
        if self.db is not None:
            try:
                active_critical = await self.db["alerts"].find_one({
                    "motor_id": motor_id,
                    "state": "ACTIVE",
                    "severity": "CRITICAL",
                })
                if active_critical:
                    return "critical"

                active_warning = await self.db["alerts"].find_one({
                    "motor_id": motor_id,
                    "state": "ACTIVE",
                    "severity": "WARNING",
                })
                if active_warning:
                    return "warning"
            except Exception as e:
                logger.debug("Error checking active alerts for motor %s: %s", motor_id, e)

        if last_telem:
            sensors = last_telem.get("sensors", {})
            sensor_status = last_telem.get("sensor_status", {})
            inf = last_telem.get("inference", {})
            if effective_thresholds is None:
                effective_thresholds = await self.get_effective_thresholds(motor_doc)

            temp = sensors.get("temperature_c")
            curr = sensors.get("current_a")
            vib = sensors.get("vibration_g_rms")

            # Check if all sensor readings are missing / disconnected
            if temp is None and curr is None and vib is None:
                return "unknown"

            # Check for disconnected sensor status
            if (
                sensor_status.get("current") in ("DISCONNECTED", "UNAVAILABLE", "OUT_OF_RANGE")
                or sensor_status.get("vibration") in ("DISCONNECTED", "UNAVAILABLE", "OUT_OF_RANGE")
            ):
                return "critical"
            if sensor_status.get("temperature") in ("DISCONNECTED", "UNAVAILABLE", "OUT_OF_RANGE"):
                return "warning"

            if (
                (temp is not None and temp >= effective_thresholds["temperature_critical_c"])
                or (curr is not None and curr >= effective_thresholds["current_critical_a"])
                or (vib is not None and vib >= effective_thresholds["vibration_critical_g"])
            ):
                return "critical"

            if (
                (temp is not None and temp >= effective_thresholds["temperature_warning_c"])
                or (curr is not None and curr >= effective_thresholds["current_warning_a"])
                or (vib is not None and vib >= effective_thresholds["vibration_warning_g"])
            ):
                return "warning"

            if inf.get("health_status") in ("healthy", "warning", "critical"):
                return inf["health_status"]

        return motor_doc.get("health_status", "unknown")

    async def get_motor(self, motor_id: str) -> Optional[MotorOut]:
        """Retrieve single motor asset by ID with live telemetry state."""
        doc = await self.collection.find_one({"motor_id": motor_id}, {"_id": 0})
        if not doc:
            return None

        # Enhance with live telemetry state and effective thresholds
        last_telem = await self.telemetry_collection.find_one(
            {"motor_id": motor_id},
            {"_id": 0},
            sort=[("timestamp", -1)],
        )
        thresholds = await self.get_effective_thresholds(doc)
        doc["effective_thresholds"] = thresholds
        doc["health_status"] = await self.calculate_motor_health(motor_id, doc, last_telem, thresholds)
        if last_telem:
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
            # Sync health state with latest telemetry and effective thresholds
            last_telem = await self.telemetry_collection.find_one(
                {"motor_id": d["motor_id"]},
                {"_id": 0},
                sort=[("timestamp", -1)],
            )
            m_eff = await self.get_effective_thresholds(d)
            d["effective_thresholds"] = m_eff
            d["health_status"] = await self.calculate_motor_health(d["motor_id"], d, last_telem, m_eff)
            if last_telem:
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
