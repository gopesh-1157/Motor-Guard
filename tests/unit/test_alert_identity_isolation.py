"""Regression coverage for metric-specific alert identity and recovery."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.services.alert_service import AlertService


def _service() -> tuple[AlertService, AsyncMock]:
    collection = AsyncMock()
    collection.find_one = AsyncMock(return_value=None)
    collection.find_one_and_update = AsyncMock(return_value=None)
    collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alert-id"))
    db = MagicMock()
    db.__getitem__.side_effect = lambda _name: collection
    return AlertService(db), collection


@pytest.mark.asyncio
async def test_sensor_faults_have_independent_alert_identities() -> None:
    service, collection = _service()

    await service.evaluate_telemetry_for_alerts({
        "motor_id": "MTR-TEST-001",
        "device_id": "esp32-test-001",
        "sensors": {"temperature_c": None, "current_a": None, "vibration_g_rms": 0.02},
        "sensor_status": {"temperature": "DISCONNECTED", "current": "DISCONNECTED", "vibration": "OK"},
        "inference": {"health_status": "unknown", "confidence": 0.0},
    })

    inserted_types = {call.args[0]["trigger_type"] for call in collection.insert_one.await_args_list}
    assert inserted_types == {"SENSOR_TEMPERATURE_DISCONNECTED", "SENSOR_CURRENT_DISCONNECTED"}
    resolved_types = {call.args[0]["trigger_type"] for call in collection.find_one_and_update.await_args_list}
    assert "SENSOR_CURRENT_DISCONNECTED" not in resolved_types


@pytest.mark.asyncio
async def test_rms_and_peak_shock_create_distinct_alerts() -> None:
    service, collection = _service()

    await service.evaluate_telemetry_for_alerts({
        "motor_id": "MTR-TEST-001",
        "device_id": "esp32-test-001",
        "sensors": {"temperature_c": 25.0, "current_a": 1.0, "vibration_g_rms": 0.5, "vibration_g_peak": 0.9},
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK", "current_calibrated": True},
        "inference": {"health_status": "healthy", "confidence": 0.9},
    })

    inserted_types = {call.args[0]["trigger_type"] for call in collection.insert_one.await_args_list}
    assert "THRESHOLD_HIGH_VIBRATION_RMS" in inserted_types
    assert "THRESHOLD_HIGH_VIBRATION_PEAK" in inserted_types


def test_freshness_uses_server_receipt_time_only() -> None:
    from backend.app.services.motor_service import MotorService

    now = datetime.now(timezone.utc)
    thresholds = {"stale_timeout_sec": 15, "offline_timeout_sec": 35}
    assert MotorService._telemetry_freshness({"server_received_at": now}, thresholds) == "fresh"
    assert MotorService._telemetry_freshness({"server_received_at": now.replace(year=2020)}, thresholds) == "offline"
    assert MotorService._telemetry_freshness({"timestamp": now.isoformat()}, thresholds) == "unknown"
