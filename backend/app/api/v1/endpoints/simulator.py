"""
MotorGuard — Edge Virtual Motor Simulator REST API

Provides deterministic simulation controls to inject warning/critical conditions,
sensor disconnection, or test sequences into the ingestion and rules pipeline.
Completely compliant with the v1.0.0 Telemetry Contract Specification.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from backend.app.db.mongodb import db_manager
from backend.app.schemas.telemetry import TelemetryMessage
from backend.app.schemas.user import UserOut
from backend.app.core.auth import get_current_active_user, require_roles
from backend.app.services.telemetry_ingestion import TelemetryIngestionService
from backend.app.services.alert_service import AlertService
from backend.app.api.v1.endpoints.websocket import ws_manager
from backend.app.mqtt.subscriber import mqtt_subscriber

logger = logging.getLogger("motorguard.simulator_api")
router = APIRouter()

# Global sequence counter and state
_simulator_seq = 1000
_active_profile = "healthy"


class SimulatorInjectRequest(BaseModel):
    motor_id: str = Field(default="MTR-775-002", description="Target motor ID")
    device_id: str = Field(default="sim-node-002", description="Assigned virtual device ID")
    condition: Literal[
        "healthy",
        "warning_temp",
        "critical_vib",
        "overload_current",
        "sensor_disconnected",
    ] = Field(default="healthy", description="Simulation condition profile")
    custom_temp: Optional[float] = Field(default=None, description="Override temperature in °C")
    custom_current: Optional[float] = Field(default=None, description="Override current in A")
    custom_vibration: Optional[float] = Field(default=None, description="Override vibration RMS in g")


class SimulatorStatusResponse(BaseModel):
    active_profile: str
    available_profiles: List[str]
    virtual_devices: List[Dict[str, str]]
    telemetry_schema_version: str


@router.get("/status", response_model=SimulatorStatusResponse)
async def get_simulator_status(
    current_user: UserOut = Depends(get_current_active_user),
):

    """Return current simulator configuration and available fault injection profiles."""
    return SimulatorStatusResponse(
        active_profile=_active_profile,
        available_profiles=[
            "healthy",
            "warning_temp",
            "critical_vib",
            "overload_current",
            "sensor_disconnected",
        ],
        virtual_devices=[
            {"motor_id": "MTR-775-001", "device_id": "sim-node-001", "profile": "healthy"},
            {"motor_id": "MTR-775-002", "device_id": "sim-node-002", "profile": "warning_temp"},
            {"motor_id": "MTR-775-003", "device_id": "sim-node-003", "profile": "critical_vib"},
        ],
        telemetry_schema_version="1.0.0",
    )


async def _process_and_broadcast_payload(payload: dict) -> bool:
    """Ingest into MongoDB, evaluate safety alert rules, and broadcast to live WebSocket clients."""
    # 1. MongoDB Ingestion if database is available
    if db_manager.db is not None:
        try:
            ingestion_svc = TelemetryIngestionService(db_manager.db)
            await ingestion_svc.ingest(payload)
        except Exception as e:
            logger.warning("MongoDB ingestion error during simulation injection: %s", e)

        # 2. Safety rules evaluation
        try:
            alert_svc = AlertService(db_manager.db)
            alerts = await alert_svc.evaluate_telemetry_for_alerts(payload)
            for a in alerts:
                await ws_manager.broadcast({
                    "type": "alert",
                    "data": a.model_dump(mode="json"),
                })
        except Exception as e:
            logger.warning("Alert evaluation error during simulation injection: %s", e)

    # 3. Live WebSocket broadcast
    await ws_manager.broadcast({"type": "telemetry", "data": payload})

    # 4. MQTT Broker forward if connected
    if mqtt_subscriber.is_connected and mqtt_subscriber._client:
        try:
            import json
            topic = f"motorguard/v1/{payload.get('device_id')}/telemetry"
            mqtt_subscriber._client.publish(topic, json.dumps(payload), qos=1)
        except Exception as e:
            logger.debug("Could not publish simulated frame to MQTT: %s", e)

    return True


@router.post("/inject")
async def inject_fault_condition(
    req: SimulatorInjectRequest,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
):
    """
    Inject a simulated condition (healthy, warning, critical, or sensor fault)
    generating a compliant v1.0.0 telemetry packet through the pipeline.
    Requires Admin or Manager clearance.
    """
    global _simulator_seq, _active_profile
    _simulator_seq += 1
    _active_profile = req.condition

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    # Default profile values
    temp_val: Optional[float] = 38.5
    temp_stat = "OK"
    curr_val: Optional[float] = 2.15
    curr_stat = "OK"
    vib_val: Optional[float] = 0.082
    vib_stat = "OK"
    health_status = "healthy"
    probs = {"healthy": 0.95, "warning": 0.04, "critical": 0.01}
    confidence = 0.95

    if req.condition == "warning_temp":
        temp_val = 55.4
        curr_val = 3.25
        vib_val = 0.125
        health_status = "warning"
        probs = {"healthy": 0.08, "warning": 0.88, "critical": 0.04}
        confidence = 0.88
    elif req.condition == "critical_vib":
        temp_val = 46.2
        curr_val = 3.85
        vib_val = 0.895
        health_status = "critical"
        probs = {"healthy": 0.02, "warning": 0.08, "critical": 0.90}
        confidence = 0.90
    elif req.condition == "overload_current":
        temp_val = 62.0
        curr_val = 4.65
        vib_val = 0.350
        health_status = "critical"
        probs = {"healthy": 0.01, "warning": 0.09, "critical": 0.90}
        confidence = 0.90
    elif req.condition == "sensor_disconnected":
        temp_val = None
        temp_stat = "DISCONNECTED"
        curr_val = 2.10
        vib_val = 0.075
        health_status = "warning"
        probs = {"healthy": 0.30, "warning": 0.65, "critical": 0.05}
        confidence = 0.65

    # Apply any custom overrides
    if req.custom_temp is not None:
        temp_val = req.custom_temp
    if req.custom_current is not None:
        curr_val = req.custom_current
    if req.custom_vibration is not None:
        vib_val = req.custom_vibration

    # Re-evaluate health_status against effective operational thresholds if custom overrides provided
    if req.custom_temp is not None or req.custom_current is not None or req.custom_vibration is not None:
        from backend.app.db.mongodb import db_manager
        warn_temp = 50.0
        crit_temp = 65.0
        warn_curr = 3.5
        crit_curr = 4.0
        warn_vib = 0.20
        crit_vib = 0.80

        if db_manager.db is not None:
            try:
                sys_doc = await db_manager.db["system_settings"].find_one({"_id": "gateway_operational_limits"})
                if isinstance(sys_doc, dict):
                    warn_temp = float(sys_doc.get("temperature_warning_c", warn_temp))
                    crit_temp = float(sys_doc.get("temperature_critical_c", crit_temp))
                    warn_curr = float(sys_doc.get("current_warning_a", warn_curr))
                    crit_curr = float(sys_doc.get("current_critical_a", crit_curr))
                    warn_vib = float(sys_doc.get("vibration_warning_g", warn_vib))
                    crit_vib = float(sys_doc.get("vibration_critical_g", crit_vib))
            except Exception:
                pass

        # Deterministic Safety Rules Evaluation (Separated from ML inference)
        safety_reasons = []
        c_state = "NORMAL"
        v_state = "NORMAL"
        t_state = "NORMAL"

        if curr_val is not None and curr_val >= crit_curr:
            c_state = "CRITICAL"
            safety_reasons.append("CURRENT_CRITICAL_EXCEEDED")
        elif curr_val is not None and curr_val >= warn_curr:
            c_state = "WARNING"
            safety_reasons.append("CURRENT_WARNING_EXCEEDED")

        if vib_val is not None and vib_val >= crit_vib:
            v_state = "CRITICAL"
            safety_reasons.append("VIBRATION_CRITICAL_EXCEEDED")
        elif vib_val is not None and vib_val >= warn_vib:
            v_state = "WARNING"
            safety_reasons.append("VIBRATION_WARNING_EXCEEDED")

        if temp_val is None:
            t_state = "UNKNOWN"
            safety_reasons.append("TEMPERATURE_SENSOR_DISCONNECTED")
        elif temp_val >= crit_temp:
            t_state = "CRITICAL"
            safety_reasons.append("AMBIENT_TEMP_CRITICAL_EXCEEDED")
        elif temp_val >= warn_temp:
            t_state = "WARNING"
            safety_reasons.append("AMBIENT_TEMP_WARNING_EXCEEDED")

        if c_state == "CRITICAL" or v_state == "CRITICAL" or t_state == "CRITICAL":
            safety_status = "CRITICAL"
        elif c_state == "WARNING" or v_state == "WARNING" or t_state == "WARNING":
            safety_status = "WARNING"
        elif c_state == "UNKNOWN" or v_state == "UNKNOWN" or t_state == "UNKNOWN":
            safety_status = "UNKNOWN"
        else:
            safety_status = "SAFE"
    else:
        safety_status = "CRITICAL" if req.condition in ("critical_vib", "overload_current") else ("WARNING" if req.condition in ("warning_temp", "sensor_disconnected") else "SAFE")
        c_state = "CRITICAL" if req.condition == "overload_current" else "NORMAL"
        v_state = "CRITICAL" if req.condition == "critical_vib" else "NORMAL"
        t_state = "CRITICAL" if (temp_val and temp_val > 65.0) else ("UNKNOWN" if temp_val is None else "NORMAL")
        safety_reasons = [req.condition.upper() + "_TRIP"] if req.condition != "healthy" else []

    curr_peak = round(curr_val * 1.15, 2) if curr_val is not None else None
    vib_peak = round(vib_val * 1.8, 3) if vib_val is not None else None

    payload = {
        "schema_version": "1.0.0",
        "event_id": str(uuid.uuid4()),
        "device_id": req.device_id,
        "motor_id": req.motor_id,
        "source": "simulator",
        "seq": _simulator_seq,
        "timestamp": now_iso,
        "sensors": {
            "temperature_c": temp_val,
            "ambient_temperature_c": temp_val,
            "case_temperature_c": None,
            "current_a": curr_val,
            "current_peak_a": curr_peak,
            "vibration_g_rms": vib_val,
            "vibration_g_peak": vib_peak,
        },
        "sensor_status": {
            "temperature": temp_stat,
            "current": curr_stat,
            "vibration": vib_stat,
            "current_calibrated": True,
            "current_zero_offset_v": 2.500,
        },
        "inference": {
            "status": "PREDICTED",
            "health_status": health_status,
            "confidence": confidence,
            "probabilities": probs,
            "model_version": "ei-motoguard-v1.0.1",
            "input_feature_version": "1.0.0-3f",
            "inference_time_ms": 6,
        },
        "safety": {
            "status": safety_status,
            "current_state": c_state,
            "vibration_state": v_state,
            "temperature_state": t_state,
            "active_reasons": safety_reasons,
            "configuration_version": 1,
            "calibration_status": "provisional",
        },
        "diagnostics": {
            "wifi_rssi_dbm": -58,
            "free_heap_bytes": 182400,
            "uptime_seconds": _simulator_seq * 2,
        },
    }

    # Validate with Pydantic model
    validated = TelemetryMessage(**payload)
    validated_dict = validated.model_dump()

    await _process_and_broadcast_payload(validated_dict)

    return {
        "status": "success",
        "condition": req.condition,
        "motor_id": req.motor_id,
        "device_id": req.device_id,
        "event_id": validated_dict["event_id"],
        "health_status": health_status,
        "sensors": validated_dict["sensors"],
        "timestamp": now_iso,
    }
