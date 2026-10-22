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
from backend.app.schemas.user import UserOut

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

    def _validate_manager_site_access(self, user: UserOut, site_id: Optional[str], action_desc: str = "perform this action") -> None:
        if user.role != "Manager":
            return
        from backend.app.config import settings
        if not user.assigned_sites:
            if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unscoped Manager cannot {action_desc}. Explicit site assignment required.",
                )
        elif site_id and site_id not in user.assigned_sites:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Manager is not authorized for site '{site_id}' to {action_desc}. Authorized sites: {user.assigned_sites}",
            )

    async def create_motor(self, data: MotorCreate, username: Union[str, UserOut]) -> MotorOut:
        """Register a new industrial motor asset."""
        user_name = username.username if isinstance(username, UserOut) else str(username)
        if isinstance(username, UserOut):
            if username.role == "Technician":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Technicians are not permitted to register motor assets",
                )
            if username.role == "Manager":
                self._validate_manager_site_access(username, data.site_id, "register motors")

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
        doc["created_by"] = user_name

        await self.collection.insert_one(doc)
        await self._audit("CREATE_MOTOR", user_name, data.motor_id, {
            "name": data.name,
            "type": data.motor_type,
            "device": data.assigned_device_id,
            "site": data.site_id,
        })

        logger.info("Created motor '%s' (%s) by '%s'", data.motor_id, data.name, user_name)
        return MotorOut(**doc)

    async def get_effective_thresholds(self, motor_doc: Union[dict, str, None] = None) -> dict:
        """
        Resolves operational thresholds in priority order via canonical ThresholdResolver:
        1. Explicit motor-specific overrides in motor_doc.
        2. Gateway operational limits saved in 'system_settings' collection.
        3. Built-in defaults.
        """
        from backend.app.services.threshold_service import ThresholdResolver
        return await ThresholdResolver.resolve(self.db, motor_doc)

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
            if effective_thresholds is None:
                effective_thresholds = await self.get_effective_thresholds(motor_doc)
            sensors = last_telem.get("sensors", {})
            sensor_status = last_telem.get("sensor_status", {})
            inf = last_telem.get("inference", {})
            temp = sensors.get("temperature_c")
            curr = sensors.get("current_a")
            vib = sensors.get("vibration_g_rms")
            vib_peak = (
                sensors.get("vibration_g_peak")
                or sensors.get("vibration_peak_g")
                or sensors.get("peak_shock_g")
            )

            # 1. Check for disconnected or out-of-range sensors
            if (
                sensor_status.get("current") in ("DISCONNECTED", "UNAVAILABLE", "OUT_OF_RANGE")
                or sensor_status.get("vibration") in ("DISCONNECTED", "UNAVAILABLE", "OUT_OF_RANGE")
            ):
                return "critical"
            if sensor_status.get("temperature") in ("DISCONNECTED", "UNAVAILABLE", "OUT_OF_RANGE"):
                return "warning"

            # 2. Check if all sensor readings are missing / null
            if temp is None and curr is None and vib is None and vib_peak is None:
                return "unknown"

            peak_crit = effective_thresholds.get("peak_vibration_critical_g", 0.800)
            peak_warn = effective_thresholds.get("peak_vibration_g", 0.350)

            # 3. Check physical threshold violations (>= for warning/critical equality)
            if (
                (temp is not None and temp >= effective_thresholds["temperature_critical_c"])
                or (curr is not None and curr >= effective_thresholds["current_critical_a"])
                or (vib is not None and vib >= effective_thresholds["vibration_critical_g"])
                or (vib_peak is not None and peak_crit is not None and vib_peak >= peak_crit)
            ):
                return "critical"

            if (
                (temp is not None and temp >= effective_thresholds["temperature_warning_c"])
                or (curr is not None and curr >= effective_thresholds["current_warning_a"])
                or (vib is not None and vib >= effective_thresholds["vibration_warning_g"])
                or (vib_peak is not None and peak_warn is not None and vib_peak >= peak_warn)
            ):
                return "warning"

            # 4. Freshness Gate: Stale or offline telemetry is NEVER classified as healthy.
            freshness = self._telemetry_freshness(last_telem, effective_thresholds)
            if freshness != "fresh":
                return "unknown"

            if inf.get("health_status") in ("healthy", "warning", "critical"):
                return inf["health_status"]

            return "healthy"

        return motor_doc.get("health_status", "unknown")

    @staticmethod
    def _telemetry_freshness(telemetry: Any, thresholds: Optional[dict] = None) -> str:
        """Classify receipt freshness using server time, never the device timestamp."""
        if not isinstance(telemetry, dict):
            return "unknown"
        if telemetry.get("liveness_eligible") is False:
            return "unknown"
        received_at = telemetry.get("server_received_at")
        if isinstance(received_at, str):
            try:
                received_at = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
            except ValueError:
                return "unknown"
        if not isinstance(received_at, datetime):
            return "unknown"
        if received_at.tzinfo is None:
            return "unknown"

        age_sec = (datetime.now(timezone.utc) - received_at.astimezone(timezone.utc)).total_seconds()
        if age_sec < 0:
            return "unknown"
        limits = thresholds or {}
        stale_after = float(limits.get("stale_timeout_sec", 15))
        offline_after = float(limits.get("offline_timeout_sec", 35))
        if age_sec > offline_after:
            return "offline"
        if age_sec > stale_after:
            return "stale"
        return "fresh"

    def _operational_state_for_telemetry(self, last_telem: Optional[dict], thresholds: dict, motor_doc: dict) -> str:
        if not last_telem:
            return "OFFLINE"
        freshness = self._telemetry_freshness(last_telem, thresholds)
        if freshness == "fresh":
            return "RUNNING" if motor_doc.get("status") == "active" else "IDLE"
        if freshness == "stale":
            return "STALE"
        if freshness == "offline":
            return "OFFLINE"
        return "UNKNOWN"

    async def get_motor(self, motor_id: str, current_user: Optional[UserOut] = None) -> Optional[MotorOut]:
        """Retrieve single motor asset by ID with live telemetry state and object-level scoping."""
        doc = await self.collection.find_one({"motor_id": motor_id}, {"_id": 0})
        if not doc:
            return None

        # Object-level authorization check
        if current_user is not None:
            if current_user.role == "Manager":
                from backend.app.config import settings
                if not current_user.assigned_sites and (settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False)):
                    return None
                if current_user.assigned_sites and doc.get("site_id") not in current_user.assigned_sites:
                    return None
                if current_user.assigned_motors and motor_id not in current_user.assigned_motors:
                    return None
            elif current_user.role == "Technician":
                is_assigned = motor_id in (current_user.assigned_motors or [])
                if not is_assigned and self.db is not None:
                    wo = await self.db["work_orders"].find_one({
                        "motor_id": motor_id,
                        "assigned_to_user_id": current_user.username,
                    })
                    if wo:
                        is_assigned = True
                if not is_assigned:
                    return None

        # Enhance with live telemetry state and effective thresholds
        last_telem = await self.telemetry_collection.find_one(
            {"motor_id": motor_id, "liveness_eligible": {"$ne": False}},
            {"_id": 0},
            sort=[("server_received_at", -1)],
        )
        thresholds = await self.get_effective_thresholds(doc)
        doc["effective_thresholds"] = thresholds
        doc["health_status"] = await self.calculate_motor_health(motor_id, doc, last_telem, thresholds)
        doc["operational_state"] = self._operational_state_for_telemetry(last_telem, thresholds, doc)

        return MotorOut(**self._normalize_doc(doc))

    async def list_motors(self, site_id: Optional[str] = None, current_user: Optional[UserOut] = None) -> List[MotorOut]:
        """List registered motor assets with role-based and object-level isolation."""
        query: Dict[str, Any] = {}
        if site_id:
            query["site_id"] = site_id

        if current_user is not None:
            if current_user.role == "Manager":
                from backend.app.config import settings
                if not current_user.assigned_sites:
                    if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                        return []
                else:
                    if site_id:
                        if site_id not in current_user.assigned_sites:
                            return []
                    else:
                        query["site_id"] = {"$in": current_user.assigned_sites}
                if current_user.assigned_motors:
                    query["motor_id"] = {"$in": current_user.assigned_motors}
            elif current_user.role == "Technician":
                tech_motors = set(current_user.assigned_motors or [])
                if self.db is not None:
                    cursor_wo = self.db["work_orders"].find({"assigned_to_user_id": current_user.username})
                    async for wo in cursor_wo:
                        if "motor_id" in wo:
                            tech_motors.add(wo["motor_id"])
                if not tech_motors:
                    return []
                query["motor_id"] = {"$in": list(tech_motors)}

        cursor = self.collection.find(query, {"_id": 0})
        docs = await cursor.to_list(length=200)

        results = []
        for d in docs:
            # Sync health state with latest telemetry and effective thresholds
            last_telem = await self.telemetry_collection.find_one(
                {"motor_id": d["motor_id"], "liveness_eligible": {"$ne": False}},
                {"_id": 0},
                sort=[("server_received_at", -1)],
            )
            m_eff = await self.get_effective_thresholds(d)
            d["effective_thresholds"] = m_eff
            d["health_status"] = await self.calculate_motor_health(d["motor_id"], d, last_telem, m_eff)
            d["operational_state"] = self._operational_state_for_telemetry(last_telem, m_eff, d)

            results.append(MotorOut(**self._normalize_doc(d)))

        return results

    async def update_motor_config(self, motor_id: str, data: MotorUpdate, username: Union[str, UserOut]) -> MotorOut:
        """Update motor parameters, thresholds, and device associations with RBAC scoping."""
        user_name = username.username if isinstance(username, UserOut) else str(username)
        if isinstance(username, UserOut):
            if username.role == "Technician":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Technicians are not permitted to modify motor configurations",
                )

        existing = await self.collection.find_one({"motor_id": motor_id})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found")

        if isinstance(username, UserOut) and username.role == "Manager":
            self._validate_manager_site_access(username, existing.get("site_id"), f"modify motor '{motor_id}'")
            if data.site_id:
                self._validate_manager_site_access(username, data.site_id, f"reassign motor to site '{data.site_id}'")

        now = datetime.now(timezone.utc)
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        if "thresholds" in update_dict and isinstance(update_dict["thresholds"], dict):
            update_dict["thresholds"]["has_custom_thresholds"] = True

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
        await self._audit("UPDATE_CONFIG", user_name, motor_id, {
            "version": new_version,
            "fields": list(update_dict.keys()),
        })

        logger.info("Updated motor config for '%s' to version %d by '%s'", motor_id, new_version, user_name)
        updated_doc = await self.collection.find_one({"motor_id": motor_id}, {"_id": 0})
        return MotorOut(**self._normalize_doc(updated_doc))

    async def disable_motor(self, motor_id: str, username: Union[str, UserOut]) -> MotorOut:
        """Mark motor inactive and disable real-time dispatch with RBAC validation."""
        user_name = username.username if isinstance(username, UserOut) else str(username)
        if isinstance(username, UserOut):
            if username.role == "Technician":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Technicians are not permitted to deactivate motors",
                )

        existing = await self.collection.find_one({"motor_id": motor_id})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found")

        if isinstance(username, UserOut) and username.role == "Manager":
            self._validate_manager_site_access(username, existing.get("site_id"), f"deactivate motor '{motor_id}'")

        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"motor_id": motor_id},
            {"$set": {"status": "inactive", "operational_state": "OFFLINE", "updated_at": now}},
        )

        await self._audit("DISABLE_MOTOR", user_name, motor_id, {"previous_status": existing.get("status")})
        logger.info("Disabled motor '%s' by '%s'", motor_id, user_name)
        updated_doc = await self.collection.find_one({"motor_id": motor_id}, {"_id": 0})
        return MotorOut(**self._normalize_doc(updated_doc))

    async def get_audit_trail(self, limit: int = 50, current_user: Optional[UserOut] = None) -> List[dict]:
        """Fetch audit log events with role-based scoping."""
        query: Dict[str, Any] = {}
        if current_user is not None:
            if current_user.role == "Technician":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Technicians are not authorized to view audit trail",
                )
            if current_user.role == "Manager":
                from backend.app.config import settings
                if not current_user.assigned_sites:
                    if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                        return []
                else:
                    query["$or"] = [
                        {"details.site": {"$in": current_user.assigned_sites}},
                        {"details.site_id": {"$in": current_user.assigned_sites}},
                    ]

        cursor = self.audit_collection.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
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
