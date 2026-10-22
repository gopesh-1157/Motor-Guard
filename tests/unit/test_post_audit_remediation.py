"""
MotorGuard — Post-Audit Remediation Verification Suite
======================================================

Tests targeted fixes for findings:
- F-01: Warning & critical boundary consistency (>= rule across health & alerts)
- F-02: Peak vibration shock inclusion in motor health classification
- F-04: Threshold precedence hierarchy and explicit override consistency
- F-05: WebSocket Origin validation & policy violation close code 1008
- F-07: Legacy trigger compatibility (THRESHOLD_HIGH_VIBRATION, SENSOR_DISCONNECTED)
- F-08: Hermetic database isolation verification (tests cannot touch real MongoDB)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.core.security import create_access_token
from backend.app.services.alert_service import AlertService
from backend.app.services.motor_service import MotorService
from backend.app.services.threshold_service import ThresholdResolver, get_builtin_defaults
from backend.app.db.mongodb import db_manager, MongoDBManager


def _make_telemetry(sensors: dict) -> dict:
    """Helper to build a valid fresh telemetry document for health classification tests."""
    return {
        "sensors": sensors,
        "server_received_at": datetime.now(timezone.utc).isoformat(),
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
        "inference": {"health_status": "healthy"},
    }


# ==============================================================================
# F-01: Warning & Critical Boundary Consistency (>= semantics)
# ==============================================================================

class TestF01BoundaryConsistency:
    """Verifies reading >= warning_limit for warnings and reading >= critical_limit for critical."""

    @pytest.mark.asyncio
    async def test_alert_service_exact_boundaries(self):
        """Alerts trigger at exact boundary (reading == limit)."""
        mock_db = MagicMock()
        mock_col = AsyncMock()
        mock_col.find_one = AsyncMock(return_value=None)
        mock_col.find_one_and_update = AsyncMock(return_value=None)
        mock_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc1"))
        mock_db.__getitem__.return_value = mock_col

        service = AlertService(mock_db)

        service.get_effective_thresholds = AsyncMock(return_value={
            "current_warning_a": 3.4,
            "current_critical_a": 4.0,
            "temperature_warning_c": 50.0,
            "temperature_critical_c": 70.0,
            "vibration_warning_g": 0.100,
            "vibration_critical_g": 0.200,
            "peak_vibration_g": 0.350,
            "peak_vibration_critical_g": 0.800,
        })

        # Exact warning boundary
        payload_warn = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sensors": {
                "current_a": 3.4,
                "temperature_c": 50.0,
                "vibration_g_rms": 0.100,
                "vibration_g_peak": 0.350,
            },
            "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
            "inference": {"health_status": "healthy", "confidence": 0.95},
        }

        alerts = await service.evaluate_telemetry_for_alerts(payload_warn)
        alert_types = {a.trigger_type: a.severity for a in alerts}

        assert alert_types.get("THRESHOLD_OVERCURRENT") == "WARNING"
        assert alert_types.get("THRESHOLD_OVERTEMPERATURE") == "WARNING"
        assert alert_types.get("THRESHOLD_HIGH_VIBRATION_RMS") == "WARNING"
        assert alert_types.get("THRESHOLD_HIGH_VIBRATION_PEAK") == "WARNING"

        # Exact critical boundary
        payload_crit = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sensors": {
                "current_a": 4.0,
                "temperature_c": 70.0,
                "vibration_g_rms": 0.200,
                "vibration_g_peak": 0.800,
            },
            "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
            "inference": {"health_status": "healthy", "confidence": 0.95},
        }

        alerts_crit = await service.evaluate_telemetry_for_alerts(payload_crit)
        alert_crit_types = {a.trigger_type: a.severity for a in alerts_crit}

        assert alert_crit_types.get("THRESHOLD_OVERCURRENT") == "CRITICAL"
        assert alert_crit_types.get("THRESHOLD_OVERTEMPERATURE") == "CRITICAL"
        assert alert_crit_types.get("THRESHOLD_HIGH_VIBRATION_RMS") == "CRITICAL"
        assert alert_crit_types.get("THRESHOLD_HIGH_VIBRATION_PEAK") == "CRITICAL"

    @pytest.mark.asyncio
    async def test_motor_service_health_exact_boundaries(self):
        """Motor health classification evaluates exact boundaries identically."""
        mock_db = MagicMock()
        mock_col = AsyncMock()
        mock_col.find_one = AsyncMock(return_value=None)
        mock_db.__getitem__.return_value = mock_col

        service = MotorService(mock_db)

        thresholds = {
            "current_warning_a": 3.4,
            "current_critical_a": 4.0,
            "temperature_warning_c": 50.0,
            "temperature_critical_c": 70.0,
            "vibration_warning_g": 0.100,
            "vibration_critical_g": 0.200,
            "peak_vibration_g": 0.350,
            "peak_vibration_critical_g": 0.800,
        }

        # Sub-warning readings -> healthy
        h_below = await service.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=_make_telemetry({"current_a": 3.399, "temperature_c": 49.9, "vibration_g_rms": 0.099, "vibration_g_peak": 0.349}),
            effective_thresholds=thresholds,
        )
        assert h_below == "healthy"

        # Exact warning readings -> warning
        h_warn = await service.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=_make_telemetry({"current_a": 3.4, "temperature_c": 30.0, "vibration_g_rms": 0.05, "vibration_g_peak": 0.1}),
            effective_thresholds=thresholds,
        )
        assert h_warn == "warning"

        # Exact critical reading -> critical
        h_crit = await service.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=_make_telemetry({"current_a": 4.0, "temperature_c": 30.0, "vibration_g_rms": 0.05, "vibration_g_peak": 0.1}),
            effective_thresholds=thresholds,
        )
        assert h_crit == "critical"


# ==============================================================================
# F-02: Peak Shock in Motor Health Classification
# ==============================================================================

class TestF02PeakShockHealthClassification:
    """Verifies peak vibration shock affects health status even when RMS is normal."""

    @pytest.mark.asyncio
    async def test_peak_shock_triggers_warning_and_critical_independently(self):
        mock_db = MagicMock()
        mock_col = AsyncMock()
        mock_col.find_one = AsyncMock(return_value=None)
        mock_db.__getitem__.return_value = mock_col

        service = MotorService(mock_db)

        thresholds = {
            "current_warning_a": 3.4,
            "current_critical_a": 4.0,
            "temperature_warning_c": 50.0,
            "temperature_critical_c": 70.0,
            "vibration_warning_g": 0.100,
            "vibration_critical_g": 0.200,
            "peak_vibration_g": 0.350,
            "peak_vibration_critical_g": 0.800,
        }

        # RMS is low (0.020 g), but peak shock hits warning (0.350 g pk)
        h_peak_warn = await service.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=_make_telemetry({"current_a": 1.0, "temperature_c": 30.0, "vibration_g_rms": 0.020, "vibration_g_peak": 0.350}),
            effective_thresholds=thresholds,
        )
        assert h_peak_warn == "warning"

        # RMS is low (0.020 g), but peak shock hits critical (0.800 g pk)
        h_peak_crit = await service.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=_make_telemetry({"current_a": 1.0, "temperature_c": 30.0, "vibration_g_rms": 0.020, "vibration_g_peak": 0.800}),
            effective_thresholds=thresholds,
        )
        assert h_peak_crit == "critical"

        # Alternate naming aliases (peak_shock_g, vibration_peak_g) supported
        h_alias = await service.calculate_motor_health(
            motor_id="MTR-775-001",
            motor_doc={"motor_id": "MTR-775-001"},
            last_telem=_make_telemetry({"current_a": 1.0, "temperature_c": 30.0, "vibration_g_rms": 0.020, "peak_shock_g": 0.850}),
            effective_thresholds=thresholds,
        )
        assert h_alias == "critical"


# ==============================================================================
# F-04: Threshold Precedence Hierarchy
# ==============================================================================

class TestF04ThresholdPrecedence:
    """Motor overrides > Persisted gateway settings > Built-in defaults."""

    def test_precedence_order(self):
        builtin_defaults = get_builtin_defaults()
        assert builtin_defaults["current_critical_a"] == 4.0

        gateway_settings = {"current_critical_a": 5.0, "temperature_critical_c": 65.0}

        # Gateway overrides built-in default
        resolved_gateway = ThresholdResolver.resolve_from_docs(
            system_settings_doc=gateway_settings,
            motor_doc=None,
        )
        assert resolved_gateway["current_critical_a"] == 5.0
        assert resolved_gateway["temperature_critical_c"] == 65.0

        # Motor explicit override overrides gateway settings
        motor = {
            "motor_id": "MTR-CUSTOM",
            "thresholds": {
                "current_critical_a": 6.5,
                "has_custom_thresholds": True,
            },
        }

        resolved_motor = ThresholdResolver.resolve_from_docs(
            system_settings_doc=gateway_settings,
            motor_doc=motor,
        )
        assert resolved_motor["current_critical_a"] == 6.5
        assert resolved_motor["temperature_critical_c"] == 65.0  # Inherited from gateway


# ==============================================================================
# F-05: WebSocket Origin Validation & Policy Violation Close
# ==============================================================================

class TestF05WebSocketOriginValidation:
    """Verifies Origin validation on WebSocket connection."""

    def test_websocket_valid_origin_accepted(self):
        client = TestClient(app)
        token = create_access_token(data={"sub": "operator_bob", "role": "Technician"})
        allowed_origin = settings.cors_origins_list[0]

        with client.websocket_connect(
            f"/ws/telemetry?token={token}",
            headers={"Origin": allowed_origin},
        ) as websocket:
            websocket.send_text("ping")

    def test_websocket_unauthorized_origin_rejected(self):
        client = TestClient(app)
        token = create_access_token(data={"sub": "operator_bob", "role": "Technician"})

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                f"/ws/telemetry?token={token}",
                headers={"Origin": "http://malicious-industrial-attacker.com"},
            ):
                pass
        # Must close with 1008 Policy Violation
        assert exc_info.value.code == 1008

    def test_websocket_no_origin_non_browser_client_accepted(self):
        """Non-browser client (e.g. backend bridge, test client) without Origin header is accepted."""
        client = TestClient(app)
        token = create_access_token(data={"sub": "tech_dave", "role": "Technician"})

        with client.websocket_connect(f"/ws/telemetry?token={token}") as websocket:
            websocket.send_text("status")


# ==============================================================================
# F-07: Legacy Trigger Compatibility
# ==============================================================================

class TestF07LegacyTriggerCompatibility:
    """Backward-compatible auto-resolution of legacy alerts without silent data loss."""

    @pytest.mark.asyncio
    async def test_legacy_vibration_alert_auto_resolves_when_safe(self):
        mock_db = MagicMock()
        mock_col = AsyncMock()
        mock_col.find_one = AsyncMock(return_value=None)
        mock_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc1"))

        resolved_triggers = []

        async def _mock_find_one_and_update(query, update, **kwargs):
            trigger = query.get("trigger_type")
            if trigger:
                resolved_triggers.append(trigger)
            return None

        mock_col.find_one_and_update = _mock_find_one_and_update
        mock_db.__getitem__.return_value = mock_col

        service = AlertService(mock_db)
        service.get_effective_thresholds = AsyncMock(return_value={
            "vibration_warning_g": 0.100,
            "vibration_critical_g": 0.200,
            "peak_vibration_g": 0.350,
            "peak_vibration_critical_g": 0.800,
        })

        # Telemetry with normalized vibration levels (0.05 g RMS, 0.15 g pk)
        payload = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sensors": {
                "vibration_g_rms": 0.05,
                "vibration_g_peak": 0.15,
            },
            "sensor_status": {"vibration": "OK"},
            "inference": {"health_status": "healthy"},
        }

        await service.evaluate_telemetry_for_alerts(payload)
        # Both modern and legacy vibration triggers should be resolved
        assert "THRESHOLD_HIGH_VIBRATION_RMS" in resolved_triggers
        assert "THRESHOLD_HIGH_VIBRATION" in resolved_triggers

    @pytest.mark.asyncio
    async def test_legacy_sensor_disconnected_alert_auto_resolves_when_ok(self):
        mock_db = MagicMock()
        mock_col = AsyncMock()
        mock_col.find_one = AsyncMock(return_value=None)
        mock_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc1"))

        resolved_triggers = []

        async def _mock_find_one_and_update(query, update, **kwargs):
            trigger = query.get("trigger_type")
            if trigger:
                resolved_triggers.append(trigger)
            return None

        mock_col.find_one_and_update = _mock_find_one_and_update
        mock_db.__getitem__.return_value = mock_col

        service = AlertService(mock_db)
        service.get_effective_thresholds = AsyncMock(return_value={})

        payload = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sensors": {},
            "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
            "inference": {},
        }

        await service.evaluate_telemetry_for_alerts(payload)
        assert "SENSOR_DISCONNECTED" in resolved_triggers


# ==============================================================================
# F-08: Database Isolation Regression Verification
# ==============================================================================

class TestF08DatabaseIsolation:
    """Verifies test environment cannot connect to or seed persistent MongoDB."""

    def test_environment_is_test(self):
        assert settings.ENVIRONMENT == "test"

    @pytest.mark.asyncio
    async def test_connect_to_database_fails_closed_without_mock(self):
        """Calling unpatched connect_to_database in test environment with db=None fails closed."""
        unpatched = getattr(MongoDBManager, "_unpatched_connect", None)
        assert unpatched is not None
        with patch.object(MongoDBManager, "db", None):
            with pytest.raises(RuntimeError) as exc_info:
                await unpatched()
            assert "CRITICAL TEST ISOLATION FAILURE" in str(exc_info.value)

    def test_db_manager_points_to_mock_isolated_db(self):
        """db_manager in active test suite is hermetic mock database."""
        assert db_manager.db is not None
        assert db_manager.db.name == "motorguard_hermetic_test_db"
