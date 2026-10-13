import uuid
import pytest
from pydantic import ValidationError
from backend.app.schemas.telemetry import TelemetryMessage


def test_valid_telemetry_payload():
    """Verify standard valid telemetry payload complies with contract."""
    payload = {
        "schema_version": "1.0.0",
        "event_id": str(uuid.uuid4()),
        "device_id": "ESP32-NODE-001",
        "motor_id": "MTR-775-001",
        "source": "hardware",
        "seq": 104,
        "timestamp": "2026-10-09T16:30:00.123Z",
        "sensors": {
            "temperature_c": 34.2,
            "current_a": 1.45,
            "vibration_g_rms": 0.42,
        },
        "sensor_status": {
            "temperature": "OK",
            "current": "OK",
            "vibration": "OK",
        },
        "inference": {
            "status": "PREDICTED",
            "health_status": "healthy",
            "confidence": 0.96,
            "probabilities": {
                "healthy": 0.96,
                "warning": 0.03,
                "critical": 0.01,
            },
            "model_version": "1.0.1",
            "inference_time_ms": 7,
        },
    }
    telemetry = TelemetryMessage(**payload)
    assert telemetry.motor_id == "MTR-775-001"
    assert telemetry.sensors.current_a == 1.45


def test_disconnected_sensor_with_null_value():
    """Verify zero vs unavailable principle: disconnected sensor has null value and DISCONNECTED status."""
    payload = {
        "schema_version": "1.0.0",
        "event_id": str(uuid.uuid4()),
        "device_id": "ESP32-NODE-001",
        "motor_id": "MTR-775-001",
        "source": "hardware",
        "seq": 105,
        "timestamp": "2026-10-09T16:30:01.000Z",
        "sensors": {
            "temperature_c": None,
            "current_a": 1.50,
            "vibration_g_rms": 0.40,
        },
        "sensor_status": {
            "temperature": "DISCONNECTED",
            "current": "OK",
            "vibration": "OK",
        },
        "inference": {
            "status": "INPUT_INVALID",
            "health_status": "unknown",
            "confidence": 0.0,
        },
    }
    telemetry = TelemetryMessage(**payload)
    assert telemetry.sensors.temperature_c is None
    assert telemetry.sensor_status.temperature == "DISCONNECTED"


def test_invalid_negative_current_rejected():
    """Verify out-of-range sensor values (negative current) are rejected."""
    payload = {
        "schema_version": "1.0.0",
        "event_id": str(uuid.uuid4()),
        "device_id": "ESP32-NODE-001",
        "motor_id": "MTR-775-001",
        "source": "hardware",
        "seq": 106,
        "timestamp": "2026-10-09T16:30:02.000Z",
        "sensors": {
            "temperature_c": 35.0,
            "current_a": -0.5,  # Invalid negative current
            "vibration_g_rms": 0.3,
        },
        "sensor_status": {
            "temperature": "OK",
            "current": "OK",
            "vibration": "OK",
        },
        "inference": {
            "status": "PREDICTED",
            "health_status": "healthy",
            "confidence": 0.95,
        },
    }
    with pytest.raises(ValidationError):
        TelemetryMessage(**payload)
