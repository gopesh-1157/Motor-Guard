"""
MotorGuard — ESP32 Device Registry & Assignment Service
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException, status

from backend.app.schemas.device import DeviceEnroll, DeviceOut, DeviceStatusOut
from backend.app.schemas.user import UserOut

logger = logging.getLogger("motorguard.device_service")


class DeviceService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["devices"]
        self.audit_collection = db["audit_events"]
        self.motors_collection = db["motors"]

    async def ensure_indexes(self) -> None:
        """Create indexes for device registry and query performance."""
        await self.collection.create_index("device_id", unique=True)
        await self.collection.create_index("assigned_motor_id")
        await self.audit_collection.create_index([("timestamp", -1)])
        logger.info("Devices collection indexes verified")

    async def _audit(self, action: str, user: str, target_id: str, details: Dict[str, Any]) -> None:
        """Record administrative action into immutable audit trail."""
        await self.audit_collection.insert_one({
            "event_id": str(uuid.uuid4()),
            "action": action,
            "user": user,
            "target_type": "device",
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

    async def enroll_device(self, data: DeviceEnroll, username: Union[str, UserOut]) -> DeviceOut:
        """Enroll a physical ESP32 node into the plant registry with RBAC scoping."""
        user_name = username.username if isinstance(username, UserOut) else str(username)
        if isinstance(username, UserOut):
            if username.role == "Technician":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Technicians are not permitted to enroll devices",
                )
            if username.role == "Manager":
                self._validate_manager_site_access(username, data.site_id, "enroll device")

        existing = await self.collection.find_one({"device_id": data.device_id})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device ID '{data.device_id}' is already registered in the registry",
            )

        now = datetime.now(timezone.utc)
        doc = {
            "device_id": data.device_id,
            "device_type": data.device_type,
            "board_variant": data.board_variant,
            "firmware_version": data.firmware_version,
            "site_id": data.site_id,
            "assigned_motor_id": data.assigned_motor_id,
            "mqtt_client_id": data.mqtt_client_id or f"client-{data.device_id}",
            "enrollment_status": "enrolled",
            "availability": "unknown",
            "last_seen": None,
            "configuration_version": 1,
            "created_at": now,
            "updated_at": now,
        }

        # If motor assignment requested on enrollment, verify motor exists and isn't assigned
        if data.assigned_motor_id:
            motor = await self.motors_collection.find_one({"motor_id": data.assigned_motor_id})
            if not motor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Motor '{data.assigned_motor_id}' not found",
                )
            if isinstance(username, UserOut) and username.role == "Manager":
                self._validate_manager_site_access(username, motor.get("site_id"), "assign device to motor")
            if motor.get("assigned_device_id") and motor.get("assigned_device_id") != data.device_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Motor '{data.assigned_motor_id}' is already assigned to device '{motor.get('assigned_device_id')}'",
                )
            await self.motors_collection.update_one(
                {"motor_id": data.assigned_motor_id},
                {"$set": {"assigned_device_id": data.device_id, "updated_at": now}},
            )

        await self.collection.insert_one(doc)
        await self._audit("ENROLL_DEVICE", user_name, data.device_id, {"board": data.board_variant, "motor": data.assigned_motor_id})
        logger.info("Enrolled ESP32 device '%s' (assigned to: %s) by '%s'", data.device_id, data.assigned_motor_id, user_name)
        return DeviceOut(**doc)

    async def list_devices(self, current_user: Optional[UserOut] = None) -> List[DeviceOut]:
        """List registered ESP32 edge nodes with role-based and site scoping."""
        query: Dict[str, Any] = {}
        if current_user is not None:
            if current_user.role == "Manager":
                from backend.app.config import settings
                if not current_user.assigned_sites:
                    if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                        return []
                else:
                    query["site_id"] = {"$in": current_user.assigned_sites}
            elif current_user.role == "Technician":
                tech_motors = set(current_user.assigned_motors or [])
                if self.db is not None:
                    cursor_wo = self.db["work_orders"].find({"assigned_to_user_id": current_user.username})
                    async for wo in cursor_wo:
                        if "motor_id" in wo:
                            tech_motors.add(wo["motor_id"])
                if not tech_motors:
                    return []
                query["assigned_motor_id"] = {"$in": list(tech_motors)}

        cursor = self.collection.find(query, {"_id": 0})
        devices = await cursor.to_list(length=200)
        return [DeviceOut(**d) for d in devices]

    async def get_device(self, device_id: str, current_user: Optional[UserOut] = None) -> Optional[DeviceOut]:
        """Retrieve single device by ID with scoping."""
        doc = await self.collection.find_one({"device_id": device_id}, {"_id": 0})
        if not doc:
            return None

        if current_user is not None:
            if current_user.role == "Manager":
                from backend.app.config import settings
                if not current_user.assigned_sites and (settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False)):
                    return None
                if current_user.assigned_sites and doc.get("site_id") not in current_user.assigned_sites:
                    return None
            elif current_user.role == "Technician":
                tech_motors = set(current_user.assigned_motors or [])
                if self.db is not None:
                    cursor_wo = self.db["work_orders"].find({"assigned_to_user_id": current_user.username})
                    async for wo in cursor_wo:
                        if "motor_id" in wo:
                            tech_motors.add(wo["motor_id"])
                if doc.get("assigned_motor_id") not in tech_motors:
                    return None

        return DeviceOut(**doc)

    async def assign_device(self, device_id: str, motor_id: str, username: Union[str, UserOut]) -> DeviceOut:
        """Assign an enrolled ESP32 device to a motor. Enforces 1-to-1 relationship and RBAC scoping."""
        user_name = username.username if isinstance(username, UserOut) else str(username)
        if isinstance(username, UserOut):
            if username.role == "Technician":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Technicians are not permitted to assign devices",
                )

        device = await self.collection.find_one({"device_id": device_id})
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")

        motor = await self.motors_collection.find_one({"motor_id": motor_id})
        if not motor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found")

        if isinstance(username, UserOut) and username.role == "Manager":
            self._validate_manager_site_access(username, device.get("site_id"), "assign device")
            self._validate_manager_site_access(username, motor.get("site_id"), "assign motor")

        # Conflict check 1: Device cannot be assigned to another motor
        if device.get("assigned_motor_id") and device.get("assigned_motor_id") != motor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device '{device_id}' is already assigned to motor '{device.get('assigned_motor_id')}'. Unassign first.",
            )

        # Conflict check 2: Motor cannot be assigned to another device
        if motor.get("assigned_device_id") and motor.get("assigned_device_id") != device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Motor '{motor_id}' is already assigned to device '{motor.get('assigned_device_id')}'. Unassign first.",
            )

        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"device_id": device_id},
            {"$set": {"assigned_motor_id": motor_id, "updated_at": now}},
        )
        await self.motors_collection.update_one(
            {"motor_id": motor_id},
            {"$set": {"assigned_device_id": device_id, "updated_at": now}},
        )

        await self._audit("ASSIGN_DEVICE", user_name, device_id, {"motor_id": motor_id})
        logger.info("Assigned device '%s' to motor '%s' by '%s'", device_id, motor_id, user_name)
        updated = await self.collection.find_one({"device_id": device_id}, {"_id": 0})
        return DeviceOut(**updated)

    async def unassign_device(self, device_id: str, username: Union[str, UserOut]) -> DeviceOut:
        """Safely unassign a device from its motor with RBAC validation."""
        user_name = username.username if isinstance(username, UserOut) else str(username)
        if isinstance(username, UserOut):
            if username.role == "Technician":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Technicians are not permitted to unassign devices",
                )

        device = await self.collection.find_one({"device_id": device_id})
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")

        if isinstance(username, UserOut) and username.role == "Manager":
            self._validate_manager_site_access(username, device.get("site_id"), "unassign device")

        current_motor = device.get("assigned_motor_id")
        now = datetime.now(timezone.utc)

        await self.collection.update_one(
            {"device_id": device_id},
            {"$set": {"assigned_motor_id": None, "updated_at": now}},
        )

        if current_motor:
            await self.motors_collection.update_one(
                {"motor_id": current_motor},
                {"$set": {"assigned_device_id": None, "updated_at": now}},
            )

        await self._audit("UNASSIGN_DEVICE", user_name, device_id, {"previous_motor": current_motor})
        logger.info("Unassigned device '%s' from motor '%s' by '%s'", device_id, current_motor, user_name)
        updated = await self.collection.find_one({"device_id": device_id}, {"_id": 0})
        return DeviceOut(**updated)

    async def record_heartbeat_or_telemetry(
        self, device_id: str, motor_id: str, update_liveness: bool = True
    ) -> bool:
        """
        Record that a device is active and receiving telemetry.
        Returns False if the device is unknown, not enrolled, or assigned to a different motor in the registry.
        If update_liveness is True, updates last_seen and availability.
        """
        device = await self.collection.find_one({"device_id": device_id})
        now = datetime.now(timezone.utc)

        if device:
            # Check enrollment status: must be active/enrolled, not pending or quarantined
            if device.get("enrollment_status") not in ["enrolled", "active"]:
                logger.warning(
                    "Rejected telemetry from unenrolled device '%s' (status: %s)",
                    device_id, device.get("enrollment_status")
                )
                return False

            assigned = device.get("assigned_motor_id")
            # If the device has an explicit motor assigned and incoming payload specifies a different motor, reject!
            if assigned and assigned != motor_id:
                logger.warning(
                    "Rejected telemetry assignment mismatch: device '%s' assigned to '%s', but payload claimed '%s'",
                    device_id, assigned, motor_id
                )
                return False

            if update_liveness:
                await self.collection.update_one(
                    {"device_id": device_id},
                    {"$set": {"last_seen": now, "availability": "online", "updated_at": now}},
                )
            return True
        else:
            # MG-F03: Do not automatically enroll unknown devices into active inventory.
            # Quarantine unknown device in pending status and reject its telemetry until approved by Admin/Manager.
            logger.warning(
                "Rejected telemetry from unknown device '%s' claiming motor '%s'. Quarantined as pending.",
                device_id, motor_id
            )
            await self.collection.insert_one({
                "device_id": device_id,
                "device_type": "ESP32",
                "board_variant": "Auto-Discovered",
                "firmware_version": "1.0.0",
                "site_id": "SITE-PLANT-A",
                "assigned_motor_id": None,
                "enrollment_status": "pending",
                "availability": "quarantined",
                "last_seen": now,
                "configuration_version": 1,
                "created_at": now,
                "updated_at": now,
            })
            return False

    async def get_device_status(self, device_id: str, current_user: Optional[UserOut] = None) -> DeviceStatusOut:
        """Return connectivity status, last telemetry, and freshness with RBAC scoping."""
        device = await self.collection.find_one({"device_id": device_id}, {"_id": 0})
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")

        if current_user is not None:
            if current_user.role == "Manager":
                from backend.app.config import settings
                if not current_user.assigned_sites and (settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False)):
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")
                if current_user.assigned_sites and device.get("site_id") not in current_user.assigned_sites:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")
            elif current_user.role == "Technician":
                tech_motors = set(current_user.assigned_motors or [])
                if self.db is not None:
                    cursor_wo = self.db["work_orders"].find({"assigned_to_user_id": current_user.username})
                    async for wo in cursor_wo:
                        if "motor_id" in wo:
                            tech_motors.add(wo["motor_id"])
                if device.get("assigned_motor_id") not in tech_motors:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")

        # Query latest telemetry
        telemetry_col = self.db["telemetry"]
        last_telem = await telemetry_col.find_one({"device_id": device_id}, {"_id": 0}, sort=[("timestamp", -1)])
        count = await telemetry_col.count_documents({"device_id": device_id})

        return DeviceStatusOut(
            device_id=device_id,
            availability=device.get("availability", "unknown"),
            last_seen=device.get("last_seen"),
            assigned_motor_id=device.get("assigned_motor_id"),
            telemetry_count=count,
            last_telemetry=last_telem,
        )

    async def seed_default_devices(self) -> None:
        """Seed baseline physical ESP32 and virtual nodes."""
        now = datetime.now(timezone.utc)
        defaults = [
            {
                "device_id": "esp32-node-001",
                "device_type": "ESP32",
                "board_variant": "ESP32-D0WD-V3",
                "firmware_version": "1.0.1-AP",
                "site_id": "SITE-PLANT-A",
                "assigned_motor_id": "MTR-775-001",
                "mqtt_client_id": "client-esp32-node-001",
                "enrollment_status": "enrolled",
                "availability": "online",
                "last_seen": now,
                "configuration_version": 1,
                "created_at": now,
                "updated_at": now,
            },
            {
                "device_id": "esp32-node-002",
                "device_type": "Virtual-ESP32",
                "board_variant": "ESP32-D0WD-V3",
                "firmware_version": "1.0.1-SIM",
                "site_id": "SITE-PLANT-A",
                "assigned_motor_id": "MTR-775-002",
                "mqtt_client_id": "client-esp32-node-002",
                "enrollment_status": "enrolled",
                "availability": "online",
                "last_seen": now,
                "configuration_version": 1,
                "created_at": now,
                "updated_at": now,
            },
            {
                "device_id": "esp32-node-003",
                "device_type": "Virtual-ESP32",
                "board_variant": "ESP32-D0WD-V3",
                "firmware_version": "1.0.1-SIM",
                "site_id": "SITE-PLANT-A",
                "assigned_motor_id": "MTR-775-003",
                "mqtt_client_id": "client-esp32-node-003",
                "enrollment_status": "enrolled",
                "availability": "online",
                "last_seen": now,
                "configuration_version": 1,
                "created_at": now,
                "updated_at": now,
            },
        ]

        for dev in defaults:
            await self.collection.update_one(
                {"device_id": dev["device_id"]},
                {"$setOnInsert": dev},
                upsert=True,
            )
        logger.info("Baseline ESP32 devices verified in registry")
