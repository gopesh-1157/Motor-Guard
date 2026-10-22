"""
Phase 4 Unit Tests — Work Orders Lifecycle & Audit Logging RBAC
- Work order creation & assignment scoped to Manager sites and valid active Technicians
- Work order lifecycle state transitions (Assigned -> Accepted -> In Progress -> Resolved / Rejected)
- Strict assignment isolation: only assigned Technician (or Admin) can transition
- Backend validation of resolution fields (root cause, corrective actions, notes, downtime)
- Audit log access: Admin sees all; Manager limited to operational/site events; Technician receives 403
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
from backend.app.services.work_order_service import WorkOrderService
from backend.app.api.v1.endpoints.work_orders import get_work_order_service
from backend.app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderResolveRequest,
    WorkOrderAcceptRequest,
    WorkOrderStartRequest,
)

client = TestClient(app)


def auth_header(username: str, role: str) -> dict:
    token = create_access_token(data={"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user():
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
def manager_user():
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
def unscoped_manager_user():
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
def tech_user():
    return UserInDB(
        id="65f123456789abcdef000004",
        username="tech_tom",
        email="tom@factory.local",
        role="Technician",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
        assigned_sites=["SITE-NORTH"],
        assigned_motors=["MTR-101"],
    )


@pytest.fixture
def other_tech_user():
    return UserInDB(
        id="65f123456789abcdef000005",
        username="tech_other",
        email="other@factory.local",
        role="Technician",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
        assigned_sites=["SITE-NORTH"],
        assigned_motors=["MTR-999"],
    )


def test_manager_work_order_creation_site_scoping(manager_user, tech_user):
    """Manager can only create work orders for motors within authorized site scope."""
    mock_user_svc = MagicMock(spec=UserService)
    mock_user_svc.get_by_username = AsyncMock(
        side_effect=lambda u: manager_user if u == manager_user.username else (
            tech_user if u == tech_user.username else None
        )
    )
    app.dependency_overrides[get_user_service] = lambda: mock_user_svc

    mock_db = MagicMock()
    mock_wo_col = MagicMock()
    mock_wo_col.insert_one = AsyncMock()
    mock_motors_col = MagicMock()
    mock_users_col = MagicMock()
    mock_alerts_col = MagicMock()
    mock_maintenance_col = MagicMock()
    mock_audit_col = MagicMock()
    mock_audit_col.insert_one = AsyncMock()

    mock_db.__getitem__.side_effect = lambda name: {
        "work_orders": mock_wo_col,
        "motors": mock_motors_col,
        "users": mock_users_col,
        "alerts": mock_alerts_col,
        "maintenance_records": mock_maintenance_col,
        "audit_logs": mock_audit_col,
    }[name]

    wo_svc = WorkOrderService(mock_db)
    app.dependency_overrides[get_work_order_service] = lambda: wo_svc

    try:
        # Motor in authorized site: SITE-NORTH
        mock_motors_col.find_one = AsyncMock(
            side_effect=lambda q: {"motor_id": "MTR-101", "site_id": "SITE-NORTH"} if q.get("motor_id") == "MTR-101" else (
                {"motor_id": "MTR-202", "site_id": "SITE-SOUTH"} if q.get("motor_id") == "MTR-202" else None
            )
        )
        mock_users_col.find_one = AsyncMock(return_value={
            "username": "tech_tom",
            "role": "Technician",
            "is_active": True,
            "assigned_sites": ["SITE-NORTH"],
        })

        # 1. Successful creation for authorized site
        res_ok = client.post(
            "/api/v1/work-orders",
            json={
                "motor_id": "MTR-101",
                "assigned_to_user_id": "tech_tom",
                "priority": "HIGH",
                "title": "Check Bearings",
                "description": "Vibration anomaly detected on Line 1",
            },
            headers=auth_header(manager_user.username, "Manager"),
        )
        assert res_ok.status_code == 201
        assert res_ok.json()["motor_id"] == "MTR-101"
        assert res_ok.json()["site_id"] == "SITE-NORTH"

        # 2. Rejection for unauthorized site (SITE-SOUTH)
        res_fail = client.post(
            "/api/v1/work-orders",
            json={
                "motor_id": "MTR-202",
                "assigned_to_user_id": "tech_tom",
                "priority": "HIGH",
                "title": "Fix Pump",
                "description": "Pump overheating on Sector 9",
            },
            headers=auth_header(manager_user.username, "Manager"),
        )
        assert res_fail.status_code == 403
        assert "Manager is not authorized to create work orders for motor at site 'SITE-SOUTH'" in res_fail.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_cannot_assign_to_deactivated_or_non_technician(manager_user):
    """Work orders cannot be assigned to inactive users or non-Technician roles."""
    mock_user_svc = MagicMock(spec=UserService)
    mock_user_svc.get_by_username = AsyncMock(return_value=manager_user)
    app.dependency_overrides[get_user_service] = lambda: mock_user_svc

    mock_db = MagicMock()
    mock_motors_col = MagicMock()
    mock_motors_col.find_one = AsyncMock(return_value={"motor_id": "MTR-101", "site_id": "SITE-NORTH"})
    mock_users_col = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "work_orders": MagicMock(),
        "motors": mock_motors_col,
        "users": mock_users_col,
        "alerts": MagicMock(),
        "maintenance_records": MagicMock(),
        "audit_logs": MagicMock(),
    }[name]

    wo_svc = WorkOrderService(mock_db)
    app.dependency_overrides[get_work_order_service] = lambda: wo_svc

    try:
        # Attempt to assign to inactive technician
        mock_users_col.find_one = AsyncMock(return_value={
            "username": "tech_inactive",
            "role": "Technician",
            "is_active": False,
        })
        res_inactive = client.post(
            "/api/v1/work-orders",
            json={
                "motor_id": "MTR-101",
                "assigned_to_user_id": "tech_inactive",
                "title": "Inspect Rotor",
                "description": "Routine rotor overhaul check",
            },
            headers=auth_header(manager_user.username, "Manager"),
        )
        assert res_inactive.status_code == 400
        assert "Cannot assign work order to deactivated technician" in res_inactive.json()["detail"]

        # Attempt to assign to a Manager
        mock_users_col.find_one = AsyncMock(return_value={
            "username": "manager_other",
            "role": "Manager",
            "is_active": True,
        })
        res_non_tech = client.post(
            "/api/v1/work-orders",
            json={
                "motor_id": "MTR-101",
                "assigned_to_user_id": "manager_other",
                "title": "Inspect Rotor",
                "description": "Routine rotor overhaul check",
            },
            headers=auth_header(manager_user.username, "Manager"),
        )
        assert res_non_tech.status_code == 400
        assert "only 'Technician' accounts can receive work orders" in res_non_tech.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_work_order_lifecycle_and_assignment_authorization(tech_user, other_tech_user):
    """
    State machine: Assigned -> Accepted -> In Progress -> Resolved.
    Strict authorization: non-assigned technicians receive HTTP 403.
    """
    mock_user_svc = MagicMock(spec=UserService)
    mock_user_svc.get_by_username = AsyncMock(
        side_effect=lambda u: tech_user if u == tech_user.username else (
            other_tech_user if u == other_tech_user.username else None
        )
    )
    app.dependency_overrides[get_user_service] = lambda: mock_user_svc

    now = datetime.now(timezone.utc)
    base_wo = {
        "work_order_id": "WO-20261022-A1B2C3",
        "motor_id": "MTR-101",
        "site_id": "SITE-NORTH",
        "assigned_to_user_id": "tech_tom",
        "assigned_by_user_id": "manager_mike",
        "priority": "HIGH",
        "title": "Fix Thermal Warning",
        "description": "Motor exceeds 45C limit",
        "status": "Assigned",
        "created_at": now,
        "updated_at": now,
    }

    mock_db = MagicMock()
    mock_wo_col = MagicMock()
    mock_alerts_col = MagicMock()
    mock_maintenance_col = MagicMock()
    mock_maintenance_col.insert_one = AsyncMock()
    mock_audit_col = MagicMock()
    mock_audit_col.insert_one = AsyncMock()

    mock_db.__getitem__.side_effect = lambda name: {
        "work_orders": mock_wo_col,
        "alerts": mock_alerts_col,
        "maintenance_records": mock_maintenance_col,
        "audit_logs": mock_audit_col,
        "users": MagicMock(),
        "motors": MagicMock(),
    }[name]

    wo_svc = WorkOrderService(mock_db)
    app.dependency_overrides[get_work_order_service] = lambda: wo_svc

    try:
        # Non-assigned technician tech_other attempts to accept WO -> 403
        mock_wo_col.find_one = AsyncMock(return_value=base_wo.copy())
        res_other = client.post(
            "/api/v1/work-orders/WO-20261022-A1B2C3/accept",
            headers=auth_header(other_tech_user.username, "Technician"),
        )
        assert res_other.status_code == 403

        # Assigned technician tech_tom accepts WO -> 200 (Assigned -> Accepted)
        accepted_wo = base_wo.copy()
        accepted_wo["status"] = "Accepted"
        accepted_wo["accepted_at"] = now
        mock_wo_col.find_one_and_update = AsyncMock(return_value=accepted_wo.copy())

        res_accept = client.post(
            "/api/v1/work-orders/WO-20261022-A1B2C3/accept",
            headers=auth_header(tech_user.username, "Technician"),
        )
        assert res_accept.status_code == 200
        assert res_accept.json()["status"] == "Accepted"

        # Technician starts WO -> 200 (Accepted -> In Progress)
        mock_wo_col.find_one = AsyncMock(return_value=accepted_wo.copy())
        in_progress_wo = accepted_wo.copy()
        in_progress_wo["status"] = "In Progress"
        in_progress_wo["started_at"] = now
        mock_wo_col.find_one_and_update = AsyncMock(return_value=in_progress_wo.copy())

        res_start = client.post(
            "/api/v1/work-orders/WO-20261022-A1B2C3/start",
            headers=auth_header(tech_user.username, "Technician"),
        )
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "In Progress"

        # Technician resolves WO with valid fields -> 200 (In Progress -> Resolved)
        mock_wo_col.find_one = AsyncMock(return_value=in_progress_wo.copy())
        resolved_wo = in_progress_wo.copy()
        resolved_wo["status"] = "Resolved"
        resolved_wo["resolved_at"] = now
        mock_wo_col.find_one_and_update = AsyncMock(return_value=resolved_wo.copy())

        res_resolve = client.post(
            "/api/v1/work-orders/WO-20261022-A1B2C3/resolve",
            json={
                "diagnosis": "Worn drive-side bearing causing friction",
                "actions_taken": "Replaced ball bearing and regreased",
                "parts_replaced": ["Deep groove ball bearing 608-2RS", "Lithium grease"],
                "downtime_minutes": 45,
                "resolution_notes": "Motor retested at 12V under conveyor load, thermal profile nominal at 34C",
            },
            headers=auth_header(tech_user.username, "Technician"),
        )
        assert res_resolve.status_code == 200
        assert res_resolve.json()["status"] == "Resolved"
        mock_maintenance_col.insert_one.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_backend_validation_of_maintenance_fields(tech_user):
    """Backend strictly validates diagnosis, actions, notes, and non-negative downtime."""
    mock_user_svc = MagicMock(spec=UserService)
    mock_user_svc.get_by_username = AsyncMock(return_value=tech_user)
    app.dependency_overrides[get_user_service] = lambda: mock_user_svc

    now = datetime.now(timezone.utc)
    in_progress_wo = {
        "work_order_id": "WO-20261022-A1B2C3",
        "motor_id": "MTR-101",
        "site_id": "SITE-NORTH",
        "assigned_to_user_id": "tech_tom",
        "assigned_by_user_id": "manager_mike",
        "priority": "HIGH",
        "title": "Fix Thermal Warning",
        "description": "Motor exceeds 45C limit",
        "status": "In Progress",
        "created_at": now,
        "updated_at": now,
    }

    mock_db = MagicMock()
    mock_wo_col = MagicMock()
    mock_wo_col.find_one = AsyncMock(return_value=in_progress_wo.copy())

    mock_db.__getitem__.side_effect = lambda name: {
        "work_orders": mock_wo_col,
        "alerts": MagicMock(),
        "maintenance_records": MagicMock(),
        "audit_logs": MagicMock(),
        "users": MagicMock(),
        "motors": MagicMock(),
    }[name]

    wo_svc = WorkOrderService(mock_db)
    app.dependency_overrides[get_work_order_service] = lambda: wo_svc

    try:
        # 1. Missing diagnosis (empty or whitespace)
        res_empty_diag = client.post(
            "/api/v1/work-orders/WO-20261022-A1B2C3/resolve",
            json={
                "diagnosis": "   ",
                "actions_taken": "Fixed it",
                "parts_replaced": [],
                "downtime_minutes": 10,
                "resolution_notes": "All good",
            },
            headers=auth_header(tech_user.username, "Technician"),
        )
        assert res_empty_diag.status_code == 400
        assert "Root cause diagnosis is required" in res_empty_diag.json()["detail"]

        # 2. Negative downtime
        res_neg_down = client.post(
            "/api/v1/work-orders/WO-20261022-A1B2C3/resolve",
            json={
                "diagnosis": "Worn bearing",
                "actions_taken": "Replaced bearing",
                "parts_replaced": [],
                "downtime_minutes": -15,
                "resolution_notes": "All good",
            },
            headers=auth_header(tech_user.username, "Technician"),
        )
        assert res_neg_down.status_code in (400, 422)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_audit_logs_role_scoping(admin_user, manager_user, tech_user):
    """
    Admin: Views all audit logs (including sensitive security events).
    Manager: Limited to authorized operational actions within their site scope.
    Technician: Blocked with HTTP 403.
    """
    mock_audit_col = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: mock_audit_col if name == "audit_logs" else MagicMock()

    wo_svc = WorkOrderService(mock_db)

    # 1. Technician cannot view audit logs
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_tech:
        await wo_svc.list_audit_logs(current_user=tech_user)
    assert exc_tech.value.status_code == 403
    assert "Technicians are not authorized to view audit logs" in exc_tech.value.detail

    # 2. Manager query restricts to operational actions and site scope
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.__aiter__.return_value = iter([])
    mock_audit_col.find = MagicMock(return_value=mock_cursor)

    await wo_svc.list_audit_logs(current_user=manager_user)
    called_query = mock_audit_col.find.call_args[0][0]
    assert "action" in called_query
    # Ensure USER_REGISTER / USER_DELETE is NOT in the allowed operational actions
    assert "USER_REGISTER" not in called_query["action"]["$in"]
    assert "USER_DELETE" not in called_query["action"]["$in"]
    assert "$or" in called_query

    # 3. Admin has unrestricted query
    mock_audit_col.find.reset_mock()
    await wo_svc.list_audit_logs(current_user=admin_user)
    admin_query = mock_audit_col.find.call_args[0][0]
    assert "action" not in admin_query  # Admin is unrestricted
