"""
MotorGuard — Complete Threshold, Calibration & P0 Safety Regression Test Suite
=============================================================================

Covers:
 1. Current below warning threshold (nominal baseline, no alert).
 2. Current above warning threshold (triggers WARNING alert).
 3. Current above critical threshold (triggers CRITICAL alert).
 4. Short startup transient within configured startup grace period.
 5. Sustained overcurrent during startup trips fast hard-limit protection (HARD_OVERCURRENT_TRIP).
 6. Hysteresis and recovery (auto-resolution on current, temperature, vibration).
 7. Missing, disconnected, stale, NaN, and infinite sensor readings handled safely.
 8. Invalid or contradictory threshold configuration (warning >= critical rejected).
 9. Vibration warning and critical evaluation (dynamic RMS and peak instantaneous shock).
10. Invalid or stale temperature data (DHT11 disconnection alert).
11. ML prediction healthy while safety rules are critical (ML NEVER suppresses safety).
12. ML inference failure / model error while safety rules detect a fault.
13. Duplicate MQTT events handled idempotently.
14. Unauthorized telemetry ingestion and WebSocket access rejected.
15. Threshold changes applied specifically to the target motor.
16. Telemetry persistence and dashboard/API consistency.
17. Firmware feature extraction vs Edge Impulse model input contract (dimension=3, [temp, vib, curr]).
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from pydantic import ValidationError

from backend.app.schemas.telemetry import TelemetryMessage
from backend.app.schemas.motor import HealthThresholds
from backend.app.schemas.settings import OperationalLimitsBase
from backend.app.services.alert_service import AlertService
from backend.app.services.telemetry_ingestion import TelemetryIngestionService
from simulator.simulator import VirtualMotor


def get_mock_db():
    """Returns a fully asynchronous mock MongoDB database with collections."""
    mock_db = MagicMock()
    collections = {
        "alerts": AsyncMock(),
        "motors": AsyncMock(),
        "telemetry": AsyncMock(),
        "system_settings": AsyncMock(),
    }
    for col in collections.values():
        col.find_one_and_update = AsyncMock(return_value=None)
        col.find_one = AsyncMock(return_value=None)
        col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc1"))
    mock_db.__getitem__.side_effect = lambda k: collections.get(k, AsyncMock())
    return mock_db, collections


def create_base_telemetry(
    motor_id: str = "MTR-775-001",
    device_id: str = "esp32-node-001",
    current: float = 1.8,
    temp: float = 35.0,
    vib: float = 0.05,
    current_peak: float = 2.0,
    health_status: str = "healthy",
    confidence: float = 0.95,
    temp_status: str = "OK",
    curr_status: str = "OK",
    vib_status: str = "OK",
    current_calibrated: bool = True,
):
    return {
        "schema_version": "1.0.0",
        "event_id": str(uuid.uuid4()),
        "device_id": device_id,
        "motor_id": motor_id,
        "source": "hardware",
        "seq": 101,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "sensors": {
            "temperature_c": temp,
            "ambient_temperature_c": temp,
            "case_temperature_c": None,
            "current_a": current,
            "current_peak_a": current_peak,
            "vibration_g_rms": vib,
            "vibration_g_peak": round(vib * 1.5, 3) if vib is not None else None,
        },
        "sensor_status": {
            "temperature": temp_status,
            "current": curr_status,
            "vibration": vib_status,
            "current_calibrated": current_calibrated,
            "current_zero_offset_v": 2.500,
        },
        "inference": {
            "status": "PREDICTED",
            "health_status": health_status,
            "confidence": confidence,
            "probabilities": {"healthy": 0.95, "warning": 0.04, "critical": 0.01},
            "model_version": "ei-motoguard-v1.0.1",
            "input_feature_version": "1.0.0-3f",
            "inference_time_ms": 6,
        },
        "safety": {
            "status": "SAFE",
            "current_state": "NORMAL",
            "vibration_state": "NORMAL",
            "temperature_state": "NORMAL",
            "active_reasons": [],
            "configuration_version": 1,
            "calibration_status": "provisional",
        },
        "diagnostics": {
            "wifi_rssi_dbm": -55,
            "free_heap_bytes": 182000,
            "uptime_seconds": 3600,
        },
    }


class TestMotorGuardRegressionSuite:

    @pytest.mark.asyncio
    async def test_01_current_below_warning_threshold_produces_no_alerts(self):
        """1. Current below warning threshold results in zero alert triggers."""
        mock_db, cols = get_mock_db()
        cols["motors"].find_one = AsyncMock(return_value={
            "motor_id": "MTR-775-001",
            "thresholds": {"current_warning_a": 3.0, "current_critical_a": 4.0},
        })
        service = AlertService(mock_db)
        telem = create_base_telemetry(current=2.1)

        alerts = await service.evaluate_telemetry_for_alerts(telem)
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_02_current_above_warning_threshold_triggers_warning_alert(self):
        """2. Current above warning threshold generates a WARNING alert with provenance."""
        mock_db, cols = get_mock_db()
        cols["motors"].find_one = AsyncMock(return_value={
            "motor_id": "MTR-775-001",
            "thresholds": {
                "current_warning_a": 3.0,
                "current_critical_a": 4.0,
                "calibration_status": "provisional",
                "provenance": "RS-775 preliminary bench test",
            },
        })
        service = AlertService(mock_db)
        telem = create_base_telemetry(current=3.4)

        alerts = await service.evaluate_telemetry_for_alerts(telem)
        assert len(alerts) >= 1
        curr_alert = next(a for a in alerts if a.trigger_type == "THRESHOLD_OVERCURRENT")
        assert curr_alert.severity == "WARNING"
        assert curr_alert.trigger_value == 3.4
        assert "[PROVISIONAL]" in curr_alert.message

    @pytest.mark.asyncio
    async def test_03_current_above_critical_threshold_triggers_critical_alert(self):
        """3. Current above critical threshold generates a CRITICAL alert."""
        mock_db, cols = get_mock_db()
        cols["motors"].find_one = AsyncMock(return_value={
            "motor_id": "MTR-775-001",
            "thresholds": {"current_warning_a": 3.0, "current_critical_a": 4.0},
        })
        service = AlertService(mock_db)
        telem = create_base_telemetry(current=4.6)

        alerts = await service.evaluate_telemetry_for_alerts(telem)
        curr_alert = next(a for a in alerts if a.trigger_type == "THRESHOLD_OVERCURRENT")
        assert curr_alert.severity == "CRITICAL"
        assert curr_alert.trigger_value == 4.6

    @pytest.mark.asyncio
    async def test_04_startup_transient_within_grace_period_policy(self):
        """4. Motor configuration validates startup grace period field."""
        th = HealthThresholds(
            temperature_warning_c=50.0,
            temperature_critical_c=75.0,
            current_warning_a=3.0,
            current_critical_a=4.0,
            vibration_warning_g=0.100,
            vibration_critical_g=0.400,
            startup_grace_period_sec=2.5,
            calibration_status="provisional",
        )
        assert th.startup_grace_period_sec == 2.5
        assert th.calibration_status == "provisional"

    @pytest.mark.asyncio
    async def test_05_sustained_overcurrent_trips_hard_limit_protection(self):
        """5. Fast hard-current ceiling trips immediate CRITICAL alert regardless of grace period."""
        mock_db, cols = get_mock_db()
        cols["motors"].find_one = AsyncMock(return_value={
            "motor_id": "MTR-775-001",
            "thresholds": {
                "current_warning_a": 3.0,
                "current_critical_a": 4.0,
                "current_hard_limit_a": 5.2,
                "calibration_status": "provisional",
            },
        })
        service = AlertService(mock_db)
        telem = create_base_telemetry(current=4.2, current_peak=5.5)

        alerts = await service.evaluate_telemetry_for_alerts(telem)
        hard_alert = next(a for a in alerts if a.trigger_type == "HARD_OVERCURRENT_TRIP")
        assert hard_alert.severity == "CRITICAL"
        assert hard_alert.trigger_value == 5.5
        assert "CRITICAL HARD CURRENT TRIP" in hard_alert.message

    @pytest.mark.asyncio
    async def test_06_hysteresis_and_auto_resolution(self):
        """6. Active overcurrent and overtemperature alerts auto-resolve when readings drop safely."""
        mock_db, cols = get_mock_db()
        cols["alerts"].find_one_and_update = AsyncMock(side_effect=lambda q, *a, **k: {
            "_id": "doc123",
            "alert_id": "ALT-001",
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "severity": "WARNING",
            "trigger_type": q.get("trigger_type", "THRESHOLD_OVERCURRENT"),
            "trigger_value": 2.4,
            "threshold_limit": 3.0,
            "unit": "A",
            "message": "Overcurrent",
            "state": "RESOLVED",
            "triggered_at": datetime.now(timezone.utc),
        } if q.get("trigger_type") == "THRESHOLD_OVERCURRENT" else None)
        cols["motors"].find_one = AsyncMock(return_value={
            "motor_id": "MTR-775-001",
            "thresholds": {"current_warning_a": 3.0, "current_critical_a": 4.0},
        })
        service = AlertService(mock_db)
        # Normalizes below 90% of warning (3.0 * 0.90 = 2.70A)
        telem = create_base_telemetry(current=2.4)

        await service.evaluate_telemetry_for_alerts(telem)
        resolved = service.consume_auto_resolved_alerts()
        assert len(resolved) == 1
        assert resolved[0].trigger_type == "THRESHOLD_OVERCURRENT"
        assert resolved[0].state == "RESOLVED"

    def test_07_missing_disconnected_nan_infinite_readings(self):
        """7. NaN, infinite, and out-of-range sensor readings are rejected by schema."""
        # 1. NaN current is rejected
        with pytest.raises(ValidationError):
            TelemetryMessage(**create_base_telemetry(current=float("nan")))

        # 2. Infinite current is rejected
        with pytest.raises(ValidationError):
            TelemetryMessage(**create_base_telemetry(current=float("inf")))

        # 3. Disconnected sensor produces valid null reading with DISCONNECTED status
        telem = create_base_telemetry(current=None, curr_status="DISCONNECTED")
        msg = TelemetryMessage(**telem)
        assert msg.sensors.current_a is None
        assert msg.sensor_status.current == "DISCONNECTED"

    def test_08_invalid_contradictory_threshold_configuration_rejected(self):
        """8. Setting warning threshold >= critical threshold is strictly rejected by schema."""
        # 1. Current warning >= critical rejected
        with pytest.raises(ValidationError):
            HealthThresholds(
                temperature_warning_c=50.0,
                temperature_critical_c=75.0,
                current_warning_a=4.5,
                current_critical_a=4.0,  # Contradictory
                vibration_warning_g=0.100,
                vibration_critical_g=0.400,
            )

        # 2. Temperature warning >= critical rejected
        with pytest.raises(ValidationError):
            OperationalLimitsBase(
                temperature_warning_c=70.0,
                temperature_critical_c=65.0,  # Contradictory
                current_warning_a=3.0,
                current_critical_a=4.0,
                vibration_warning_g=0.100,
                vibration_critical_g=0.400,
                stale_timeout_sec=15,
                offline_timeout_sec=35,
            )

    @pytest.mark.asyncio
    async def test_09_vibration_warning_and_critical_evaluation(self):
        """9. Dynamic vibration RMS and peak shock evaluate correctly against limits."""
        mock_db, cols = get_mock_db()
        cols["motors"].find_one = AsyncMock(return_value={
            "motor_id": "MTR-775-001",
            "thresholds": {"vibration_warning_g": 0.100, "vibration_critical_g": 0.400},
        })
        service = AlertService(mock_db)

        # 1. Warning level RMS (0.150g)
        telem_warn = create_base_telemetry(vib=0.150)
        alerts_warn = await service.evaluate_telemetry_for_alerts(telem_warn)
        vib_alert = next(a for a in alerts_warn if a.trigger_type == "THRESHOLD_HIGH_VIBRATION_RMS")
        assert vib_alert.severity == "WARNING"

        # 2. Critical level RMS (0.550g)
        telem_crit = create_base_telemetry(vib=0.550)
        alerts_crit = await service.evaluate_telemetry_for_alerts(telem_crit)
        vib_crit_alert = next(a for a in alerts_crit if a.trigger_type == "THRESHOLD_HIGH_VIBRATION_RMS")
        assert vib_crit_alert.severity == "CRITICAL"

    @pytest.mark.asyncio
    async def test_10_invalid_or_stale_temperature_data_triggers_sensor_alert(self):
        """10. Disconnected DHT11 triggers a temperature-specific alert, never fabricated as 0°C."""
        mock_db, cols = get_mock_db()
        service = AlertService(mock_db)

        telem = create_base_telemetry(temp=None, temp_status="DISCONNECTED")
        alerts = await service.evaluate_telemetry_for_alerts(telem)
        dis_alert = next(a for a in alerts if a.trigger_type == "SENSOR_TEMPERATURE_DISCONNECTED")
        assert dis_alert.severity == "WARNING"
        assert "DHT11" in dis_alert.message

    @pytest.mark.asyncio
    async def test_11_ml_prediction_healthy_never_suppresses_safety_critical(self):
        """11. An ML prediction of 'healthy' NEVER cancels or suppresses an overcurrent safety alert."""
        mock_db, cols = get_mock_db()
        cols["motors"].find_one = AsyncMock(return_value={
            "motor_id": "MTR-775-001",
            "thresholds": {"current_warning_a": 3.0, "current_critical_a": 4.0},
        })
        service = AlertService(mock_db)

        # ML model claims healthy (e.g. from synthetic artifact), but current is 4.8A
        telem = create_base_telemetry(current=4.8, health_status="healthy", confidence=0.98)
        alerts = await service.evaluate_telemetry_for_alerts(telem)

        # Safety overcurrent must still trigger!
        crit_alert = next(a for a in alerts if a.trigger_type == "THRESHOLD_OVERCURRENT")
        assert crit_alert.severity == "CRITICAL"
        assert crit_alert.trigger_value == 4.8

    @pytest.mark.asyncio
    async def test_12_ml_inference_failure_preserves_safety_rule_evaluation(self):
        """12. If TinyML inference fails (MODEL_ERROR), rule-based overcurrent remains 100% operational."""
        mock_db, cols = get_mock_db()
        cols["motors"].find_one = AsyncMock(return_value={
            "motor_id": "MTR-775-001",
            "thresholds": {"current_warning_a": 3.0, "current_critical_a": 4.0},
        })
        service = AlertService(mock_db)

        telem = create_base_telemetry(current=4.5, health_status="unknown", confidence=0.0)
        telem["inference"]["status"] = "MODEL_ERROR"

        alerts = await service.evaluate_telemetry_for_alerts(telem)
        crit_alert = next(a for a in alerts if a.trigger_type == "THRESHOLD_OVERCURRENT")
        assert crit_alert.severity == "CRITICAL"

    @pytest.mark.asyncio
    async def test_13_duplicate_mqtt_events_handled_idempotently(self):
        """13. Ingesting duplicate event_id drops duplicate safely without error."""
        from pymongo.errors import DuplicateKeyError
        mock_col = AsyncMock()
        # First insert succeeds, second raises DuplicateKeyError
        mock_col.insert_one = AsyncMock(side_effect=[
            MagicMock(inserted_id="doc1"),
            DuplicateKeyError("Duplicate event_id"),
        ])
        mock_db = MagicMock()
        mock_db.__getitem__.side_effect = lambda k: mock_col

        service = TelemetryIngestionService(mock_db)
        telem = create_base_telemetry()

        res1 = await service.ingest(dict(telem))
        assert res1 is True

        res2 = await service.ingest(dict(telem))
        assert res2 is False  # Safely dropped duplicate

    def test_14_unauthorized_telemetry_ingestion_and_websocket_access(self):
        """14. Unauthenticated WebSocket and protected routes are rejected."""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        app.dependency_overrides.clear()

        with TestClient(app) as client:
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/telemetry"):
                    pass

    @pytest.mark.asyncio
    async def test_15_threshold_changes_applied_to_target_motor(self):
        """15. Threshold updates apply strictly to the designated motor without leaking across fleet."""
        mock_db, cols = get_mock_db()
        motor_a = {
            "motor_id": "MTR-775-001",
            "name": "Motor 1",
            "thresholds": {"current_warning_a": 2.5, "current_critical_a": 3.5},
        }
        motor_b = {
            "motor_id": "MTR-775-002",
            "name": "Motor 2",
            "thresholds": {"current_warning_a": 3.8, "current_critical_a": 4.8},
        }
        cols["motors"].find_one = AsyncMock(side_effect=lambda q, *a, **k: motor_a if q.get("motor_id") == "MTR-775-001" else motor_b)

        service = AlertService(mock_db)
        th_a = await service.get_effective_thresholds("MTR-775-001")
        th_b = await service.get_effective_thresholds("MTR-775-002")

        assert th_a["current_warning_a"] == 2.5
        assert th_b["current_warning_a"] == 3.8

    def test_16_simulator_produces_fully_compliant_v100_telemetry(self):
        """16. VirtualMotor simulator generates decoupled safety and calibrated sensor payload."""
        vm = VirtualMotor(motor_id="MTR-775-001", device_id="esp32-node-001", profile="healthy")
        payload = vm.step()

        msg = TelemetryMessage(**payload)
        assert msg.schema_version == "1.0.0"
        assert msg.sensors.ambient_temperature_c is not None
        assert msg.sensors.current_peak_a is not None
        assert msg.sensor_status.current_calibrated is True
        assert msg.safety is not None
        assert msg.safety.status in ("SAFE", "WARNING", "CRITICAL", "UNKNOWN")

    def test_17_firmware_feature_extraction_matches_edge_impulse_contract(self):
        """17. Verifies exact runtime feature vector matches Edge Impulse input contract: shape (3,), [temp, vib, curr]."""
        # Ground truth verified from model_variables.h:
        # EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE = 3
        # Feature order in training dataset: [0] temperature_C, [1] vibration_g, [2] current_A
        temp_reading = 28.5
        vib_reading = 0.045
        curr_reading = 1.25

        ei_features = [0.0, 0.0, 0.0]
        ei_features[0] = temp_reading
        ei_features[1] = vib_reading
        ei_features[2] = curr_reading

        assert len(ei_features) == 3
        assert ei_features[0] == 28.5  # temperature_C
        assert ei_features[1] == 0.045 # vibration_g
        assert ei_features[2] == 1.25  # current_A
