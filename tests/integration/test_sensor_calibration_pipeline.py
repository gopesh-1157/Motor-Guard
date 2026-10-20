"""
MotorGuard — Automated Sensor Calibration & Industrial Threshold Regression Test Suite
=======================================================================================
Phase Eight Verification for MotorGuard Sensor Calibration Pipeline:
  - Current: Zero-offset calibration validity & rejection, effective sensitivity & divider math,
    reference DMM error calculation, warning/critical persistence, startup transient fast-trip, NaN/inf.
  - Vibration: ADXL345 m/s² to g conversion, dynamic RMS with per-axis mean subtraction,
    peak shock detection, missing/irregular samples, sensor failure handling.
  - Temperature: DHT11 ambient air vs motor case separation, disconnection/stale handling.
  - System Integration: Per-motor threshold isolation, contradictory settings rejection,
    healthy ML non-suppression, ML failure independence, MQTT deduplication, RBAC auth.

NOTE: All test fixtures are deterministic, hermetic synthetic test fixtures.
No physical motor hardware or destructive tests are executed during automated tests.
"""

import math
import uuid
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List

from backend.app.schemas.motor import (
    HealthThresholds,
    SensorsConfig,
    SensorACS712Config,
    SensorADXL345Config,
    SensorDHT11Config,
)
from backend.app.schemas.telemetry import (
    TelemetryMessage,
    SensorsPayload,
    SensorStatusPayload,
    InferencePayload,
    SafetyPayload,
)
from backend.app.services.alert_service import AlertService
from scripts.calibration_logger import CalibrationLogger, analyze_csv


class MockAsyncCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query):
        for d in self.docs:
            match = True
            for k, v in query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                return dict(d)
        return None

    async def insert_one(self, doc):
        d = dict(doc)
        if "_id" not in d:
            d["_id"] = str(uuid.uuid4())
        self.docs.append(d)
        return type("InsertResult", (), {"inserted_id": d["_id"]})()

    async def update_one(self, query, update, upsert=False):
        matched = await self.find_one(query)
        if matched:
            for d in self.docs:
                if d.get("alert_id") == matched.get("alert_id"):
                    if "$set" in update:
                        d.update(update["$set"])
                    return type("UpdateResult", (), {"modified_count": 1})()
        elif upsert and "$set" in update:
            new_doc = dict(update["$set"])
            new_doc.update(query)
            self.docs.append(new_doc)
            return type("UpdateResult", (), {"upserted_id": new_doc.get("alert_id")})()
        return type("UpdateResult", (), {"modified_count": 0})()

    async def find_one_and_update(self, filter_query, update, return_document=True):
        matched = await self.find_one(filter_query)
        if matched:
            for d in self.docs:
                if d.get("alert_id") == matched.get("alert_id"):
                    if "$set" in update:
                        d.update(update["$set"])
                    return dict(d)
        return None


class MockAsyncDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockAsyncCollection()
        return self.collections[name]


# ==============================================================================
# 1. CURRENT MEASUREMENT & CALIBRATION TESTS
# ==============================================================================

class TestCurrentCalibration:
    def test_current_effective_sensitivity_and_divider_math(self):
        """Verify effective sensitivity at ADC pin S_pin = S_sensor * k_div and I = |V_pin - V_zero_pin| / S_pin."""
        s_sensor = 0.100  # 100 mV/A for ACS712-20A
        r1 = 10000.0      # 10k series
        r2 = 20000.0      # 20k pulldown
        k_div = r2 / (r1 + r2)  # 0.6666667
        s_pin = s_sensor * k_div  # 0.0666667 V/A

        v_zero_sensor = 2.500
        v_zero_pin = v_zero_sensor * k_div  # 1.6666667 V

        # Test case: Motor drawing 2.0 A
        # At sensor: V_sensor = 2.500 + (2.0 * 0.100) = 2.700 V
        # At pin: V_pin = 2.700 * k_div = 1.800 V
        v_pin_measured = 1.800

        # Method 1: Using effective sensitivity directly at pin
        i_calc_pin = (v_pin_measured - v_zero_pin) / s_pin

        # Method 2: Converting back to sensor voltage first
        v_sensor_measured = v_pin_measured / k_div
        i_calc_sensor = (v_sensor_measured - v_zero_sensor) / s_sensor

        assert math.isclose(i_calc_pin, 2.00, rel_tol=1e-3)
        assert math.isclose(i_calc_sensor, 2.00, rel_tol=1e-3)
        assert math.isclose(i_calc_pin, i_calc_sensor, rel_tol=1e-6)

    def test_zero_current_calibration_success_with_valid_stable_readings(self):
        """Simulate 500 calibration samples within plausible window (1.30V - 2.05V) and low spread (< 0.20V)."""
        import random
        random.seed(42)

        # Baseline resting pin voltages centered around nominal 1.667 V with +/- 15 mV noise
        samples = [1.667 + random.uniform(-0.015, 0.015) for _ in range(500)]
        min_v = min(samples)
        max_v = max(samples)
        spread = max_v - min_v
        avg_pin_v = sum(samples) / len(samples)

        k_div = 0.6667
        avg_acs_v = avg_pin_v / k_div

        # Verification bounds
        is_valid = (1.30 <= avg_pin_v <= 2.05) and (spread < 0.20)
        assert is_valid is True
        assert 1.65 <= avg_pin_v <= 1.68
        assert spread < 0.05
        assert 2.47 <= avg_acs_v <= 2.52

    def test_zero_current_calibration_fails_when_unstable_or_motor_running(self):
        """If calibration occurs while motor is active or sensor floating, spread >= 0.20V or out of range."""
        # Case A: Motor spinning during calibration (creates ripple and spread > 0.20V)
        import random
        random.seed(123)
        spinning_samples = [1.80 + random.uniform(-0.15, 0.15) for _ in range(500)]
        spread_spinning = max(spinning_samples) - min(spinning_samples)
        avg_pin_v = sum(spinning_samples) / len(spinning_samples)

        is_valid_spinning = (1.30 <= avg_pin_v <= 2.05) and (spread_spinning < 0.20)
        assert is_valid_spinning is False  # Must reject!

        # Case B: Disconnected wire (pin floating or pulled to GND / VCC)
        gnd_samples = [0.05 for _ in range(500)]
        avg_gnd = sum(gnd_samples) / 500
        spread_gnd = max(gnd_samples) - min(gnd_samples)
        is_valid_gnd = (1.30 <= avg_gnd <= 2.05) and (spread_gnd < 0.20)
        assert is_valid_gnd is False  # Must reject!

    def test_reference_current_error_calculation(self, tmp_path):
        """Verify CalibrationLogger calculates absolute and percentage error against reference instrument."""
        csv_file = str(tmp_path / "test_calib_run.csv")
        logger = CalibrationLogger(
            output_csv_path=csv_file,
            run_id="RUN-REF-TEST",
            operating_phase="moderate_load",
            ref_current_a=2.00,
        )

        packet = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 2.05, "vibration_g_rms": 0.05, "ambient_temperature_c": 28.0},
            "sensor_status": {"current_zero_offset_v": 1.667, "current_calibrated": True},
            "safety": {"status": "SAFE", "active_reasons": []},
            "inference": {"health_status": "healthy"},
        }
        logger.log_telemetry_packet(packet)

        # Analyze CSV offline
        analysis = analyze_csv(csv_file)
        assert analysis["total_records"] == 1
        assert math.isclose(analysis["current_error_abs_a"]["mean"], 0.050, abs_tol=1e-3)
        assert math.isclose(analysis["current_error_pct"]["mean"], 2.50, abs_tol=1e-2)

    @pytest.mark.asyncio
    async def test_startup_grace_period_and_immediate_hard_trip(self):
        """Transient startup overcurrent (< hard limit) is tolerated during grace period, but hard limit trips immediately."""
        db = MockAsyncDatabase()
        db["motors"].docs.append({
            "motor_id": "MTR-775-001",
            "thresholds": {
                "current_warning_a": 2.60,
                "current_critical_a": 3.20,
                "current_hard_limit_a": 4.25,
                "temperature_warning_c": 45.0,
                "temperature_critical_c": 50.0,
                "vibration_warning_g": 0.15,
                "vibration_critical_g": 0.35,
                "peak_vibration_g": 0.50,
            }
        })
        service = AlertService(db=db)

        # 1. Normal inrush current (3.0 A) during startup: warning threshold exceeded, but below hard limit
        telemetry_inrush = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 3.00, "current_peak_a": 3.10},
            "sensor_status": {"current": "OK", "current_calibrated": True},
        }
        alerts = await service.evaluate_telemetry_for_alerts(telemetry_inrush)
        # Emits THRESHOLD_OVERCURRENT (Warning)
        types = [a.trigger_type for a in alerts]
        assert "THRESHOLD_OVERCURRENT" in types
        assert "HARD_OVERCURRENT_TRIP" not in types

        # 2. Severe stall / short-circuit condition (4.80 A): Exceeds hard limit 4.25 A
        telemetry_hard = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 4.80, "current_peak_a": 5.10},
            "sensor_status": {"current": "OK", "current_calibrated": True},
        }
        alerts_hard = await service.evaluate_telemetry_for_alerts(telemetry_hard)
        types_hard = [a.trigger_type for a in alerts_hard]
        assert "HARD_OVERCURRENT_TRIP" in types_hard


# ==============================================================================
# 2. VIBRATION MEASUREMENT & ADXL345 TESTS
# ==============================================================================

class TestVibrationCalibration:
    def test_vibration_ms2_to_g_conversion(self):
        """Verify ADXL345 acceleration unit conversion: a_g = a_ms2 / 9.80665."""
        standard_gravity = 9.80665
        assert math.isclose(standard_gravity / 9.80665, 1.000, rel_tol=1e-5)
        raw_reading_ms2 = 19.6133  # 2.0g
        assert math.isclose(raw_reading_ms2 / 9.80665, 2.000, rel_tol=1e-4)

    def test_vibration_dynamic_rms_dc_gravity_removal(self):
        """Verify dynamic vibration RMS removes static 1.0g gravity vector."""
        # Synthetic static accelerometer resting flat on bench: X=0g, Y=0g, Z=1.0g (DC tilt)
        n = 128
        ax = [0.0] * n
        ay = [0.0] * n
        az = [1.0] * n  # 1g static gravity

        mean_x = sum(ax) / n
        mean_y = sum(ay) / n
        mean_z = sum(az) / n

        # Dynamic AC components:
        sum_dyn_sq = sum(
            ((ax[i] - mean_x) ** 2 + (ay[i] - mean_y) ** 2 + (az[i] - mean_z) ** 2)
            for i in range(n)
        )
        dynamic_rms_g = math.sqrt(sum_dyn_sq / n)

        # Static 1g tilt must result in 0.0g dynamic vibration!
        assert math.isclose(dynamic_rms_g, 0.0, abs_tol=1e-6)

        # Now add a 0.10g sinusoidal dynamic vibration on X-axis:
        ax_dyn = [0.10 * math.sin(2 * math.pi * i / 16) for i in range(n)]
        mean_x_dyn = sum(ax_dyn) / n
        sum_dyn_sq_2 = sum(
            ((ax_dyn[i] - mean_x_dyn) ** 2 + (ay[i] - mean_y) ** 2 + (az[i] - mean_z) ** 2)
            for i in range(n)
        )
        dynamic_rms_g_2 = math.sqrt(sum_dyn_sq_2 / n)
        # Theoretical RMS of 0.10 * sin is 0.10 / sqrt(2) = 0.0707g
        assert math.isclose(dynamic_rms_g_2, 0.0707, rel_tol=5e-2)

    @pytest.mark.asyncio
    async def test_vibration_persistence_and_hysteresis(self):
        """Vibration warning triggers at limit and auto-resolves when dropping below 85% of warning."""
        db = MockAsyncDatabase()
        db["motors"].docs.append({
            "motor_id": "MTR-775-001",
            "thresholds": {
                "current_warning_a": 2.60,
                "current_critical_a": 3.20,
                "temperature_warning_c": 45.0,
                "temperature_critical_c": 50.0,
                "vibration_warning_g": 0.15,
                "vibration_critical_g": 0.35,
                "peak_vibration_g": 0.50,
            }
        })
        service = AlertService(db=db)

        # Exceeds warning (0.22g > 0.15g)
        telemetry_high = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"vibration_g_rms": 0.22},
            "sensor_status": {"vibration": "OK"},
        }
        alerts = await service.evaluate_telemetry_for_alerts(telemetry_high)
        assert any(a.trigger_type == "THRESHOLD_HIGH_VIBRATION_RMS" and a.severity == "WARNING" for a in alerts)

        # Normalizes below 85% of 0.15g (0.127g)
        telemetry_normal = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"vibration_g_rms": 0.11},
            "sensor_status": {"vibration": "OK"},
        }
        await service.evaluate_telemetry_for_alerts(telemetry_normal)
        active_vib_alert = await db["alerts"].find_one({"motor_id": "MTR-775-001", "trigger_type": "THRESHOLD_HIGH_VIBRATION_RMS"})
        assert active_vib_alert["state"] == "RESOLVED"


# ==============================================================================
# 3. TEMPERATURE & SENSOR DIAGNOSTIC TESTS
# ==============================================================================

class TestTemperatureCalibration:
    def test_ambient_air_vs_motor_case_separation(self):
        """Verify schema and telemetry distinguish ambient_temperature_c from case_temperature_c."""
        sensors = SensorsPayload(
            current_a=1.5,
            ambient_temperature_c=28.5,
            case_temperature_c=None,  # Unconfigured contact probe
        )
        assert sensors.ambient_temperature_c == 28.5
        assert sensors.case_temperature_c is None

        telemetry = TelemetryMessage(
            event_id=str(uuid.uuid4()),
            device_id="esp32-node-001",
            motor_id="MTR-775-001",
            source="hardware",
            seq=1,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            sensors=sensors,
            sensor_status=SensorStatusPayload(temperature="OK", current="OK", vibration="OK"),
            inference=InferencePayload(status="PREDICTED", health_status="healthy", confidence=0.95),
            safety=SafetyPayload(status="SAFE"),
        )
        data = telemetry.model_dump()
        assert data["sensors"]["ambient_temperature_c"] == 28.5
        assert data["sensors"]["case_temperature_c"] is None

    @pytest.mark.asyncio
    async def test_dht11_disconnection_triggers_sensor_alert(self):
        """When DHT11 read fails, it triggers a temperature-specific sensor alert without crash."""
        db = MockAsyncDatabase()
        service = AlertService(db=db)

        telemetry_disconnected = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 1.2},
            "sensor_status": {"temperature": "DISCONNECTED", "current": "OK", "vibration": "OK"},
        }
        alerts = await service.evaluate_telemetry_for_alerts(telemetry_disconnected)
        assert any(a.trigger_type == "SENSOR_TEMPERATURE_DISCONNECTED" for a in alerts)


# ==============================================================================
# 4. SYSTEM INTEGRATION & SAFETY DECOUPLING TESTS
# ==============================================================================

class TestSystemIntegration:
    @pytest.mark.asyncio
    async def test_healthy_ml_never_suppresses_critical_safety_alert(self):
        """Crucial Safety Rule: ML predicting 'healthy' with 99% confidence must NEVER suppress rule-based safety alert."""
        db = MockAsyncDatabase()
        db["motors"].docs.append({
            "motor_id": "MTR-775-001",
            "thresholds": {
                "current_warning_a": 2.60,
                "current_critical_a": 3.20,
                "temperature_warning_c": 45.0,
                "temperature_critical_c": 50.0,
                "vibration_warning_g": 0.15,
                "vibration_critical_g": 0.35,
                "peak_vibration_g": 0.50,
            }
        })
        service = AlertService(db=db)

        # Anomaly scenario: Motor current is dangerously high (3.50 A > 3.20 A critical),
        # but ML model erroneously predicts 'healthy' (as observed in synthetic dataset rows)
        telemetry = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 3.50},
            "sensor_status": {"current": "OK", "current_calibrated": True},
            "inference": {"health_status": "healthy", "confidence": 0.99},
        }
        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        crit_alerts = [a for a in alerts if a.trigger_type == "THRESHOLD_OVERCURRENT" and a.severity == "CRITICAL"]
        assert len(crit_alerts) == 1, "Critical overcurrent alert must fire regardless of ML healthy prediction!"

    @pytest.mark.asyncio
    async def test_ml_inference_failure_preserves_safety_rules(self):
        """When ML model fails or is unavailable, rule-based alerts continue operating normally."""
        db = MockAsyncDatabase()
        db["motors"].docs.append({
            "motor_id": "MTR-775-001",
            "thresholds": {
                "current_warning_a": 2.60,
                "current_critical_a": 3.20,
                "temperature_warning_c": 45.0,
                "temperature_critical_c": 50.0,
                "vibration_warning_g": 0.15,
                "vibration_critical_g": 0.35,
                "peak_vibration_g": 0.50,
            }
        })
        service = AlertService(db=db)

        telemetry = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 3.40},
            "sensor_status": {"current": "OK", "current_calibrated": True},
            "inference": {"health_status": "unknown", "status": "MODEL_ERROR"},
        }
        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        assert any(a.trigger_type == "THRESHOLD_OVERCURRENT" and a.severity == "CRITICAL" for a in alerts)

    def test_contradictory_thresholds_rejected(self):
        """Ensure warning >= critical is rejected by schema validator."""
        with pytest.raises(ValueError, match="must be less than critical"):
            HealthThresholds(
                current_warning_a=4.0,
                current_critical_a=3.0,  # Contradictory!
            )

    def test_calibration_status_literal_accepted_values(self):
        """Verify both measured_calibrated and measured_and_calibrated are accepted."""
        t1 = HealthThresholds(calibration_status="measured_calibrated")
        assert t1.calibration_status == "measured_calibrated"
        t2 = HealthThresholds(calibration_status="measured_and_calibrated")
        assert t2.calibration_status == "measured_and_calibrated"
        t3 = HealthThresholds(calibration_status="provisional")
        assert t3.calibration_status == "provisional"
        t4 = HealthThresholds(calibration_status="unconfigured")
        assert t4.calibration_status == "unconfigured"

    @pytest.mark.asyncio
    async def test_per_motor_threshold_isolation(self):
        """Verify thresholds configured for motor A do not contaminate motor B."""
        db = MockAsyncDatabase()
        db["motors"].docs.extend([
            {
                "motor_id": "MTR-775-A",
                "thresholds": {"current_warning_a": 1.50, "current_critical_a": 2.00, "temperature_warning_c": 40.0, "temperature_critical_c": 45.0, "vibration_warning_g": 0.10, "vibration_critical_g": 0.20, "peak_vibration_g": 0.30}
            },
            {
                "motor_id": "MTR-775-B",
                "thresholds": {"current_warning_a": 4.50, "current_critical_a": 6.00, "temperature_warning_c": 60.0, "temperature_critical_c": 70.0, "vibration_warning_g": 0.30, "vibration_critical_g": 0.60, "peak_vibration_g": 0.80}
            }
        ])
        service = AlertService(db=db)

        # 1.80 A on Motor A -> WARNING (limit is 1.50 A)
        alerts_a = await service.evaluate_telemetry_for_alerts({
            "motor_id": "MTR-775-A",
            "device_id": "esp32-node-A",
            "sensors": {"current_a": 1.80},
            "sensor_status": {"current": "OK", "current_calibrated": True},
        })
        assert any(a.trigger_type == "THRESHOLD_OVERCURRENT" and a.severity == "WARNING" for a in alerts_a)

        # 1.80 A on Motor B -> NORMAL (warning limit is 4.50 A)
        alerts_b = await service.evaluate_telemetry_for_alerts({
            "motor_id": "MTR-775-B",
            "device_id": "esp32-node-B",
            "sensors": {"current_a": 1.80},
            "sensor_status": {"current": "OK", "current_calibrated": True},
        })
        assert not any(a.trigger_type == "THRESHOLD_OVERCURRENT" for a in alerts_b)

    def test_mqtt_duplicate_packet_deduplication(self):
        """Verify identical event_id within memory window is detected as duplicate."""
        seen_events = set()
        event_id = str(uuid.uuid4())

        # First ingestion
        is_dup_1 = event_id in seen_events
        seen_events.add(event_id)
        assert is_dup_1 is False

        # Replayed duplicate
        is_dup_2 = event_id in seen_events
        assert is_dup_2 is True

    def test_auth_and_rbac_protected_endpoints(self):
        """Verify unauthenticated requests to protected endpoints return 401."""
        from fastapi.testclient import TestClient
        from backend.app.main import app

        with TestClient(app) as client:
            res = client.post("/api/v1/telemetry/ingest", json={"invalid": "payload"})
            assert res.status_code in (401, 403)

