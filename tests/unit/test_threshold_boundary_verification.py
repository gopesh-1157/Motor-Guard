"""
MotorGuard — Exhaustive Threshold Boundary & Auto-Recovery Verification
========================================================================

Systematically tests each physical metric:
1. Armature current (current_a)
2. Operating temperature (temperature_c)
3. Dynamic vibration RMS (vibration_g_rms)
4. Instantaneous vibration peak shock (vibration_g_peak)

At 6 boundary conditions:
- Just below warning (warning - delta)
- Exactly at warning (warning)
- Just above warning (warning + delta)
- Just below critical (critical - delta)
- Exactly at critical (critical)
- Just above critical (critical + delta)

And verifies:
- Motor health classification (MotorService.calculate_motor_health)
- Alert generation severity (AlertService.evaluate_telemetry_for_alerts)
- Alert auto-recovery hysteresis behavior (AlertService._auto_resolve_if_active)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from backend.app.services.alert_service import AlertService
from backend.app.services.motor_service import MotorService


def _fresh_telemetry(sensors: dict) -> dict:
    """Helper returning fresh, valid telemetry payload."""
    return {
        "motor_id": "MTR-775-001",
        "device_id": "esp32-node-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server_received_at": datetime.now(timezone.utc).isoformat(),
        "sensors": sensors,
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
        "inference": {"health_status": "healthy", "confidence": 0.98},
    }


# Standard effective thresholds for boundary evaluation
TEST_THRESHOLDS = {
    "current_warning_a": 3.4,
    "current_critical_a": 4.0,
    "temperature_warning_c": 50.0,
    "temperature_critical_c": 70.0,
    "vibration_warning_g": 0.100,
    "vibration_critical_g": 0.400,
    "peak_vibration_g": 0.350,
    "peak_vibration_critical_g": 0.800,
    "stale_timeout_sec": 15,
    "offline_timeout_sec": 35,
}

NOMINAL_SENSORS = {
    "current_a": 1.0,
    "temperature_c": 30.0,
    "vibration_g_rms": 0.030,
    "vibration_g_peak": 0.100,
}


@pytest.fixture
def mock_db_and_services():
    mock_db = MagicMock()
    mock_col = AsyncMock()
    mock_col.find_one = AsyncMock(return_value=None)
    mock_col.find_one_and_update = AsyncMock(return_value=None)
    mock_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alert-123"))
    mock_col.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.__getitem__.return_value = mock_col

    alert_svc = AlertService(mock_db)
    alert_svc.get_effective_thresholds = AsyncMock(return_value=dict(TEST_THRESHOLDS))
    motor_svc = MotorService(mock_db)

    return mock_db, alert_svc, motor_svc


def was_auto_resolved(mock_db: MagicMock, trigger_type: str) -> bool:
    """Helper to check if find_one_and_update was called targeting a specific trigger_type."""
    for call in mock_db["alerts"].find_one_and_update.call_args_list:
        args, _ = call
        if args and isinstance(args[0], dict) and args[0].get("trigger_type") == trigger_type:
            return True
    return False


# ==============================================================================
# 1. Armature Current Boundaries (Warn: 3.4A, Crit: 4.0A)
# ==============================================================================

class TestCurrentBoundaries:
    @pytest.mark.parametrize(
        "current_val, expected_health, expected_alert_severity",
        [
            (3.390, "healthy", None),       # Just below warning
            (3.400, "warning", "WARNING"),   # Exactly at warning
            (3.410, "warning", "WARNING"),   # Just above warning
            (3.990, "warning", "WARNING"),   # Just below critical
            (4.000, "critical", "CRITICAL"), # Exactly at critical
            (4.010, "critical", "CRITICAL"), # Just above critical
        ],
    )
    @pytest.mark.asyncio
    async def test_current_boundaries(self, mock_db_and_services, current_val, expected_health, expected_alert_severity):
        _, alert_svc, motor_svc = mock_db_and_services

        sensors = dict(NOMINAL_SENSORS, current_a=current_val)
        telem = _fresh_telemetry(sensors)

        # 1. Health status
        health = await motor_svc.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=telem,
            effective_thresholds=TEST_THRESHOLDS,
        )
        assert health == expected_health, f"Current {current_val}A expected health {expected_health}, got {health}"

        # 2. Alert generation
        alerts = await alert_svc.evaluate_telemetry_for_alerts(telem)
        curr_alerts = [a for a in alerts if a.trigger_type == "THRESHOLD_OVERCURRENT"]
        if expected_alert_severity is None:
            assert len(curr_alerts) == 0, f"Expected no alert at {current_val}A, got {curr_alerts}"
        else:
            assert len(curr_alerts) == 1, f"Expected 1 alert at {current_val}A, got {len(curr_alerts)}"
            assert curr_alerts[0].severity == expected_alert_severity

    @pytest.mark.asyncio
    async def test_current_auto_recovery_hysteresis(self, mock_db_and_services):
        mock_db, alert_svc, _ = mock_db_and_services

        # Warning is 3.4A. Hysteresis is 10% (3.4 * 0.90 = 3.06A).
        # At 3.10A (below 3.4A, but above 3.06A) -> no new alert, but no auto-recovery yet.
        telem_hysteresis = _fresh_telemetry(dict(NOMINAL_SENSORS, current_a=3.10))
        await alert_svc.evaluate_telemetry_for_alerts(telem_hysteresis)
        assert not was_auto_resolved(mock_db, "THRESHOLD_OVERCURRENT")

        # At 3.05A (below 3.06A) -> auto-recovery triggers!
        mock_db["alerts"].find_one_and_update.reset_mock()
        telem_recovery = _fresh_telemetry(dict(NOMINAL_SENSORS, current_a=3.05))
        await alert_svc.evaluate_telemetry_for_alerts(telem_recovery)
        assert was_auto_resolved(mock_db, "THRESHOLD_OVERCURRENT")


# ==============================================================================
# 2. Temperature Boundaries (Warn: 50.0°C, Crit: 70.0°C)
# ==============================================================================

class TestTemperatureBoundaries:
    @pytest.mark.parametrize(
        "temp_val, expected_health, expected_alert_severity",
        [
            (49.9, "healthy", None),        # Just below warning
            (50.0, "warning", "WARNING"),    # Exactly at warning
            (50.1, "warning", "WARNING"),    # Just above warning
            (69.9, "warning", "WARNING"),    # Just below critical
            (70.0, "critical", "CRITICAL"),  # Exactly at critical
            (70.1, "critical", "CRITICAL"),  # Just above critical
        ],
    )
    @pytest.mark.asyncio
    async def test_temperature_boundaries(self, mock_db_and_services, temp_val, expected_health, expected_alert_severity):
        _, alert_svc, motor_svc = mock_db_and_services

        sensors = dict(NOMINAL_SENSORS, temperature_c=temp_val)
        telem = _fresh_telemetry(sensors)

        # 1. Health status
        health = await motor_svc.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=telem,
            effective_thresholds=TEST_THRESHOLDS,
        )
        assert health == expected_health, f"Temp {temp_val}°C expected health {expected_health}, got {health}"

        # 2. Alert generation
        alerts = await alert_svc.evaluate_telemetry_for_alerts(telem)
        temp_alerts = [a for a in alerts if a.trigger_type == "THRESHOLD_OVERTEMPERATURE"]
        if expected_alert_severity is None:
            assert len(temp_alerts) == 0
        else:
            assert len(temp_alerts) == 1
            assert temp_alerts[0].severity == expected_alert_severity

    @pytest.mark.asyncio
    async def test_temperature_auto_recovery_hysteresis(self, mock_db_and_services):
        mock_db, alert_svc, _ = mock_db_and_services

        # Warning is 50.0°C. Hysteresis is 2.0°C (recovery requires <= 48.0°C).
        # At 49.0°C (below 50.0°C, but above 48.0°C) -> no auto-recovery yet.
        telem_hysteresis = _fresh_telemetry(dict(NOMINAL_SENSORS, temperature_c=49.0))
        await alert_svc.evaluate_telemetry_for_alerts(telem_hysteresis)
        assert not was_auto_resolved(mock_db, "THRESHOLD_OVERTEMPERATURE")

        # At 47.9°C (<= 48.0°C) -> auto-recovery triggers!
        mock_db["alerts"].find_one_and_update.reset_mock()
        telem_recovery = _fresh_telemetry(dict(NOMINAL_SENSORS, temperature_c=47.9))
        await alert_svc.evaluate_telemetry_for_alerts(telem_recovery)
        assert was_auto_resolved(mock_db, "THRESHOLD_OVERTEMPERATURE")


# ==============================================================================
# 3. Dynamic Vibration RMS Boundaries (Warn: 0.100g, Crit: 0.400g)
# ==============================================================================

class TestVibrationRMSBoundaries:
    @pytest.mark.parametrize(
        "vib_val, expected_health, expected_alert_severity",
        [
            (0.099, "healthy", None),        # Just below warning
            (0.100, "warning", "WARNING"),    # Exactly at warning
            (0.101, "warning", "WARNING"),    # Just above warning
            (0.399, "warning", "WARNING"),    # Just below critical
            (0.400, "critical", "CRITICAL"),  # Exactly at critical
            (0.401, "critical", "CRITICAL"),  # Just above critical
        ],
    )
    @pytest.mark.asyncio
    async def test_vibration_rms_boundaries(self, mock_db_and_services, vib_val, expected_health, expected_alert_severity):
        _, alert_svc, motor_svc = mock_db_and_services

        sensors = dict(NOMINAL_SENSORS, vibration_g_rms=vib_val)
        telem = _fresh_telemetry(sensors)

        # 1. Health status
        health = await motor_svc.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=telem,
            effective_thresholds=TEST_THRESHOLDS,
        )
        assert health == expected_health, f"Vib RMS {vib_val}g expected health {expected_health}, got {health}"

        # 2. Alert generation
        alerts = await alert_svc.evaluate_telemetry_for_alerts(telem)
        rms_alerts = [a for a in alerts if a.trigger_type == "THRESHOLD_HIGH_VIBRATION_RMS"]
        if expected_alert_severity is None:
            assert len(rms_alerts) == 0
        else:
            assert len(rms_alerts) == 1
            assert rms_alerts[0].severity == expected_alert_severity

    @pytest.mark.asyncio
    async def test_vibration_rms_auto_recovery_hysteresis(self, mock_db_and_services):
        mock_db, alert_svc, _ = mock_db_and_services

        # Warning is 0.100g. Hysteresis is 15% (recovery requires <= 0.085g).
        # At 0.090g (below 0.100g, but above 0.085g) -> no auto-recovery yet.
        telem_hysteresis = _fresh_telemetry(dict(NOMINAL_SENSORS, vibration_g_rms=0.090))
        await alert_svc.evaluate_telemetry_for_alerts(telem_hysteresis)
        assert not was_auto_resolved(mock_db, "THRESHOLD_HIGH_VIBRATION_RMS")

        # At 0.084g (<= 0.085g) -> auto-recovery triggers!
        mock_db["alerts"].find_one_and_update.reset_mock()
        telem_recovery = _fresh_telemetry(dict(NOMINAL_SENSORS, vibration_g_rms=0.084))
        await alert_svc.evaluate_telemetry_for_alerts(telem_recovery)
        assert was_auto_resolved(mock_db, "THRESHOLD_HIGH_VIBRATION_RMS")


# ==============================================================================
# 4. Instantaneous Vibration Peak Shock Boundaries (Warn: 0.350g, Crit: 0.800g)
# ==============================================================================

class TestPeakShockBoundaries:
    @pytest.mark.parametrize(
        "peak_val, expected_health, expected_alert_severity",
        [
            (0.349, "healthy", None),        # Just below warning
            (0.350, "warning", "WARNING"),    # Exactly at warning
            (0.351, "warning", "WARNING"),    # Just above warning
            (0.799, "warning", "WARNING"),    # Just below critical
            (0.800, "critical", "CRITICAL"),  # Exactly at critical
            (0.801, "critical", "CRITICAL"),  # Just above critical
        ],
    )
    @pytest.mark.asyncio
    async def test_peak_shock_boundaries(self, mock_db_and_services, peak_val, expected_health, expected_alert_severity):
        _, alert_svc, motor_svc = mock_db_and_services

        sensors = dict(NOMINAL_SENSORS, vibration_g_peak=peak_val)
        telem = _fresh_telemetry(sensors)

        # 1. Health status
        health = await motor_svc.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=telem,
            effective_thresholds=TEST_THRESHOLDS,
        )
        assert health == expected_health, f"Peak shock {peak_val}g expected health {expected_health}, got {health}"

        # 2. Alert generation
        alerts = await alert_svc.evaluate_telemetry_for_alerts(telem)
        peak_alerts = [a for a in alerts if a.trigger_type == "THRESHOLD_HIGH_VIBRATION_PEAK"]
        if expected_alert_severity is None:
            assert len(peak_alerts) == 0
        else:
            assert len(peak_alerts) == 1
            assert peak_alerts[0].severity == expected_alert_severity

    @pytest.mark.asyncio
    async def test_peak_shock_auto_recovery_hysteresis(self, mock_db_and_services):
        mock_db, alert_svc, _ = mock_db_and_services

        # Warning is 0.350g. Hysteresis is 15% (recovery requires <= 0.2975g).
        # At 0.320g (below 0.350g, but above 0.2975g) -> no auto-recovery yet.
        telem_hysteresis = _fresh_telemetry(dict(NOMINAL_SENSORS, vibration_g_peak=0.320))
        await alert_svc.evaluate_telemetry_for_alerts(telem_hysteresis)
        assert not was_auto_resolved(mock_db, "THRESHOLD_HIGH_VIBRATION_PEAK")

        # At 0.290g (<= 0.2975g) -> auto-recovery triggers!
        mock_db["alerts"].find_one_and_update.reset_mock()
        telem_recovery = _fresh_telemetry(dict(NOMINAL_SENSORS, vibration_g_peak=0.290))
        await alert_svc.evaluate_telemetry_for_alerts(telem_recovery)
        assert was_auto_resolved(mock_db, "THRESHOLD_HIGH_VIBRATION_PEAK")
