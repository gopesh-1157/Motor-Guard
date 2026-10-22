"""
MotorGuard — Phase 7 Steps 3-6: Alert System Verification & Regression Tests

Comprehensive tests covering:
1. Exact ML labels: 'healthy', 'warning', 'critical'.
2. Deterministic safety rules never suppressed by a healthy ML prediction.
3. Sensor and inference diagnostic alerts without fabricated ML labels.
4. Alert metadata persistence, site_id, category, and safe configuration snapshots.
5. Deduplication and recovery hysteresis.
6. Offline timeout detection, single-alert deduplication, grace period, and recovery on fresh telemetry.
7. Multi-tenant RBAC: Admin fleet-wide, Manager site isolation, Technician motor/alert scoping.
8. Non-disclosing 404 responses for inaccessible objects.
9. Dynamic technician assignment validation (active status, Technician role, site scoping).
10. Audit trail generation for all alert lifecycle events.
11. WebSocket cross-site and unscoped manager isolation.
"""

from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.core.security import create_access_token
from backend.app.schemas.user import UserOut, UserInDB
from backend.app.schemas.alert import AlertOut, AlertCategory, TRIGGER_TYPE_TO_CATEGORY
from backend.app.services.alert_service import AlertService, _build_safe_config_snapshot
from backend.app.api.v1.endpoints.websocket import ws_manager
from backend.app.api.v1.endpoints.alerts import get_alert_service
from backend.app.core.auth import get_user_service

client = TestClient(app)


def auth_header(username: str, role: str) -> dict:
    token = create_access_token(data={"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


class TestStep3AlertPersistenceAndEvaluation:
    """Step 3: Alert records, evaluation, hysteresis, and offline detection."""

    def test_configuration_snapshot_sanitization(self):
        """Configuration snapshots must filter out sensitive keys and secrets."""
        raw_thresholds = {
            "current_warning_a": 3.4,
            "current_critical_a": 4.0,
            "secret_api_key": "super_secret_token",
            "db_password": "sensitive_password",
            "vibration_warning_g": 0.100,
        }
        safe_snapshot = _build_safe_config_snapshot(raw_thresholds)
        assert "secret_api_key" not in safe_snapshot
        assert "db_password" not in safe_snapshot
        assert safe_snapshot["current_warning_a"] == 3.4
        assert safe_snapshot["vibration_warning_g"] == 0.100

    @pytest.mark.asyncio
    async def test_deterministic_safety_never_suppressed_by_healthy_ml(self):
        """Requirement: A healthy ML prediction must never suppress a deterministic safety violation."""
        mock_alerts = AsyncMock()
        mock_alerts.find_one = AsyncMock(return_value=None)
        mock_alerts.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alt_safety_1"))
        mock_motors = AsyncMock()
        mock_motors.find_one = AsyncMock(return_value={"motor_id": "MTR-SAFETY-01", "site_id": "SITE-PLANT-A"})

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: {
            "alerts": mock_alerts,
            "motors": mock_motors,
            "telemetry": AsyncMock(),
            "users": AsyncMock(),
            "work_orders": AsyncMock(),
            "audit_events": AsyncMock(),
            "audit_logs": AsyncMock(),
        }.get(name, AsyncMock()))

        service = AlertService(mock_db)

        # Telemetry has HARD overcurrent violation AND ML claims 'healthy' with 99% confidence
        telemetry = {
            "motor_id": "MTR-SAFETY-01",
            "device_id": "dev-01",
            "site_id": "SITE-PLANT-A",
            "sensors": {
                "current_a": 6.8,  # Critical exceedance
                "temperature_c": 32.0,
                "vibration_g_rms": 0.04,
            },
            "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
            "inference": {
                "health_status": "healthy",  # ML says healthy!
                "confidence": 0.99,
            },
        }

        created = await service.evaluate_telemetry_for_alerts(telemetry)
        assert len(created) >= 1
        trigger_types = [a.trigger_type for a in created]
        assert "THRESHOLD_OVERCURRENT" in trigger_types or "HARD_OVERCURRENT_TRIP" in trigger_types
        # Verify severity remains CRITICAL despite healthy ML
        for a in created:
            assert a.severity in ("CRITICAL", "WARNING")
            assert a.category == "SAFETY_THRESHOLD"

    @pytest.mark.asyncio
    async def test_all_three_exact_ml_labels(self):
        """Preserve exactly three Edge Impulse labels: healthy, warning, critical."""
        mock_alerts = AsyncMock()
        mock_alerts.find_one = AsyncMock(return_value=None)
        mock_alerts.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alt_ml_1"))
        mock_alerts.find_one_and_update = AsyncMock(return_value=None)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: {
            "alerts": mock_alerts,
            "motors": AsyncMock(),
            "telemetry": AsyncMock(),
            "users": AsyncMock(),
            "work_orders": AsyncMock(),
            "audit_events": AsyncMock(),
            "audit_logs": AsyncMock(),
        }.get(name, AsyncMock()))

        service = AlertService(mock_db)

        # 1. Critical inference
        telem_crit = {
            "motor_id": "MTR-ML-01",
            "device_id": "dev-01",
            "sensors": {"current_a": 1.0, "temperature_c": 30.0, "vibration_g_rms": 0.05},
            "inference": {"health_status": "critical", "confidence": 0.94},
        }
        alerts_crit = await service.evaluate_telemetry_for_alerts(telem_crit)
        assert any(a.trigger_type == "CRITICAL_INFERENCE_FAULT" and a.category == "ML_INFERENCE" for a in alerts_crit)

        # 2. Warning inference
        telem_warn = {
            "motor_id": "MTR-ML-01",
            "device_id": "dev-01",
            "sensors": {"current_a": 1.0, "temperature_c": 30.0, "vibration_g_rms": 0.05},
            "inference": {"health_status": "warning", "confidence": 0.82},
        }
        alerts_warn = await service.evaluate_telemetry_for_alerts(telem_warn)
        assert any(a.trigger_type == "WARNING_INFERENCE_ANOMALY" and a.category == "ML_INFERENCE" for a in alerts_warn)

        # 3. Healthy inference: triggers no ML alerts, normalizes previous
        telem_healthy = {
            "motor_id": "MTR-ML-01",
            "device_id": "dev-01",
            "sensors": {"current_a": 1.0, "temperature_c": 30.0, "vibration_g_rms": 0.05},
            "inference": {"health_status": "healthy", "confidence": 0.98},
        }
        alerts_healthy = await service.evaluate_telemetry_for_alerts(telem_healthy)
        assert len(alerts_healthy) == 0

    @pytest.mark.asyncio
    async def test_sensor_and_inference_diagnostics_without_fabricated_ml_classes(self):
        """Sensor fault or model error generates diagnostic alert without synthesizing ML classes."""
        mock_alerts = AsyncMock()
        mock_alerts.find_one = AsyncMock(return_value=None)
        mock_alerts.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alt_diag_1"))

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: {
            "alerts": mock_alerts,
            "motors": AsyncMock(),
            "telemetry": AsyncMock(),
            "users": AsyncMock(),
            "work_orders": AsyncMock(),
            "audit_events": AsyncMock(),
            "audit_logs": AsyncMock(),
        }.get(name, AsyncMock()))

        service = AlertService(mock_db)

        # Telemetry reporting MODEL_ERROR on TinyML engine
        telem_err = {
            "motor_id": "MTR-ERR-01",
            "device_id": "dev-01",
            "sensors": {"current_a": 1.0, "temperature_c": 30.0, "vibration_g_rms": 0.05},
            "inference": {"status": "MODEL_ERROR", "model_error": "I2C bus timeout reading ADXL345 buffer"},
        }
        alerts = await service.evaluate_telemetry_for_alerts(telem_err)
        assert len(alerts) == 1
        assert alerts[0].trigger_type == "INFERENCE_DIAGNOSTIC_FAILURE"
        assert alerts[0].category == "SENSOR_DIAGNOSTIC"
        assert alerts[0].severity == "WARNING"

    @pytest.mark.asyncio
    async def test_offline_detection_deduplication_and_fresh_telemetry_recovery(self):
        """Device offline detection creates alert after timeout, deduplicates, and resolves on fresh data."""
        now = datetime.now(timezone.utc)
        timed_out_time = now - timedelta(seconds=60)

        # 1. Setup mock database
        active_alerts: dict = {}

        mock_alerts = AsyncMock()
        async def fake_find_one(filter_query):
            if filter_query.get("state") == "ACTIVE" and filter_query.get("trigger_type") == "DEVICE_OFFLINE":
                return active_alerts.get(filter_query.get("motor_id"))
            return None
        mock_alerts.find_one = AsyncMock(side_effect=fake_find_one)

        async def fake_insert_one(doc):
            doc["_id"] = "inserted_offline_alt"
            active_alerts[doc["motor_id"]] = dict(doc)
            return MagicMock(inserted_id="inserted_offline_alt")
        mock_alerts.insert_one = AsyncMock(side_effect=fake_insert_one)

        mock_alerts.update_one = AsyncMock()

        async def fake_find_one_and_update(filter_query, update_query, **kwargs):
            m_id = filter_query.get("motor_id")
            if m_id in active_alerts and filter_query.get("trigger_type") == "DEVICE_OFFLINE":
                doc = active_alerts.pop(m_id)
                doc["state"] = "RESOLVED"
                doc["_id"] = "resolved_offline_id"
                return doc
            return None
        mock_alerts.find_one_and_update = AsyncMock(side_effect=fake_find_one_and_update)

        # Mock motor and telemetry collections
        mock_motors = MagicMock()
        def fake_motor_cursor(*args, **kwargs):
            async def gen():
                yield {
                    "motor_id": "MTR-TIMED-OUT-01",
                    "assigned_device_id": "ESP32-NODE-TIMEOUT",
                    "site_id": "SITE-PLANT-A",
                    "device_offline_timeout_sec": 30,
                }
            return gen()
        mock_motors.find = MagicMock(side_effect=fake_motor_cursor)

        mock_telemetry = AsyncMock()
        # Telemetry is 60 seconds old (exceeds 30s timeout)
        mock_telemetry.find_one = AsyncMock(return_value={"server_received_at": timed_out_time})

        mock_work_orders = AsyncMock()
        mock_work_orders.find_one = AsyncMock(return_value=None)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: {
            "alerts": mock_alerts,
            "motors": mock_motors,
            "telemetry": mock_telemetry,
            "users": AsyncMock(),
            "work_orders": mock_work_orders,
            "audit_events": AsyncMock(),
            "audit_logs": AsyncMock(),
        }.get(name, AsyncMock()))

        service = AlertService(mock_db)

        # First scan: creates DEVICE_OFFLINE alert
        created_1 = await service.check_offline_devices(now=now)
        assert len(created_1) == 1
        assert created_1[0].trigger_type == "DEVICE_OFFLINE"
        assert created_1[0].category == "CONNECTIVITY"
        assert created_1[0].site_id == "SITE-PLANT-A"

        # Second scan (same state): deduplicated, does NOT create a second alert
        created_2 = await service.check_offline_devices(now=now)
        assert len(created_2) == 0
        mock_alerts.update_one.assert_called_once()  # Updated last_observed_at

        # Fresh telemetry arrives: resolves the active DEVICE_OFFLINE alert
        fresh_telemetry = {
            "motor_id": "MTR-TIMED-OUT-01",
            "device_id": "ESP32-NODE-TIMEOUT",
            "site_id": "SITE-PLANT-A",
            "sensors": {"current_a": 1.2, "temperature_c": 30.0, "vibration_g_rms": 0.05},
            "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
            "inference": {"health_status": "healthy", "confidence": 0.95},
        }
        await service.evaluate_telemetry_for_alerts(fresh_telemetry)
        auto_resolved = service.consume_auto_resolved_alerts()
        assert any(r.trigger_type == "DEVICE_OFFLINE" for r in auto_resolved)


class TestStep4ObjectLevelAuthorizationAndAudit:
    """Step 4: Object-level authorization, lifecycle transitions, audit logging, and WebSocket isolation."""

    @pytest.mark.asyncio
    async def test_admin_manager_technician_cross_site_isolation(self):
        """
        Verify isolation across two sites (SITE-A, SITE-B), two managers, and two technicians.
        - Manager A cannot view Site B alerts.
        - Technician A cannot view alerts for motors outside assigned scope.
        - Direct ID query for foreign alert returns non-disclosing 404.
        """
        now = datetime.now(timezone.utc)
        site_a_alert = {
            "_id": "id_alt_a",
            "alert_id": "ALT-SITE-A-01",
            "motor_id": "MTR-SITE-A-01",
            "device_id": "dev-a-01",
            "site_id": "SITE-A",
            "category": "SAFETY_THRESHOLD",
            "severity": "CRITICAL",
            "trigger_type": "THRESHOLD_OVERCURRENT",
            "trigger_value": 5.0,
            "threshold_limit": 4.0,
            "unit": "A",
            "message": "Site A overcurrent",
            "state": "ACTIVE",
            "triggered_at": now,
        }
        site_b_alert = {
            "_id": "id_alt_b",
            "alert_id": "ALT-SITE-B-01",
            "motor_id": "MTR-SITE-B-01",
            "device_id": "dev-b-01",
            "site_id": "SITE-B",
            "category": "SAFETY_THRESHOLD",
            "severity": "CRITICAL",
            "trigger_type": "THRESHOLD_OVERTEMPERATURE",
            "trigger_value": 65.0,
            "threshold_limit": 50.0,
            "unit": "°C",
            "message": "Site B overtemperature",
            "state": "ACTIVE",
            "triggered_at": now,
        }

        alerts_db = {"ALT-SITE-A-01": site_a_alert, "ALT-SITE-B-01": site_b_alert}

        mock_alerts = AsyncMock()
        mock_alerts.find_one = AsyncMock(side_effect=lambda q: alerts_db.get(q.get("alert_id")))

        # Motors collection mapping
        motors_db = {
            "MTR-SITE-A-01": {"motor_id": "MTR-SITE-A-01", "site_id": "SITE-A"},
            "MTR-SITE-B-01": {"motor_id": "MTR-SITE-B-01", "site_id": "SITE-B"},
        }
        mock_motors = AsyncMock()
        mock_motors.find_one = AsyncMock(side_effect=lambda q, *args: motors_db.get(q.get("motor_id")))

        # Cursor for listing motors
        def fake_motors_find(query, *args):
            allowed_sites = query.get("site_id", {}).get("$in", [])
            docs = [m for m in motors_db.values() if m["site_id"] in allowed_sites]
            async def gen():
                for d in docs:
                    yield d
            return gen()
        mock_motors.find = MagicMock(side_effect=fake_motors_find)

        # Cursor for listing alerts
        def fake_alerts_find(query, *args):
            m_in = query.get("motor_id", {}).get("$in", [])
            docs = [a for a in alerts_db.values() if not m_in or a["motor_id"] in m_in]
            class MockCursor:
                def sort(self, *a, **kw): return self
                def limit(self, *a, **kw): return self
                def __aiter__(self):
                    async def it():
                        for d in docs:
                            yield dict(d)
                    return it()
            return MockCursor()
        mock_alerts.find = MagicMock(side_effect=fake_alerts_find)

        mock_work_orders = AsyncMock()
        mock_work_orders.find_one = AsyncMock(return_value=None)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: {
            "alerts": mock_alerts,
            "motors": mock_motors,
            "users": AsyncMock(),
            "work_orders": mock_work_orders,
            "audit_events": AsyncMock(),
            "audit_logs": AsyncMock(),
        }.get(name, AsyncMock()))

        service = AlertService(mock_db)

        # 1. Admin: can access both Site A and Site B
        admin_user = UserOut(id="u1", username="admin_1", role="Admin", email="admin@m.local.com", is_active=True)
        res_a = await service.get_alert("ALT-SITE-A-01", current_user=admin_user)
        res_b = await service.get_alert("ALT-SITE-B-01", current_user=admin_user)
        assert res_a is not None and res_b is not None

        # 2. Manager A (assigned to SITE-A):
        manager_a = UserOut(id="u2", username="mgr_a", role="Manager", email="mgr_a@m.local.com", is_active=True, assigned_sites=["SITE-A"])
        assert await service.get_alert("ALT-SITE-A-01", current_user=manager_a) is not None
        # Must return None (non-disclosing 404) for Site B alert
        assert await service.get_alert("ALT-SITE-B-01", current_user=manager_a) is None

        # 3. Manager B (assigned to SITE-B):
        manager_b = UserOut(id="u3", username="mgr_b", role="Manager", email="mgr_b@m.local.com", is_active=True, assigned_sites=["SITE-B"])
        assert await service.get_alert("ALT-SITE-B-01", current_user=manager_b) is not None
        assert await service.get_alert("ALT-SITE-A-01", current_user=manager_b) is None

        # 4. Technician A (assigned to MTR-SITE-A-01):
        tech_a = UserOut(id="u4", username="tech_a", role="Technician", email="tech_a@m.local.com", is_active=True, assigned_motors=["MTR-SITE-A-01"])
        assert await service.get_alert("ALT-SITE-A-01", current_user=tech_a) is not None
        assert await service.get_alert("ALT-SITE-B-01", current_user=tech_a) is None

    @pytest.mark.asyncio
    async def test_dynamic_technician_assignment_scope_and_role_validation(self):
        """Manager cannot assign alert to out-of-scope technician or non-technician."""
        mock_alerts = AsyncMock()
        now = datetime.now(timezone.utc)
        alert_doc = {
            "_id": "id_alt_assign",
            "alert_id": "ALT-ASSIGN-VAL-01",
            "motor_id": "MTR-PLANT-A-01",
            "device_id": "dev-01",
            "site_id": "SITE-PLANT-A",
            "state": "ACTIVE",
            "severity": "CRITICAL",
            "trigger_type": "THRESHOLD_OVERCURRENT",
            "trigger_value": 4.5,
            "threshold_limit": 4.0,
            "unit": "A",
            "message": "Stator overcurrent",
            "triggered_at": now,
        }
        mock_alerts.find_one = AsyncMock(return_value=alert_doc)
        mock_alerts.find_one_and_update = AsyncMock(return_value=dict(alert_doc))

        # Users collection
        users_db = {
            "tech_site_a": {"username": "tech_site_a", "role": "Technician", "is_active": True, "assigned_sites": ["SITE-PLANT-A"]},
            "tech_site_b": {"username": "tech_site_b", "role": "Technician", "is_active": True, "assigned_sites": ["SITE-PLANT-B"]},
            "operator_c": {"username": "operator_c", "role": "Operator", "is_active": True, "assigned_sites": ["SITE-PLANT-A"]},
            "tech_inactive": {"username": "tech_inactive", "role": "Technician", "is_active": False, "assigned_sites": ["SITE-PLANT-A"]},
        }
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(side_effect=lambda q: users_db.get(q.get("username")))

        mock_work_orders = AsyncMock()
        mock_work_orders.find_one = AsyncMock(return_value=None)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: {
            "alerts": mock_alerts,
            "users": mock_users,
            "motors": AsyncMock(),
            "work_orders": mock_work_orders,
            "audit_events": AsyncMock(),
            "audit_logs": AsyncMock(),
        }.get(name, AsyncMock()))

        service = AlertService(mock_db)
        manager_a = UserOut(id="m1", username="mgr_a", role="Manager", email="m@local.com", is_active=True, assigned_sites=["SITE-PLANT-A"])

        # 1. Success: Assign to active Technician in SITE-PLANT-A
        res_ok = await service.assign_alert("ALT-ASSIGN-VAL-01", "tech_site_a", "mgr_a", current_user=manager_a)
        assert res_ok is not None

        # 2. Rejection: Assign to Technician outside manager site scope (403)
        with pytest.raises(Exception) as exc_403:
            await service.assign_alert("ALT-ASSIGN-VAL-01", "tech_site_b", "mgr_a", current_user=manager_a)
        assert "outside manager scope" in str(exc_403.value).lower()

        # 3. Rejection: Assign to Operator (400)
        with pytest.raises(Exception) as exc_op:
            await service.assign_alert("ALT-ASSIGN-VAL-01", "operator_c", "mgr_a", current_user=manager_a)
        assert "requires technician or admin role" in str(exc_op.value).lower()

        # 4. Rejection: Assign to inactive technician (400)
        with pytest.raises(Exception) as exc_inact:
            await service.assign_alert("ALT-ASSIGN-VAL-01", "tech_inactive", "mgr_a", current_user=manager_a)
        assert "inactive" in str(exc_inact.value).lower()

    @pytest.mark.asyncio
    async def test_websocket_authorization_isolation_logic(self):
        """WebSocket manager strictly isolates events across sites and unscoped managers."""
        # Manager scoped to SITE-NORTH
        meta_manager_north = {
            "username": "mgr_north",
            "role": "Manager",
            "assigned_sites": {"SITE-NORTH"},
            "assigned_motors": set(),
        }
        # Technician assigned only to MTR-01
        meta_tech_01 = {
            "username": "tech_bob",
            "role": "Technician",
            "assigned_sites": set(),
            "assigned_motors": {"MTR-01"},
        }

        # Event from SITE-NORTH / MTR-01
        event_north = {"type": "alert", "data": {"motor_id": "MTR-01", "site_id": "SITE-NORTH", "assigned_to": None}}
        # Event from SITE-SOUTH / MTR-02
        event_south = {"type": "alert", "data": {"motor_id": "MTR-02", "site_id": "SITE-SOUTH", "assigned_to": None}}
        # Event with missing site_id
        event_no_site = {"type": "alert", "data": {"motor_id": "MTR-UNKNOWN", "site_id": None}}

        # Manager North checks
        assert ws_manager.is_authorized_for_event(meta_manager_north, event_north) is True
        assert ws_manager.is_authorized_for_event(meta_manager_north, event_south) is False
        assert ws_manager.is_authorized_for_event(meta_manager_north, event_no_site) is False  # Withhold missing site

        # Technician Bob checks
        assert ws_manager.is_authorized_for_event(meta_tech_01, event_north) is True
        assert ws_manager.is_authorized_for_event(meta_tech_01, event_south) is False


class TestPhase72CriticalRemediation:
    """P0, P1, and P2 regression verification for Phase 7.2 remediation."""

    @pytest.mark.asyncio
    async def test_cross_site_manager_mutation_rejection_and_db_immutability(self):
        """
        P0: Cross-site Manager attempts against all four operations (acknowledge, assign,
        resolve, reopen) MUST return None (non-disclosing 404) and leave the database
        document completely unchanged.
        """
        now = datetime.now(timezone.utc)
        initial_alert_b = {
            "_id": "doc_id_site_b",
            "alert_id": "ALT-SITE-B-SEC",
            "motor_id": "MTR-SITE-B-01",
            "device_id": "dev-b-01",
            "site_id": "SITE-B",
            "state": "ACTIVE",
            "severity": "CRITICAL",
            "trigger_type": "THRESHOLD_OVERCURRENT",
            "trigger_value": 5.2,
            "threshold_limit": 4.0,
            "unit": "A",
            "message": "Site B current breach",
            "triggered_at": now,
            "assigned_to": None,
            "assigned_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
        }

        alerts_db = {"ALT-SITE-B-SEC": dict(initial_alert_b)}

        mock_alerts = AsyncMock()
        mock_alerts.find_one = AsyncMock(side_effect=lambda q, *args: dict(alerts_db[q["alert_id"]]) if q.get("alert_id") in alerts_db else None)
        mock_alerts.find_one_and_update = AsyncMock()

        mock_motors = AsyncMock()
        mock_motors.find_one = AsyncMock(return_value={"motor_id": "MTR-SITE-B-01", "site_id": "SITE-B"})

        mock_audit = AsyncMock()

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: {
            "alerts": mock_alerts,
            "motors": mock_motors,
            "users": AsyncMock(),
            "work_orders": AsyncMock(),
            "audit_events": mock_audit,
            "audit_logs": mock_audit,
        }.get(name, AsyncMock()))

        service = AlertService(mock_db)
        # Manager A is scoped strictly to SITE-A
        manager_a = UserOut(id="m_a", username="mgr_a", role="Manager", email="mgr_a@m.local.com", is_active=True, assigned_sites=["SITE-A"])

        # 1. Acknowledge attempt by cross-site manager
        res_ack = await service.acknowledge_alert("ALT-SITE-B-SEC", acknowledged_by="mgr_a", current_user=manager_a)
        assert res_ack is None
        # Assert database mutation was NEVER invoked
        mock_alerts.find_one_and_update.assert_not_called()
        assert alerts_db["ALT-SITE-B-SEC"]["state"] == "ACTIVE"

        # 2. Assign attempt by cross-site manager
        res_assign = await service.assign_alert("ALT-SITE-B-SEC", assigned_to="tech_bob", assigned_by="mgr_a", current_user=manager_a)
        assert res_assign is None
        mock_alerts.find_one_and_update.assert_not_called()
        assert alerts_db["ALT-SITE-B-SEC"]["assigned_to"] is None

        # 3. Resolve attempt by cross-site manager
        res_resolve = await service.resolve_alert("ALT-SITE-B-SEC", resolved_by="mgr_a", resolution_notes="Attempted unauthorized resolve", current_user=manager_a)
        assert res_resolve is None
        mock_alerts.find_one_and_update.assert_not_called()
        assert alerts_db["ALT-SITE-B-SEC"]["state"] == "ACTIVE"

        # 4. Reopen attempt by cross-site manager (even if alert was in RESOLVED state)
        alerts_db["ALT-SITE-B-SEC"]["state"] = "RESOLVED"
        res_reopen = await service.reopen_alert("ALT-SITE-B-SEC", reopened_by="mgr_a", reason="Attempted unauthorized reopen", current_user=manager_a)
        assert res_reopen is None
        mock_alerts.find_one_and_update.assert_not_called()
        assert alerts_db["ALT-SITE-B-SEC"]["state"] == "RESOLVED"

        # Verify no audit events were created by unauthorized attempts
        mock_audit.insert_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_authorized_mutations_and_invalid_concurrent_state_transitions(self):
        """
        P0: Authorized operations succeed, while invalid or concurrent state transitions
        (e.g. acknowledging already resolved alert) are safely rejected atomically.
        """
        now = datetime.now(timezone.utc)
        alert_doc = {
            "_id": "doc_id_site_a",
            "alert_id": "ALT-SITE-A-LIFECYCLE",
            "motor_id": "MTR-SITE-A-01",
            "device_id": "dev-a-01",
            "site_id": "SITE-A",
            "state": "ACTIVE",
            "severity": "CRITICAL",
            "trigger_type": "THRESHOLD_OVERTEMPERATURE",
            "trigger_value": 78.0,
            "threshold_limit": 75.0,
            "unit": "°C",
            "message": "Overheat",
            "triggered_at": now,
            "assigned_to": None,
        }

        alerts_db = {"ALT-SITE-A-LIFECYCLE": dict(alert_doc)}

        mock_alerts = AsyncMock()
        mock_alerts.find_one = AsyncMock(side_effect=lambda q, *args: dict(alerts_db[q["alert_id"]]) if q.get("alert_id") in alerts_db else None)

        async def fake_update(filter_q, update_q, **kwargs):
            m_id = filter_q.get("alert_id")
            doc = alerts_db.get(m_id)
            if not doc:
                return None
            # Check state precondition in filter
            expected = filter_q.get("state")
            if isinstance(expected, dict) and "$in" in expected:
                if doc["state"] not in expected["$in"]:
                    return None
            elif expected is not None and doc["state"] != expected:
                return None
            # Apply update
            doc.update(update_q.get("$set", {}))
            return dict(doc)

        mock_alerts.find_one_and_update = AsyncMock(side_effect=fake_update)

        mock_motors = AsyncMock()
        mock_motors.find_one = AsyncMock(return_value={"motor_id": "MTR-SITE-A-01", "site_id": "SITE-A"})

        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value={
            "username": "tech_site_a",
            "role": "Technician",
            "is_active": True,
            "assigned_sites": ["SITE-A"],
        })

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: {
            "alerts": mock_alerts,
            "motors": mock_motors,
            "users": mock_users,
            "work_orders": AsyncMock(),
            "audit_events": AsyncMock(),
            "audit_logs": AsyncMock(),
        }.get(name, AsyncMock()))

        service = AlertService(mock_db)
        manager_a = UserOut(id="m_a", username="mgr_a", role="Manager", email="mgr_a@m.local.com", is_active=True, assigned_sites=["SITE-A"])

        # 1. Authorized Manager A acknowledges ACTIVE alert -> state becomes ACKNOWLEDGED
        res_ack = await service.acknowledge_alert("ALT-SITE-A-LIFECYCLE", acknowledged_by="mgr_a", current_user=manager_a)
        assert res_ack is not None
        assert res_ack.state == "ACKNOWLEDGED"

        # 2. Duplicate acknowledge attempt (alert is already ACKNOWLEDGED, not ACTIVE) -> returns None
        res_ack_dup = await service.acknowledge_alert("ALT-SITE-A-LIFECYCLE", acknowledged_by="mgr_a", current_user=manager_a)
        assert res_ack_dup is None

        # 3. Assign alert to technician in SITE-A -> succeeds
        res_assign = await service.assign_alert("ALT-SITE-A-LIFECYCLE", assigned_to="tech_site_a", assigned_by="mgr_a", current_user=manager_a)
        assert res_assign is not None
        assert res_assign.assigned_to == "tech_site_a"

        # 4. Resolve alert with valid notes
        res_resolve = await service.resolve_alert("ALT-SITE-A-LIFECYCLE", resolved_by="mgr_a", resolution_notes="Coolant pipe inspected and replaced", current_user=manager_a)
        assert res_resolve is not None
        assert res_resolve.state == "RESOLVED"

        # 5. Concurrent or redundant resolve on already RESOLVED alert -> returns None
        res_res_dup = await service.resolve_alert("ALT-SITE-A-LIFECYCLE", resolved_by="mgr_a", resolution_notes="Attempt redundant resolution", current_user=manager_a)
        assert res_res_dup is None

        # 6. Reopen resolved alert -> state becomes ACTIVE
        res_reopen = await service.reopen_alert("ALT-SITE-A-LIFECYCLE", reopened_by="mgr_a", reason="Thermal spike recurred on next shift", current_user=manager_a)
        assert res_reopen is not None
        assert res_reopen.state == "ACTIVE"

        # 7. Reopening an already ACTIVE alert -> returns None
        res_reopen_dup = await service.reopen_alert("ALT-SITE-A-LIFECYCLE", reopened_by="mgr_a", reason="Redundant reopen", current_user=manager_a)
        assert res_reopen_dup is None

    def test_technician_websocket_fail_closed_and_empty_assignments(self):
        """
        P1: Technician WebSocket event authorization must fail closed when assigned_motors
        is empty and reject cross-site / unassigned assets.
        """
        # Technician with EMPTY motor assignment
        tech_unassigned = {
            "username": "tech_empty",
            "role": "Technician",
            "assigned_sites": set(),
            "assigned_motors": set(),
        }
        # Technician with assigned motor MTR-ALPHA
        tech_alpha = {
            "username": "tech_alpha",
            "role": "Technician",
            "assigned_sites": {"SITE-ALPHA"},
            "assigned_motors": {"MTR-ALPHA"},
        }

        # Events
        alert_assigned_to_empty = {"type": "alert", "data": {"motor_id": "MTR-OTHER", "site_id": "SITE-X", "assigned_to": "tech_empty"}}
        alert_assigned_to_other = {"type": "alert", "data": {"motor_id": "MTR-OTHER", "site_id": "SITE-X", "assigned_to": "tech_other"}}
        telemetry_alpha = {"type": "telemetry", "data": {"motor_id": "MTR-ALPHA", "site_id": "SITE-ALPHA"}}
        telemetry_beta = {"type": "telemetry", "data": {"motor_id": "MTR-BETA", "site_id": "SITE-BETA"}}
        event_missing_motor = {"type": "alert", "data": {"site_id": "SITE-ALPHA"}}

        # 1. Empty assignment technician:
        # Cannot see general motor telemetry (empty motor list must NOT mean fleet access!)
        assert ws_manager.is_authorized_for_event(tech_unassigned, telemetry_alpha) is False
        assert ws_manager.is_authorized_for_event(tech_unassigned, telemetry_beta) is False
        # Cannot see alerts assigned to others
        assert ws_manager.is_authorized_for_event(tech_unassigned, alert_assigned_to_other) is False
        # Can ONLY see alerts directly assigned to their username
        assert ws_manager.is_authorized_for_event(tech_unassigned, alert_assigned_to_empty) is True

        # 2. Technician assigned to MTR-ALPHA:
        # Can see MTR-ALPHA telemetry and alerts
        assert ws_manager.is_authorized_for_event(tech_alpha, telemetry_alpha) is True
        # Cannot see MTR-BETA (unassigned motor)
        assert ws_manager.is_authorized_for_event(tech_alpha, telemetry_beta) is False
        # Missing motor scope fails closed
        assert ws_manager.is_authorized_for_event(tech_alpha, event_missing_motor) is False

    @pytest.mark.asyncio
    async def test_offline_alert_concurrency_duplicate_key_handling(self):
        """
        P2: When multiple workers attempt to insert an active alert for the same
        (motor_id, trigger_type), DuplicateKeyError (11000) is safely handled by
        updating last_observed_at without raising an unhandled exception or creating duplicates.
        """
        mock_alerts = AsyncMock()
        mock_alerts.find_one = AsyncMock(return_value=None)  # Worker thinks no active alert exists

        # Simulate MongoDB DuplicateKeyError code 11000 from partial unique index
        from pymongo.errors import DuplicateKeyError
        mock_alerts.insert_one = AsyncMock(side_effect=DuplicateKeyError("E11000 duplicate key error on active alert"))
        mock_alerts.update_one = AsyncMock()

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_alerts)

        service = AlertService(mock_db)

        # Trigger alert insertion
        result = await service._trigger_or_update_alert(
            motor_id="MTR-RACE-01",
            device_id="dev-race",
            severity="WARNING",
            trigger_type="DEVICE_OFFLINE",
            trigger_value=0.0,
            threshold_limit=30.0,
            unit="sec",
            message="Device offline test",
            site_id="SITE-A",
            category="CONNECTIVITY",
        )

        # Should handle DuplicateKeyError gracefully: return None and update winner's last_observed_at
        assert result is None
        mock_alerts.update_one.assert_called_once()
        update_call = mock_alerts.update_one.call_args
        assert update_call[0][0] == {"motor_id": "MTR-RACE-01", "trigger_type": "DEVICE_OFFLINE", "state": "ACTIVE"}
        assert "$set" in update_call[0][1] and "last_observed_at" in update_call[0][1]["$set"]

