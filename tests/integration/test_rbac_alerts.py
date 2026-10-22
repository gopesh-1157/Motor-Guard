"""
MotorGuard — Phase 4 Acceptance Tests: RBAC, Alerts & Maintenance Records

Verifies:
  1. Users authenticate with username and password, receiving signed JWT tokens.
  2. Role hierarchy enforced on server: Operator cannot access user management
     or create maintenance records; Technician & Admin can.
  3. Simulated threshold violation triggers an active alert record in MongoDB.
  4. Technician user can acknowledge and resolve alerts with technician notes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.security import get_password_hash, verify_password, create_access_token
from backend.app.core.auth import get_user_service
from backend.app.api.v1.endpoints.maintenance import get_maintenance_service
from backend.app.services.user_service import UserService
from backend.app.services.alert_service import AlertService
from backend.app.services.maintenance_service import MaintenanceService
from backend.app.schemas.user import UserInDB, UserOut
from backend.app.schemas.maintenance import MaintenanceRecordOut


client = TestClient(app)


# ---- 1. JWT Authentication Tests --------------------------------------------

class TestJWTAuthentication:
    """Verifies user authentication, bcrypt hashing, and JWT token issuance."""

    def test_password_hashing(self):
        """Verify bcrypt password hashing and verification."""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_login_success_returns_jwt_token(self):
        """Valid login returns signed JWT bearer token and user object."""
        mock_user = UserInDB(
            id="65f123456789abcdef012345",
            username="tech_dave",
            email="dave@factory.local",
            role="Technician",
            password_hash=get_password_hash("technicianPass!"),
            created_at=datetime.now(timezone.utc),
            is_active=True,
            assigned_sites=["SITE-A"],
            assigned_motors=["MTR-001"],
        )

        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.authenticate = AsyncMock(return_value=mock_user)
        app.dependency_overrides[get_user_service] = lambda: mock_user_service

        try:
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "tech_dave", "password": "technicianPass!"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["user"]["username"] == "tech_dave"
            assert data["user"]["role"] == "Technician"
        finally:
            app.dependency_overrides.clear()

    def test_login_invalid_credentials_rejected(self):
        """Invalid credentials return 401 Unauthorized."""
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.authenticate = AsyncMock(return_value=None)
        app.dependency_overrides[get_user_service] = lambda: mock_user_service

        try:
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "unknown_user", "password": "badpassword"},
            )
            assert response.status_code == 401
            assert "Incorrect username or password" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_auth_me_endpoint_with_valid_jwt(self):
        """GET /api/v1/auth/me returns profile for valid JWT bearer token."""
        mock_user = UserInDB(
            id="65f123456789abcdef012345",
            username="tech_bob",
            email="bob@factory.local",
            role="Technician",
            password_hash="hash",
            created_at=datetime.now(timezone.utc),
            is_active=True,
            assigned_sites=["SITE-B"],
            assigned_motors=["MTR-002"],
        )

        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_by_username = AsyncMock(return_value=mock_user)
        app.dependency_overrides[get_user_service] = lambda: mock_user_service

        try:
            token = create_access_token({"sub": "tech_bob", "role": "Technician"})
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["username"] == "tech_bob"
            assert data["role"] == "Technician"
        finally:
            app.dependency_overrides.clear()


# ---- 2. Role-Based Access Control (RBAC) Tests ------------------------------

class TestRoleBasedAccessControl:
    """Verifies server-enforced role hierarchy on sensitive administrative & maintenance operations."""

    def test_operator_forbidden_from_user_management(self):
        """Technician cannot access Admin-only user management endpoint."""
        mock_user = UserInDB(
            id="65f123456789abcdef012345",
            username="tech_jim",
            email="jim@factory.local",
            role="Technician",
            password_hash="hash",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_by_username = AsyncMock(return_value=mock_user)
        app.dependency_overrides[get_user_service] = lambda: mock_user_service

        try:
            token = create_access_token({"sub": "tech_jim", "role": "Technician"})
            response = client.get(
                "/api/v1/auth/users",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 403
            assert "Operation requires role in" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_operator_forbidden_from_creating_maintenance_records(self):
        """Manager cannot create maintenance records directly (Requires Technician or Admin)."""
        mock_user = UserInDB(
            id="65f123456789abcdef012345",
            username="manager_jim",
            email="jim@factory.local",
            role="Manager",
            password_hash="hash",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_by_username = AsyncMock(return_value=mock_user)
        app.dependency_overrides[get_user_service] = lambda: mock_user_service

        try:
            token = create_access_token({"sub": "manager_jim", "role": "Manager"})
            maintenance_payload = {
                "motor_id": "MTR-775-001",
                "service_type": "INSPECTION",
                "summary": "Routine check",
                "details": "Inspected bearing housing",
                "downtime_minutes": 10,
            }

            response = client.post(
                "/api/v1/maintenance/motors/MTR-775-001",
                json=maintenance_payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 403
            assert "Operation requires role in" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_technician_permitted_to_create_maintenance_records(self):
        """Technician role can successfully log maintenance records."""
        mock_user = UserInDB(
            id="65f123456789abcdef012345",
            username="tech_sara",
            email="sara@factory.local",
            role="Technician",
            password_hash="hash",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_by_username = AsyncMock(return_value=mock_user)
        app.dependency_overrides[get_user_service] = lambda: mock_user_service

        mock_record_out = MaintenanceRecordOut(
            id="65f123456789abcdef012345",
            record_id="MAINT-202610-001",
            motor_id="MTR-775-001",
            service_type="LUBRICATION",
            summary="Bearing grease replenishment",
            details="Injected 5g high-temperature synthetic grease",
            parts_replaced=[],
            downtime_minutes=15,
            technician_id="tech_sara",
            technician_name="tech_sara",
            timestamp=datetime.now(timezone.utc),
        )
        mock_maint_service = MagicMock(spec=MaintenanceService)
        mock_maint_service.create_record = AsyncMock(return_value=mock_record_out)
        app.dependency_overrides[get_maintenance_service] = lambda: mock_maint_service

        try:
            token = create_access_token({"sub": "tech_sara", "role": "Technician"})
            maintenance_payload = {
                "motor_id": "MTR-775-001",
                "service_type": "LUBRICATION",
                "summary": "Bearing grease replenishment",
                "details": "Injected 5g high-temperature synthetic grease",
                "parts_replaced": [],
                "downtime_minutes": 15,
            }

            response = client.post(
                "/api/v1/maintenance/motors/MTR-775-001",
                json=maintenance_payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 201
            mock_maint_service.create_record.assert_called_once()
        finally:
            app.dependency_overrides.clear()


# ---- 3. Automated Threshold Alerts Engine Tests -----------------------------

class TestThresholdAlertsEngine:
    """Verifies simulated threshold violations trigger active alert records in MongoDB."""

    @pytest.mark.asyncio
    async def test_overcurrent_triggers_critical_alert(self):
        """Current reading > 4.0A generates THRESHOLD_OVERCURRENT critical alert."""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)  # No active alert yet
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alert123"))

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)

        telemetry = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 5.4, "temperature_c": 35.0, "vibration_g_rms": 0.08},
            "inference": {"health_status": "healthy", "confidence": 0.95},
        }

        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        assert len(alerts) == 1
        assert alerts[0].trigger_type == "THRESHOLD_OVERCURRENT"
        assert alerts[0].severity == "CRITICAL"
        assert alerts[0].trigger_value == 5.4
        assert alerts[0].threshold_limit == 4.0
        assert alerts[0].state == "ACTIVE"
        mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_overtemperature_triggers_thermal_alert(self):
        """Temperature > 50.0°C generates THRESHOLD_OVERTEMPERATURE alert."""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alert456"))

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)

        telemetry = {
            "motor_id": "MTR-775-002",
            "device_id": "esp32-node-002",
            "sensors": {"current_a": 2.1, "temperature_c": 58.5, "vibration_g_rms": 0.05},
            "inference": {"health_status": "warning", "confidence": 0.88},
        }

        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        assert len(alerts) == 1
        assert alerts[0].trigger_type == "THRESHOLD_OVERTEMPERATURE"
        assert alerts[0].severity == "WARNING"
        assert alerts[0].trigger_value == 58.5

    @pytest.mark.asyncio
    async def test_continuous_violation_de_duplicated(self):
        """Subsequent violations update existing ACTIVE alert rather than inserting duplicates."""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value={"_id": "existing_alert_id", "state": "ACTIVE"})
        mock_collection.update_one = AsyncMock()
        mock_collection.insert_one = AsyncMock()

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)

        telemetry = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 5.6, "temperature_c": 35.0, "vibration_g_rms": 0.08},
            "inference": {"health_status": "healthy", "confidence": 0.95},
        }

        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        assert len(alerts) == 0  # No new alert returned because existing was updated
        mock_collection.update_one.assert_called_once()
        mock_collection.insert_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_shaking_vibration_triggers_warning_alert(self):
        """Vibration RMS > 0.100g generates a metric-specific RMS alert."""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alert_vib_1"))

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)

        telemetry = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 1.2, "temperature_c": 30.0, "vibration_g_rms": 0.145},
            "inference": {"health_status": "healthy", "confidence": 0.90},
        }

        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        assert len(alerts) == 1
        assert alerts[0].trigger_type == "THRESHOLD_HIGH_VIBRATION_RMS"
        assert alerts[0].severity == "WARNING"
        assert alerts[0].trigger_value == 0.145
        assert alerts[0].threshold_limit == 0.100
        mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_peak_vibration_shock_triggers_alert(self):
        """Instantaneous peak shock creates an independent peak alert even if RMS is low."""
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alert_vib_peak"))

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)

        telemetry = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 1.0, "temperature_c": 28.0, "vibration_g_rms": 0.060, "vibration_g_peak": 0.520},
            "inference": {"health_status": "healthy", "confidence": 0.92},
        }

        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        assert len(alerts) == 1
        assert alerts[0].trigger_type == "THRESHOLD_HIGH_VIBRATION_PEAK"
        assert alerts[0].trigger_value == 0.520
        assert alerts[0].threshold_limit == 0.350

    @pytest.mark.asyncio
    async def test_vibration_normalization_auto_resolves_and_allows_retrigger(self):
        """When vibration drops back to baseline, alert auto-resolves, allowing future shakes to re-trigger."""
        now = datetime.now(timezone.utc)
        mock_collection = AsyncMock()
        def fake_find_one_and_update(filter_query, update_query, **kwargs):
            if filter_query.get("trigger_type") == "THRESHOLD_HIGH_VIBRATION_RMS":
                return {
                    "_id": "alert_obj_1",
                    "alert_id": "ALT-20261018-001",
                    "motor_id": "MTR-775-001",
                    "device_id": "esp32-node-001",
                    "severity": "WARNING",
                    "trigger_type": "THRESHOLD_HIGH_VIBRATION_RMS",
                    "trigger_value": 0.030,
                    "threshold_limit": 0.100,
                    "unit": "g",
                    "message": "Dynamic vibration normalized",
                    "state": "RESOLVED",
                    "triggered_at": now,
                    "acknowledged_at": None,
                    "acknowledged_by": None,
                    "resolved_at": now,
                    "resolved_by": "System (Auto-Normalized)",
                    "resolution_notes": "Dynamic vibration normalized",
                }
            return None

        mock_collection.find_one_and_update = AsyncMock(side_effect=fake_find_one_and_update)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)

        # Baseline safe telemetry
        telemetry_safe = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 1.0, "temperature_c": 28.0, "vibration_g_rms": 0.030},
            "inference": {"health_status": "healthy", "confidence": 0.95},
        }

        alerts = await service.evaluate_telemetry_for_alerts(telemetry_safe)
        assert len(alerts) == 0
        auto_resolved = service.consume_auto_resolved_alerts()
        assert len(auto_resolved) == 1
        assert auto_resolved[0].state == "RESOLVED"
        assert auto_resolved[0].trigger_type == "THRESHOLD_HIGH_VIBRATION_RMS"

    @pytest.mark.asyncio
    async def test_overcurrent_normalization_auto_resolves(self):
        """When armature current drops below 90% limit, active overcurrent alert is auto-resolved."""
        now = datetime.now(timezone.utc)
        mock_collection = AsyncMock()
        def fake_find_one_and_update(filter_query, update_query, **kwargs):
            if filter_query.get("trigger_type") == "THRESHOLD_OVERCURRENT":
                return {
                    "_id": "alert_curr_1",
                    "alert_id": "ALT-CURR-001",
                    "motor_id": "MTR-775-001",
                    "device_id": "esp32-node-001",
                    "severity": "CRITICAL",
                    "trigger_type": "THRESHOLD_OVERCURRENT",
                    "trigger_value": 1.5,
                    "threshold_limit": 4.0,
                    "unit": "A",
                    "message": "Armature current normalized",
                    "state": "RESOLVED",
                    "triggered_at": now,
                    "acknowledged_at": None,
                    "acknowledged_by": None,
                    "resolved_at": now,
                    "resolved_by": "System (Auto-Normalized)",
                    "resolution_notes": "Armature current normalized",
                }
            return None

        mock_collection.find_one_and_update = AsyncMock(side_effect=fake_find_one_and_update)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)
        telemetry = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 1.5, "temperature_c": 30.0, "vibration_g_rms": 0.04},
            "inference": {"health_status": "healthy", "confidence": 0.95},
        }

        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        assert len(alerts) == 0
        auto_resolved = service.consume_auto_resolved_alerts()
        assert len(auto_resolved) == 1
        assert auto_resolved[0].trigger_type == "THRESHOLD_OVERCURRENT"
        assert auto_resolved[0].state == "RESOLVED"

    @pytest.mark.asyncio
    async def test_overtemperature_normalization_auto_resolves(self):
        """When temperature cools down below limit - 2°C, active thermal alert is auto-resolved."""
        now = datetime.now(timezone.utc)
        mock_collection = AsyncMock()
        def fake_find_one_and_update(filter_query, update_query, **kwargs):
            if filter_query.get("trigger_type") == "THRESHOLD_OVERTEMPERATURE":
                return {
                    "_id": "alert_temp_1",
                    "alert_id": "ALT-TEMP-001",
                    "motor_id": "MTR-775-001",
                    "device_id": "esp32-node-001",
                    "severity": "WARNING",
                    "trigger_type": "THRESHOLD_OVERTEMPERATURE",
                    "trigger_value": 35.0,
                    "threshold_limit": 50.0,
                    "unit": "°C",
                    "message": "Temperature normalized",
                    "state": "RESOLVED",
                    "triggered_at": now,
                    "acknowledged_at": None,
                    "acknowledged_by": None,
                    "resolved_at": now,
                    "resolved_by": "System (Auto-Normalized)",
                    "resolution_notes": "Temperature normalized",
                }
            return None

        mock_collection.find_one_and_update = AsyncMock(side_effect=fake_find_one_and_update)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)
        telemetry = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 1.0, "temperature_c": 35.0, "vibration_g_rms": 0.04},
            "inference": {"health_status": "healthy", "confidence": 0.95},
        }

        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        assert len(alerts) == 0
        auto_resolved = service.consume_auto_resolved_alerts()
        assert len(auto_resolved) == 1
        assert auto_resolved[0].trigger_type == "THRESHOLD_OVERTEMPERATURE"
        assert auto_resolved[0].state == "RESOLVED"

    @pytest.mark.asyncio
    async def test_tinyml_inference_fault_auto_resolves_when_healthy(self):
        """When Edge TinyML returns to healthy state, active critical inference fault is auto-resolved."""
        now = datetime.now(timezone.utc)
        mock_collection = AsyncMock()
        def fake_find_one_and_update(filter_query, update_query, **kwargs):
            if filter_query.get("trigger_type") == "CRITICAL_INFERENCE_FAULT":
                return {
                    "_id": "alert_ai_1",
                    "alert_id": "ALT-AI-001",
                    "motor_id": "MTR-775-001",
                    "device_id": "esp32-node-001",
                    "severity": "CRITICAL",
                    "trigger_type": "CRITICAL_INFERENCE_FAULT",
                    "trigger_value": 0.95,
                    "threshold_limit": 0.5,
                    "unit": "confidence",
                    "message": "Edge TinyML normalized to healthy",
                    "state": "RESOLVED",
                    "triggered_at": now,
                    "acknowledged_at": None,
                    "acknowledged_by": None,
                    "resolved_at": now,
                    "resolved_by": "System (Auto-Normalized)",
                    "resolution_notes": "Edge TinyML model status normalized to healthy",
                }
            return None

        mock_collection.find_one_and_update = AsyncMock(side_effect=fake_find_one_and_update)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)
        telemetry = {
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "sensors": {"current_a": 1.0, "temperature_c": 30.0, "vibration_g_rms": 0.04},
            "inference": {"health_status": "healthy", "confidence": 0.95},
        }

        alerts = await service.evaluate_telemetry_for_alerts(telemetry)
        assert len(alerts) == 0
        auto_resolved = service.consume_auto_resolved_alerts()
        assert len(auto_resolved) == 1
        assert auto_resolved[0].trigger_type == "CRITICAL_INFERENCE_FAULT"
        assert auto_resolved[0].state == "RESOLVED"


# ---- 4. Alert Lifecycle (Acknowledge & Resolve) Tests ------------------------

class TestAlertLifecycle:
    """Verifies Technician can acknowledge and resolve alerts with required resolution notes."""

    @pytest.mark.asyncio
    async def test_technician_acknowledges_active_alert(self):
        """Active alert can be transitioned to ACKNOWLEDGED state."""
        mock_collection = AsyncMock()
        now = datetime.now(timezone.utc)
        mock_collection.find_one_and_update = AsyncMock(return_value={
            "_id": "alert_obj_id",
            "alert_id": "ALT-20261009-001",
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "severity": "CRITICAL",
            "trigger_type": "THRESHOLD_OVERCURRENT",
            "trigger_value": 4.5,
            "threshold_limit": 4.0,
            "unit": "A",
            "message": "Overcurrent trip",
            "state": "ACKNOWLEDGED",
            "triggered_at": now,
            "acknowledged_at": now,
            "acknowledged_by": "tech_dave",
            "resolved_at": None,
            "resolved_by": None,
            "resolution_notes": None,
        })

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)
        acknowledged = await service.acknowledge_alert("ALT-20261009-001", "tech_dave")

        assert acknowledged is not None
        assert acknowledged.state == "ACKNOWLEDGED"
        assert acknowledged.acknowledged_by == "tech_dave"

    @pytest.mark.asyncio
    async def test_technician_resolves_alert_with_notes(self):
        """Acknowledged alert can be transitioned to RESOLVED state with technician notes."""
        mock_collection = AsyncMock()
        now = datetime.now(timezone.utc)
        mock_collection.find_one_and_update = AsyncMock(return_value={
            "_id": "alert_obj_id",
            "alert_id": "ALT-20261009-001",
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "severity": "CRITICAL",
            "trigger_type": "THRESHOLD_OVERCURRENT",
            "trigger_value": 4.5,
            "threshold_limit": 4.0,
            "unit": "A",
            "message": "Overcurrent trip",
            "state": "RESOLVED",
            "triggered_at": now,
            "acknowledged_at": now,
            "acknowledged_by": "tech_dave",
            "resolved_at": now,
            "resolved_by": "tech_dave",
            "resolution_notes": "Replaced jammed drive belt and tested idle current at 1.2 A.",
        })

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = AlertService(mock_db)
        resolved = await service.resolve_alert(
            alert_id="ALT-20261009-001",
            resolved_by="tech_dave",
            resolution_notes="Replaced jammed drive belt and tested idle current at 1.2 A.",
        )

        assert resolved is not None
        assert resolved.state == "RESOLVED"
        assert resolved.resolved_by == "tech_dave"
        assert "Replaced jammed drive belt" in resolved.resolution_notes
