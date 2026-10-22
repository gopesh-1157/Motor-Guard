"""
Phase 3 Unit Tests — Motor and Device Management RBAC & Scoping
- Admin full access to motors and devices
- Manager scoped strictly to assigned_sites (creation, edit, device enrollment/assignment)
- Unscoped Manager blocked from fleet modifications
- Technician blocked from creating/editing motors and devices (403)
- Technician can only view assigned motors
- Enforce 1-to-1 device-motor association and rejection of duplicates
- Device unassign clears motor link cleanly
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.user import UserInDB
from backend.app.core.auth import get_user_service
from backend.app.core.security import create_access_token
from backend.app.services.user_service import UserService
from backend.app.services.motor_service import MotorService
from backend.app.services.device_service import DeviceService
from backend.app.api.v1.endpoints.motors import get_motor_service
from backend.app.api.v1.endpoints.devices import get_device_service

client = TestClient(app)


def auth_header(username: str, role: str) -> dict:
    token = create_access_token(data={"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_admin_user():
    return UserInDB(
        id="65f123456789abcdef000001",
        username="admin_alice",
        email="alice@factory.local",
        role="Admin",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )


@pytest.fixture
def mock_manager_user():
    return UserInDB(
        id="65f123456789abcdef000002",
        username="manager_mike",
        email="mike@factory.local",
        role="Manager",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
        assigned_sites=["SITE-NORTH"],
    )


@pytest.fixture
def mock_unscoped_manager_user():
    return UserInDB(
        id="65f123456789abcdef000003",
        username="manager_unscoped",
        email="unscoped@factory.local",
        role="Manager",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
        assigned_sites=[],
    )


@pytest.fixture
def mock_technician_user():
    return UserInDB(
        id="65f123456789abcdef000004",
        username="tech_tom",
        email="tom@factory.local",
        role="Technician",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
        assigned_motors=["MTR-ALLOWED-01"],
    )


def test_manager_site_scoping_on_motor_creation(mock_manager_user):
    """Manager can only create motors in their assigned sites."""
    mock_user_svc = MagicMock(spec=UserService)
    mock_user_svc.get_by_username = AsyncMock(return_value=mock_manager_user)
    app.dependency_overrides[get_user_service] = lambda: mock_user_svc

    mock_db = MagicMock()
    mock_motors_col = MagicMock()
    mock_audit_col = MagicMock()
    mock_audit_col.insert_one = AsyncMock()
    mock_devices_col = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "motors": mock_motors_col,
        "devices": mock_devices_col,
        "audit_events": mock_audit_col,
        "telemetry": MagicMock(),
    }[name]

    motor_svc = MotorService(mock_db)
    app.dependency_overrides[get_motor_service] = lambda: motor_svc

    try:
        # 1. Allowed site: SITE-NORTH
        mock_motors_col.find_one = AsyncMock(return_value=None)
        mock_motors_col.insert_one = AsyncMock()

        res_ok = client.post(
            "/api/v1/motors",
            json={
                "motor_id": "MTR-NORTH-101",
                "name": "North Pump Motor",
                "site_id": "SITE-NORTH",
                "location": "Sector 4",
                "motor_type": "RS-775 Brushed DC",
                "electrical_specs": {
                    "rated_voltage_v": 12.0,
                    "rated_current_a": 2.5,
                },
            },
            headers=auth_header(mock_manager_user.username, "Manager"),
        )
        assert res_ok.status_code == 201
        assert res_ok.json()["motor_id"] == "MTR-NORTH-101"

        # 2. Unauthorized site: SITE-SOUTH
        res_fail = client.post(
            "/api/v1/motors",
            json={
                "motor_id": "MTR-SOUTH-201",
                "name": "South Conveyor",
                "site_id": "SITE-SOUTH",
                "location": "Sector 9",
                "motor_type": "RS-775 Brushed DC",
                "electrical_specs": {
                    "rated_voltage_v": 12.0,
                    "rated_current_a": 2.5,
                },
            },
            headers=auth_header(mock_manager_user.username, "Manager"),
        )
        assert res_fail.status_code == 403
        assert "Manager is not authorized for site 'SITE-SOUTH'" in res_fail.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_unscoped_manager_cannot_create_motors(mock_unscoped_manager_user):
    """An unscoped manager must receive HTTP 403 when attempting to create motors."""
    mock_user_svc = MagicMock(spec=UserService)
    mock_user_svc.get_by_username = AsyncMock(return_value=mock_unscoped_manager_user)
    app.dependency_overrides[get_user_service] = lambda: mock_user_svc

    mock_db = MagicMock()
    motor_svc = MotorService(mock_db)
    app.dependency_overrides[get_motor_service] = lambda: motor_svc

    try:
        res = client.post(
            "/api/v1/motors",
            json={
                "motor_id": "MTR-ANY-001",
                "name": "Any Motor",
                "site_id": "SITE-PLANT-A",
                "location": "Line 1",
                "motor_type": "RS-775 Brushed DC",
                "electrical_specs": {
                    "rated_voltage_v": 12.0,
                    "rated_current_a": 2.5,
                },
            },
            headers=auth_header(mock_unscoped_manager_user.username, "Manager"),
        )
        assert res.status_code == 403
        assert "Unscoped Manager cannot register motors" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_technician_cannot_create_or_modify_motor(mock_technician_user):
    """Technicians receive 403 on motor creation or configuration modifications."""
    mock_user_svc = MagicMock(spec=UserService)
    mock_user_svc.get_by_username = AsyncMock(return_value=mock_technician_user)
    app.dependency_overrides[get_user_service] = lambda: mock_user_svc

    mock_db = MagicMock()
    motor_svc = MotorService(mock_db)
    app.dependency_overrides[get_motor_service] = lambda: motor_svc

    try:
        # Create motor -> 403
        res_create = client.post(
            "/api/v1/motors",
            json={
                "motor_id": "MTR-TECH-001",
                "name": "Tech Motor",
                "site_id": "SITE-PLANT-A",
                "location": "Line 1",
                "motor_type": "RS-775 Brushed DC",
                "electrical_specs": {
                    "rated_voltage_v": 12.0,
                    "rated_current_a": 2.5,
                },
            },
            headers=auth_header(mock_technician_user.username, "Technician"),
        )
        assert res_create.status_code == 403

        # Update motor -> 403
        res_update = client.patch(
            "/api/v1/motors/MTR-ALLOWED-01",
            json={"location": "New Location"},
            headers=auth_header(mock_technician_user.username, "Technician"),
        )
        assert res_update.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_technician_motor_visibility_scoping(mock_technician_user):
    """Technician can only retrieve motors assigned to them."""
    mock_user_svc = MagicMock(spec=UserService)
    mock_user_svc.get_by_username = AsyncMock(return_value=mock_technician_user)
    app.dependency_overrides[get_user_service] = lambda: mock_user_svc

    now = datetime.now(timezone.utc)
    mock_motors_col = MagicMock()
    mock_telem_col = MagicMock()
    mock_telem_col.find_one = AsyncMock(return_value=None)
    mock_wo_col = MagicMock()
    mock_wo_col.find_one = AsyncMock(return_value=None)

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "motors": mock_motors_col,
        "telemetry": mock_telem_col,
        "work_orders": mock_wo_col,
        "system_settings": MagicMock(),
        "alerts": MagicMock(),
        "devices": MagicMock(),
        "audit_events": MagicMock(),
    }[name]

    motor_svc = MotorService(mock_db)
    app.dependency_overrides[get_motor_service] = lambda: motor_svc

    try:
        # 1. Allowed motor doc
        allowed_doc = {
            "motor_id": "MTR-ALLOWED-01",
            "name": "Permitted Motor",
            "site_id": "SITE-PLANT-A",
            "motor_type": "RS-775 Brushed DC",
            "status": "active",
            "electrical_specs": {
                "rated_voltage_v": 12.0,
                "rated_current_a": 2.5,
            },
            "mechanical_specs": {},
            "sensors_config": {},
            "thresholds": {},
            "edge_impulse_config": {},
            "configuration_version": 1,
            "created_at": now,
            "updated_at": now,
        }
        forbidden_doc = {
            "motor_id": "MTR-FORBIDDEN-99",
            "name": "Secret Motor",
            "site_id": "SITE-PLANT-B",
            "motor_type": "RS-775 Brushed DC",
            "status": "active",
            "electrical_specs": {
                "rated_voltage_v": 12.0,
                "rated_current_a": 2.5,
            },
            "mechanical_specs": {},
            "sensors_config": {},
            "thresholds": {},
            "edge_impulse_config": {},
            "configuration_version": 1,
            "created_at": now,
            "updated_at": now,
        }
        mock_motors_col.find_one = AsyncMock(
            side_effect=lambda q, *args, **kwargs: allowed_doc.copy() if q.get("motor_id") == "MTR-ALLOWED-01" else (
                forbidden_doc.copy() if q.get("motor_id") == "MTR-FORBIDDEN-99" else None
            )
        )

        res_allowed = client.get(
            "/api/v1/motors/MTR-ALLOWED-01",
            headers=auth_header(mock_technician_user.username, "Technician"),
        )
        assert res_allowed.status_code == 200
        assert res_allowed.json()["motor_id"] == "MTR-ALLOWED-01"

        # 2. Forbidden motor doc
        res_forbidden = client.get(
            "/api/v1/motors/MTR-FORBIDDEN-99",
            headers=auth_header(mock_technician_user.username, "Technician"),
        )
        assert res_forbidden.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_device_1_to_1_assignment_and_conflict_rejection():
    """Verify 1-to-1 ESP32 device to motor assignment prevents duplicate assignments and unassigns cleanly."""
    mock_devices_col = MagicMock()
    mock_motors_col = MagicMock()
    mock_audit_col = MagicMock()
    mock_audit_col.insert_one = AsyncMock()

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "devices": mock_devices_col,
        "motors": mock_motors_col,
        "audit_events": mock_audit_col,
    }[name]

    dev_svc = DeviceService(mock_db)
    now = datetime.now(timezone.utc)

    # Device A already assigned to Motor 1
    dev_a = {
        "device_id": "esp32-node-A",
        "device_type": "ESP32",
        "board_variant": "NodeMCU-32S",
        "firmware_version": "1.0.0",
        "site_id": "SITE-MAIN",
        "assigned_motor_id": "MTR-001",
        "mqtt_client_id": "client-esp32-node-A",
        "enrollment_status": "enrolled",
        "availability": "unknown",
        "last_seen": None,
        "configuration_version": 1,
        "created_at": now,
        "updated_at": now,
    }
    # Device B unassigned
    dev_b = {
        "device_id": "esp32-node-B",
        "device_type": "ESP32",
        "board_variant": "NodeMCU-32S",
        "firmware_version": "1.0.0",
        "site_id": "SITE-MAIN",
        "assigned_motor_id": None,
        "mqtt_client_id": "client-esp32-node-B",
        "enrollment_status": "enrolled",
        "availability": "unknown",
        "last_seen": None,
        "configuration_version": 1,
        "created_at": now,
        "updated_at": now,
    }
    # Motor 1 already assigned to Device A
    mtr_1 = {
        "motor_id": "MTR-001",
        "assigned_device_id": "esp32-node-A",
        "site_id": "SITE-MAIN",
    }
    # Motor 2 unassigned
    mtr_2 = {
        "motor_id": "MTR-002",
        "assigned_device_id": None,
        "site_id": "SITE-MAIN",
    }

    mock_devices_col.find_one = AsyncMock(
        side_effect=lambda q, *args, **kwargs: dev_a.copy() if q.get("device_id") == "esp32-node-A" else (
            dev_b.copy() if q.get("device_id") == "esp32-node-B" else None
        )
    )
    mock_motors_col.find_one = AsyncMock(
        side_effect=lambda q, *args, **kwargs: mtr_1.copy() if q.get("motor_id") == "MTR-001" else (
            mtr_2.copy() if q.get("motor_id") == "MTR-002" else None
        )
    )

    from fastapi import HTTPException
    # 1. Attempt to assign Device A (already assigned to MTR-001) to MTR-002 -> Fail 400
    with pytest.raises(HTTPException) as exc_1:
        await dev_svc.assign_device("esp32-node-A", "MTR-002", username="admin")
    assert exc_1.value.status_code == 400
    assert "already assigned to motor 'MTR-001'" in exc_1.value.detail

    # 2. Attempt to assign Device B to Motor 1 (which already has Device A) -> Fail 400
    with pytest.raises(HTTPException) as exc_2:
        await dev_svc.assign_device("esp32-node-B", "MTR-001", username="admin")
    assert exc_2.value.status_code == 400
    assert "already assigned to device 'esp32-node-A'" in exc_2.value.detail

    # 3. Assign Device B to Motor 2 -> Success
    mock_devices_col.update_one = AsyncMock()
    mock_motors_col.update_one = AsyncMock()
    assigned_dev_b = dev_b.copy()
    assigned_dev_b["assigned_motor_id"] = "MTR-002"

    mock_devices_col.find_one = AsyncMock(
        side_effect=lambda q, *args, **kwargs: dev_b.copy() if mock_devices_col.update_one.call_count == 0 else assigned_dev_b.copy()
    )

    res_assign = await dev_svc.assign_device("esp32-node-B", "MTR-002", username="admin")
    assert res_assign.assigned_motor_id == "MTR-002"
    mock_devices_col.update_one.assert_called_once()
    mock_motors_col.update_one.assert_called_once()

    # 4. Unassign Device B -> Clears motor link cleanly
    unassigned_dev_b = dev_b.copy()
    unassigned_dev_b["assigned_motor_id"] = None
    mock_devices_col.update_one.reset_mock()
    mock_motors_col.update_one.reset_mock()

    mock_devices_col.find_one = AsyncMock(
        side_effect=lambda q, *args, **kwargs: assigned_dev_b.copy() if mock_devices_col.update_one.call_count == 0 else unassigned_dev_b.copy()
    )

    res_unassign = await dev_svc.unassign_device("esp32-node-B", username="admin")
    assert res_unassign.assigned_motor_id is None
    mock_devices_col.update_one.assert_called_once()
    mock_motors_col.update_one.assert_called_once()
