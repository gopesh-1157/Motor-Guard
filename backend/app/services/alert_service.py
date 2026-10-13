"""
MotorGuard — Automated Alert & Threshold Rules Engine

Evaluates ingested telemetry against physical threshold limits,
manages alert lifecycles (ACTIVE -> ACKNOWLEDGED -> RESOLVED),
and prevents alert fatigue through continuous state de-duplication.
"""

from datetime import datetime, timezone
import logging
import uuid
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.config import settings
from backend.app.schemas.alert import AlertOut, AlertState, AlertSeverity, AlertTriggerType

logger = logging.getLogger("motorguard.alert_service")


class AlertService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["alerts"]

    async def ensure_indexes(self) -> None:
        """Create indexes for alert lookups and state queries."""
        await self.collection.create_index([("alert_id", 1)], unique=True)
        await self.collection.create_index([("motor_id", 1), ("state", 1)])
        await self.collection.create_index([("severity", 1), ("state", 1)])
        await self.collection.create_index([("triggered_at", -1)])
        logger.info("Alerts collection indexes verified")

    async def evaluate_telemetry_for_alerts(self, telemetry: dict) -> List[AlertOut]:
        """
        Evaluate an ingested telemetry payload against threshold limits.
        Creates new ACTIVE alerts if violations exist and are not already active.
        """
        motor_id = telemetry.get("motor_id")
        device_id = telemetry.get("device_id")
        sensors = telemetry.get("sensors", {})
        inference = telemetry.get("inference", {})

        if not motor_id or not device_id:
            return []

        created_alerts: List[AlertOut] = []

        # 1. Overcurrent check
        current_a = sensors.get("current_a")
        if current_a is not None and current_a > settings.DEFAULT_OVERCURRENT_LIMIT_A:
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity="CRITICAL",
                trigger_type="THRESHOLD_OVERCURRENT",
                trigger_value=float(current_a),
                threshold_limit=float(settings.DEFAULT_OVERCURRENT_LIMIT_A),
                unit="A",
                message=f"Overcurrent trip limit exceeded on {motor_id}: measured {current_a:.2f} A (limit {settings.DEFAULT_OVERCURRENT_LIMIT_A:.1f} A)",
            )
            if alert:
                created_alerts.append(alert)

        # 2. Overtemperature check
        temp_c = sensors.get("temperature_c")
        if temp_c is not None and temp_c > settings.DEFAULT_MAX_TEMP_C:
            severity: AlertSeverity = "CRITICAL" if temp_c > 75.0 else "WARNING"
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity=severity,
                trigger_type="THRESHOLD_OVERTEMPERATURE",
                trigger_value=float(temp_c),
                threshold_limit=float(settings.DEFAULT_MAX_TEMP_C),
                unit="°C",
                message=f"Thermal limit exceeded on {motor_id}: measured {temp_c:.1f} °C (limit {settings.DEFAULT_MAX_TEMP_C:.1f} °C)",
            )
            if alert:
                created_alerts.append(alert)

        # 3. High Vibration check
        vib_g = sensors.get("vibration_g_rms")
        if vib_g is not None and vib_g > settings.DEFAULT_MAX_VIBRATION_G:
            severity = "CRITICAL" if vib_g > 0.8 else "WARNING"
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity=severity,
                trigger_type="THRESHOLD_HIGH_VIBRATION",
                trigger_value=float(vib_g),
                threshold_limit=float(settings.DEFAULT_MAX_VIBRATION_G),
                unit="g",
                message=f"Dynamic vibration RMS exceeded on {motor_id}: measured {vib_g:.3f} g (limit {settings.DEFAULT_MAX_VIBRATION_G:.3f} g)",
            )
            if alert:
                created_alerts.append(alert)

        # 4. TinyML Critical Inference check
        health_status = inference.get("health_status")
        confidence = inference.get("confidence", 0.0)
        if health_status == "critical":
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity="CRITICAL",
                trigger_type="CRITICAL_INFERENCE_FAULT",
                trigger_value=float(confidence),
                threshold_limit=0.5,
                unit="confidence",
                message=f"Edge TinyML model diagnosed CRITICAL motor health for {motor_id} (confidence: {confidence:.1%})",
            )
            if alert:
                created_alerts.append(alert)

        return created_alerts

    async def _trigger_or_update_alert(
        self,
        motor_id: str,
        device_id: str,
        severity: AlertSeverity,
        trigger_type: AlertTriggerType,
        trigger_value: float,
        threshold_limit: float,
        unit: str,
        message: str,
    ) -> Optional[AlertOut]:
        """Insert a new alert if no ACTIVE alert exists for (motor_id, trigger_type)."""
        existing = await self.collection.find_one({
            "motor_id": motor_id,
            "trigger_type": trigger_type,
            "state": "ACTIVE",
        })

        if existing:
            # Update latest reading without duplicating alert record
            await self.collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {"trigger_value": trigger_value}}
            )
            return None

        now = datetime.now(timezone.utc)
        alert_id = f"ALT-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        doc = {
            "alert_id": alert_id,
            "motor_id": motor_id,
            "device_id": device_id,
            "severity": severity,
            "trigger_type": trigger_type,
            "trigger_value": trigger_value,
            "threshold_limit": threshold_limit,
            "unit": unit,
            "message": message,
            "state": "ACTIVE",
            "triggered_at": now,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "resolved_at": None,
            "resolved_by": None,
            "resolution_notes": None,
        }

        result = await self.collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        logger.warning("Active alert triggered: [%s] %s on %s", severity, trigger_type, motor_id)
        return AlertOut(**doc)

    async def list_alerts(
        self,
        motor_id: Optional[str] = None,
        state: Optional[AlertState] = None,
        severity: Optional[AlertSeverity] = None,
        limit: int = 50,
    ) -> List[AlertOut]:
        """Query alert records with optional filters."""
        query: dict = {}
        if motor_id:
            query["motor_id"] = motor_id
        if state:
            query["state"] = state
        if severity:
            query["severity"] = severity

        cursor = self.collection.find(query).sort("triggered_at", -1).limit(limit)
        alerts: List[AlertOut] = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id", ""))
            alerts.append(AlertOut(**doc))
        return alerts

    async def get_alert(self, alert_id: str) -> Optional[AlertOut]:
        """Fetch alert by alert_id."""
        doc = await self.collection.find_one({"alert_id": alert_id})
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id", ""))
        return AlertOut(**doc)

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> Optional[AlertOut]:
        """Transition alert to ACKNOWLEDGED state."""
        now = datetime.now(timezone.utc)
        result = await self.collection.find_one_and_update(
            {"alert_id": alert_id, "state": "ACTIVE"},
            {
                "$set": {
                    "state": "ACKNOWLEDGED",
                    "acknowledged_at": now,
                    "acknowledged_by": acknowledged_by,
                }
            },
            return_document=True,
        )
        if not result:
            return None
        result["id"] = str(result.pop("_id", ""))
        logger.info("Alert %s acknowledged by %s", alert_id, acknowledged_by)
        return AlertOut(**result)

    async def assign_alert(
        self,
        alert_id: str,
        assigned_to: str,
        assigned_by: str,
        priority: str = "URGENT",
        instructions: Optional[str] = None,
    ) -> Optional[AlertOut]:
        """Manager assigns an active/critical alert to a technician."""
        now = datetime.now(timezone.utc)
        result = await self.collection.find_one_and_update(
            {"alert_id": alert_id},
            {
                "$set": {
                    "assigned_to": assigned_to,
                    "assigned_by": assigned_by,
                    "assigned_at": now,
                    "priority": priority,
                    "instructions": instructions,
                    "state": "ACKNOWLEDGED",
                    "acknowledged_at": now,
                    "acknowledged_by": assigned_by,
                }
            },
            return_document=True,
        )
        if not result:
            return None
        result["id"] = str(result.pop("_id", ""))
        logger.info("Alert %s assigned to %s by %s [Priority: %s]", alert_id, assigned_to, assigned_by, priority)
        return AlertOut(**result)

    async def resolve_alert(
        self, alert_id: str, resolved_by: str, resolution_notes: str
    ) -> Optional[AlertOut]:
        """Transition alert to RESOLVED state with resolution notes."""
        now = datetime.now(timezone.utc)
        result = await self.collection.find_one_and_update(
            {"alert_id": alert_id, "state": {"$in": ["ACTIVE", "ACKNOWLEDGED"]}},
            {
                "$set": {
                    "state": "RESOLVED",
                    "resolved_at": now,
                    "resolved_by": resolved_by,
                    "resolution_notes": resolution_notes,
                }
            },
            return_document=True,
        )
        if not result:
            return None
        result["id"] = str(result.pop("_id", ""))
        logger.info("Alert %s resolved by %s: %s", alert_id, resolved_by, resolution_notes)
        return AlertOut(**result)

    async def reopen_alert(
        self, alert_id: str, reopened_by: str, reason: str = "Recurrence detected or investigation incomplete"
    ) -> Optional[AlertOut]:
        """Transition alert back to ACTIVE state."""
        now = datetime.now(timezone.utc)
        result = await self.collection.find_one_and_update(
            {"alert_id": alert_id, "state": "RESOLVED"},
            {
                "$set": {
                    "state": "ACTIVE",
                    "reopened_at": now,
                    "reopened_by": reopened_by,
                    "reopen_reason": reason,
                }
            },
            return_document=True,
        )
        if not result:
            return None
        result["id"] = str(result.pop("_id", ""))
        logger.info("Alert %s reopened by %s: %s", alert_id, reopened_by, reason)
        return AlertOut(**result)

