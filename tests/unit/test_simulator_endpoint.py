"""
MotorGuard — Unit tests for Simulator Endpoint & RBAC Protection
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.schemas.user import UserOut
from backend.app.core.auth import get_current_active_user, require_roles

client = TestClient(app)


def test_simulator_unauthenticated_rejected():
    """Unauthenticated calls to simulator endpoints must return 401 Unauthorized."""
    # Ensure no active overrides
    app.dependency_overrides.clear()

    res_status = client.get("/api/v1/simulator/status")
    assert res_status.status_code == 401
    assert "WWW-Authenticate" in res_status.headers

    res_inject = client.post("/api/v1/simulator/inject", json={"motor_id": "MTR-775-002", "condition": "healthy"})
    assert res_inject.status_code == 401


def test_simulator_status_authenticated():
    """Authenticated user can view simulator status and virtual node topology."""
    mock_user = UserOut(
        id="usr-test",
        username="technician_bob",
        email="bob@factory.local",
        role="Technician",
        assigned_sites=["SITE-MAIN"],
        assigned_motors=[],
        is_active=True,
    )
    app.dependency_overrides[get_current_active_user] = lambda: mock_user

    try:
        response = client.get("/api/v1/simulator/status")
        assert response.status_code == 200
        data = response.json()
        assert "active_profile" in data
        assert "available_profiles" in data
        assert "virtual_devices" in data
        assert len(data["virtual_devices"]) >= 3
    finally:
        app.dependency_overrides.clear()


def test_simulator_operator_forbidden_from_injection():
    """Technician receives 403 Forbidden when attempting to inject simulated faults."""
    mock_op = UserOut(
        id="usr-tech",
        username="technician_bob",
        email="bob@factory.local",
        role="Technician",
        assigned_sites=["SITE-MAIN"],
        assigned_motors=[],
        is_active=True,
    )
    app.dependency_overrides[get_current_active_user] = lambda: mock_op

    payload = {
        "motor_id": "MTR-775-002",
        "device_id": "sim-node-002",
        "condition": "warning_temp",
    }
    try:
        response = client.post("/api/v1/simulator/inject", json=payload)
        assert response.status_code == 403
        assert "Operation requires role" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_simulator_admin_can_inject_condition():
    """Admin or Manager clearance successfully injects fault condition."""
    mock_admin = UserOut(
        id="usr-admin",
        username="admin",
        email="admin@motorguard.local",
        role="Admin",
        assigned_sites=["SITE-MAIN"],
        assigned_motors=[],
        is_active=True,
    )
    app.dependency_overrides[get_current_active_user] = lambda: mock_admin

    payload = {
        "motor_id": "MTR-775-002",
        "device_id": "sim-node-002",
        "condition": "warning_temp",
    }
    try:
        response = client.post("/api/v1/simulator/inject", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["health_status"] == "warning"
        assert data["sensors"]["temperature_c"] > 50.0
    finally:
        app.dependency_overrides.clear()
