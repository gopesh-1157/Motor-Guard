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
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.config import settings
from backend.app.schemas.alert import AlertOut, AlertState, AlertSeverity, AlertTriggerType
from backend.app.services.threshold_service import ThresholdResolver

logger = logging.getLogger("motorguard.alert_service")


class AlertService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["alerts"]
        self.users_collection = db["users"]
        self._recent_auto_resolved: List[AlertOut] = []

    async def ensure_indexes(self) -> None:
        """Create indexes for alert lookups and state queries."""
        await self.collection.create_index([("alert_id", 1)], unique=True)
        await self.collection.create_index([("motor_id", 1), ("state", 1)])
        await self.collection.create_index([("severity", 1), ("state", 1)])
        await self.collection.create_index([("triggered_at", -1)])
        logger.info("Alerts collection indexes verified")

    def consume_auto_resolved_alerts(self) -> List[AlertOut]:
        """Drain and return alerts that were auto-resolved during telemetry evaluation."""
        drained = list(self._recent_auto_resolved)
        self._recent_auto_resolved.clear()
        return drained

    async def _auto_resolve_if_active(
        self, motor_id: str, trigger_type: AlertTriggerType, notes: str
    ) -> Optional[AlertOut]:
        """Auto-resolve an ACTIVE alert when physical sensor readings return to a safe baseline."""
        now = datetime.now(timezone.utc)
        result = await self.collection.find_one_and_update(
            {"motor_id": motor_id, "trigger_type": trigger_type, "state": "ACTIVE"},
            {
                "$set": {
                    "state": "RESOLVED",
                    "resolved_at": now,
                    "resolved_by": "System (Auto-Normalized)",
                    "resolution_notes": notes,
                }
            },
            return_document=True,
        )
        if isinstance(result, dict) and result:
            result["id"] = str(result.pop("_id", ""))
            resolved_alert = AlertOut(**result)
            self._recent_auto_resolved.append(resolved_alert)
            logger.info("Auto-normalized active alert for %s [%s]: %s", motor_id, trigger_type, notes)
            return resolved_alert
        return None

    async def get_effective_thresholds(self, motor_id: Optional[str] = None) -> dict:
        """
        Resolves operational thresholds in priority order via canonical ThresholdResolver:
        1. Motor-specific thresholds in 'motors' collection (if configured).
        2. Gateway operational limits saved in 'system_settings' collection.
        3. Built-in configuration defaults in config.Settings.
        """
        return await ThresholdResolver.resolve(self.db, motor_id)

    async def evaluate_telemetry_for_alerts(self, telemetry: dict) -> List[AlertOut]:
        """
        Evaluate an ingested telemetry payload against threshold limits.
        Creates new ACTIVE alerts if violations exist and are not already active,
        and auto-normalizes active alerts once values safely drop below threshold.
        """
        motor_id = telemetry.get("motor_id")
        device_id = telemetry.get("device_id")
        sensors = telemetry.get("sensors", {})
        sensor_status = telemetry.get("sensor_status", {})
        inference = telemetry.get("inference", {})

        if not motor_id or not device_id:
            return []

        created_alerts: List[AlertOut] = []
        thresholds = await self.get_effective_thresholds(motor_id)
        calib_tag = f" [{thresholds.get('calibration_status', 'provisional').upper()}]"

        # 0. Sensor Availability & Diagnostics Evaluation
        t_stat = sensor_status.get("temperature")
        c_stat = sensor_status.get("current")
        v_stat = sensor_status.get("vibration")
        c_calibrated = sensor_status.get("current_calibrated")

        if t_stat in ("DISCONNECTED", "UNAVAILABLE", "OUT_OF_RANGE"):
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity="WARNING",
                trigger_type="SENSOR_TEMPERATURE_DISCONNECTED",
                trigger_value=0.0,
                threshold_limit=0.0,
                unit="status",
                message=f"DHT11 ambient air temperature sensor reported {t_stat} on {motor_id}",
            )
            if alert:
                created_alerts.append(alert)
        elif t_stat == "OK":
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="SENSOR_TEMPERATURE_DISCONNECTED",
                notes="Ambient temperature sensor communication normalized (OK)",
            )

        if c_stat in ("DISCONNECTED", "UNAVAILABLE", "OUT_OF_RANGE"):
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity="CRITICAL",
                trigger_type="SENSOR_CURRENT_DISCONNECTED",
                trigger_value=0.0,
                threshold_limit=0.0,
                unit="status",
                message=f"ACS712 armature current sensor reported {c_stat} (wire break / ADC error) on {motor_id}",
            )
            if alert:
                created_alerts.append(alert)
        elif c_stat == "OK":
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="SENSOR_CURRENT_DISCONNECTED",
                notes="Armature current sensor communication normalized (OK)",
            )

        if v_stat in ("DISCONNECTED", "UNAVAILABLE", "OUT_OF_RANGE"):
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity="CRITICAL",
                trigger_type="SENSOR_VIBRATION_DISCONNECTED",
                trigger_value=0.0,
                threshold_limit=0.0,
                unit="status",
                message=f"ADXL345 accelerometer reported {v_stat} on I2C bus for {motor_id}",
            )
            if alert:
                created_alerts.append(alert)
        elif v_stat == "OK":
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="SENSOR_VIBRATION_DISCONNECTED",
                notes="Accelerometer communication normalized (OK)",
            )

        if t_stat == "OK" and c_stat == "OK" and v_stat == "OK":
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="SENSOR_DISCONNECTED",
                notes="All physical sensor telemetry normalized (OK); auto-resolved legacy sensor fault alert",
            )

        if c_stat == "UNCALIBRATED" or c_calibrated is False:
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity="WARNING",
                trigger_type="SENSOR_UNCALIBRATED",
                trigger_value=0.0,
                threshold_limit=0.0,
                unit="status",
                message=f"ACS712 zero offset calibration unverified on {motor_id}; readings flagged UNCALIBRATED",
            )
            if alert:
                created_alerts.append(alert)
        elif c_calibrated is True:
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="SENSOR_UNCALIBRATED",
                notes="Current sensor zero-point verified and calibrated",
            )

        # 1. Immediate Hard Current Protection (Hardware rating ceiling)
        current_a = sensors.get("current_a")
        current_peak_a = sensors.get("current_peak_a")
        hard_limit = thresholds.get("current_hard_limit_a")
        peak_or_avg_current = max(current_a or 0.0, current_peak_a or 0.0)

        if hard_limit is not None and peak_or_avg_current >= hard_limit:
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity="CRITICAL",
                trigger_type="HARD_OVERCURRENT_TRIP",
                trigger_value=float(peak_or_avg_current),
                threshold_limit=float(hard_limit),
                unit="A",
                message=f"CRITICAL HARD CURRENT TRIP on {motor_id}: measured {peak_or_avg_current:.2f} A reached absolute ceiling ({hard_limit:.2f} A){calib_tag}",
            )
            if alert:
                created_alerts.append(alert)

        # 2. Overcurrent check (with 10% hysteresis normalization, >= for warning/critical equality)
        crit_curr = thresholds.get("current_critical_a", getattr(settings, "DEFAULT_OVERCURRENT_LIMIT_A", 4.0))
        warn_curr = thresholds.get("current_warning_a", crit_curr * 0.85)
        if current_a is not None and current_a >= warn_curr:
            curr_sev: AlertSeverity = "CRITICAL" if current_a >= crit_curr else "WARNING"
            curr_limit = float(crit_curr) if current_a >= crit_curr else float(warn_curr)
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity=curr_sev,
                trigger_type="THRESHOLD_OVERCURRENT",
                trigger_value=float(current_a),
                threshold_limit=curr_limit,
                unit="A",
                message=f"Overcurrent trip limit exceeded on {motor_id}: measured {current_a:.2f} A (limit {curr_limit:.1f} A){calib_tag}",
            )
            if alert:
                created_alerts.append(alert)
        elif current_a is not None and current_a <= (warn_curr * 0.90):
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="THRESHOLD_OVERCURRENT",
                notes=f"Armature current normalized to {current_a:.2f} A (below {warn_curr * 0.90:.2f} A)",
            )

        # 3. Overtemperature check (with 2.0°C hysteresis normalization, >= for warning/critical equality)
        temp_c = sensors.get("temperature_c") or sensors.get("ambient_temperature_c")
        warn_temp = thresholds.get("temperature_warning_c", getattr(settings, "DEFAULT_MAX_TEMP_C", 50.0))
        crit_temp = thresholds.get("temperature_critical_c", 75.0)
        if temp_c is not None and temp_c >= warn_temp:
            temp_sev: AlertSeverity = "CRITICAL" if temp_c >= crit_temp else "WARNING"
            temp_limit = float(crit_temp) if temp_c >= crit_temp else float(warn_temp)
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity=temp_sev,
                trigger_type="THRESHOLD_OVERTEMPERATURE",
                trigger_value=float(temp_c),
                threshold_limit=temp_limit,
                unit="°C",
                message=f"Thermal limit exceeded on {motor_id}: measured {temp_c:.1f} °C (limit {temp_limit:.1f} °C){calib_tag}",
            )
            if alert:
                created_alerts.append(alert)
        elif temp_c is not None and temp_c <= (warn_temp - 2.0):
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="THRESHOLD_OVERTEMPERATURE",
                notes=f"Temperature normalized to {temp_c:.1f} °C (below {warn_temp - 2.0:.1f} °C)",
            )

        # 4. RMS vibration and peak shock are independent measurements.  They must
        # retain distinct alert identities so one cannot overwrite or resolve the other.
        vib_g = sensors.get("vibration_g_rms")
        vib_peak = sensors.get("vibration_g_peak") or sensors.get("vibration_peak_g") or sensors.get("peak_shock_g")

        warn_vib = thresholds.get("vibration_warning_g", getattr(settings, "DEFAULT_MAX_VIBRATION_G", 0.100))
        crit_vib = thresholds.get("vibration_critical_g", 0.400)
        peak_vib_warn = thresholds.get("peak_vibration_g", getattr(settings, "DEFAULT_MAX_PEAK_VIBRATION_G", 0.350))
        peak_vib_crit = thresholds.get("peak_vibration_critical_g", 0.800)

        if vib_g is not None and vib_g >= warn_vib:
            rms_severity: AlertSeverity = "CRITICAL" if vib_g >= crit_vib else "WARNING"
            rms_limit = float(crit_vib) if vib_g >= crit_vib else float(warn_vib)
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity=rms_severity,
                trigger_type="THRESHOLD_HIGH_VIBRATION_RMS",
                trigger_value=float(vib_g),
                threshold_limit=rms_limit,
                unit="g RMS",
                message=f"Dynamic vibration RMS exceeded on {motor_id}: measured {vib_g:.3f} g (limit {rms_limit:.3f} g){calib_tag}",
            )
            if alert:
                created_alerts.append(alert)
        elif vib_g is not None and vib_g <= (warn_vib * 0.85):
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="THRESHOLD_HIGH_VIBRATION_RMS",
                notes=f"Dynamic vibration normalized to {vib_g:.3f} g (below {warn_vib * 0.85:.3f} g)",
            )
            # Backward-compatible recovery of legacy THRESHOLD_HIGH_VIBRATION if peak is also safe
            if vib_peak is None or vib_peak <= (peak_vib_warn * 0.85):
                await self._auto_resolve_if_active(
                    motor_id=motor_id,
                    trigger_type="THRESHOLD_HIGH_VIBRATION",
                    notes="Vibration levels normalized below hysteresis thresholds; auto-resolved legacy THRESHOLD_HIGH_VIBRATION alert",
                )

        if vib_peak is not None and vib_peak >= peak_vib_warn:
            peak_severity: AlertSeverity = "CRITICAL" if vib_peak >= peak_vib_crit else "WARNING"
            peak_limit = float(peak_vib_crit) if vib_peak >= peak_vib_crit else float(peak_vib_warn)
            alert = await self._trigger_or_update_alert(
                motor_id=motor_id,
                device_id=device_id,
                severity=peak_severity,
                trigger_type="THRESHOLD_HIGH_VIBRATION_PEAK",
                trigger_value=float(vib_peak),
                threshold_limit=peak_limit,
                unit="g pk",
                message=f"Peak instantaneous vibration shock exceeded on {motor_id}: measured {vib_peak:.3f} g pk (limit {peak_limit:.3f} g pk){calib_tag}",
            )
            if alert:
                created_alerts.append(alert)
        elif vib_peak is not None and vib_peak <= (peak_vib_warn * 0.85):
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="THRESHOLD_HIGH_VIBRATION_PEAK",
                notes=f"Peak vibration normalized to {vib_peak:.3f} g pk (below {peak_vib_warn * 0.85:.3f} g pk)",
            )

        # 5. TinyML Inference check (generates alerts for WARNING and CRITICAL, auto-resolves on healthy)
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
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="WARNING_INFERENCE_ANOMALY",
                notes=f"Escalated from WARNING to CRITICAL (confidence: {confidence:.1%})",
            )
        elif health_status == "warning":
            # Only trigger independent inference warning if no physical threshold alerts were triggered in this cycle
            has_physical_alert = any(
                a.trigger_type in ("THRESHOLD_OVERCURRENT", "THRESHOLD_OVERTEMPERATURE", "THRESHOLD_HIGH_VIBRATION_RMS", "THRESHOLD_HIGH_VIBRATION_PEAK", "HARD_OVERCURRENT_TRIP")
                for a in created_alerts
            )
            if not has_physical_alert:
                alert = await self._trigger_or_update_alert(
                    motor_id=motor_id,
                    device_id=device_id,
                    severity="WARNING",
                    trigger_type="WARNING_INFERENCE_ANOMALY",
                    trigger_value=float(confidence),
                    threshold_limit=0.5,
                    unit="confidence",
                    message=f"Edge TinyML model diagnosed WARNING motor anomaly for {motor_id} (confidence: {confidence:.1%})",
                )
                if alert:
                    created_alerts.append(alert)
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="CRITICAL_INFERENCE_FAULT",
                notes=f"De-escalated to WARNING (confidence: {confidence:.1%})",
            )
        elif health_status == "healthy":
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="CRITICAL_INFERENCE_FAULT",
                notes=f"Edge TinyML model status normalized to healthy (confidence: {confidence:.1%})",
            )
            await self._auto_resolve_if_active(
                motor_id=motor_id,
                trigger_type="WARNING_INFERENCE_ANOMALY",
                notes=f"Edge TinyML model status normalized to healthy (confidence: {confidence:.1%})",
            )

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
            # Never downgrade a critical active alert on a subsequent lower reading.
            updated_severity = "CRITICAL" if existing.get("severity") == "CRITICAL" else severity
            await self.collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "trigger_value": trigger_value,
                    "threshold_limit": threshold_limit,
                    "severity": updated_severity,
                    "unit": unit,
                    "message": message,
                }}
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
        """Manager or Admin assigns an active/critical alert to a verified technician."""
        # MG-F05: Validate that assigned technician exists, is active, and has Technician or Admin role
        assigned_user = await self.users_collection.find_one({"username": assigned_to})
        if not assigned_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Technician user '{assigned_to}' not found",
            )
        if not assigned_user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Technician user '{assigned_to}' is inactive",
            )
        if assigned_user.get("role") not in ["Technician", "Admin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{assigned_to}' has role '{assigned_user.get('role')}', but alert assignment requires Technician or Admin role",
            )

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

