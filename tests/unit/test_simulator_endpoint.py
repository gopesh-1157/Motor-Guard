"""
MotorGuard — Unit tests for Simulator Endpoint
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_simulator_status():
    """Verify simulator status returns profile and virtual devices list."""
    response = client.get("/api/v1/simulator/status")
    assert response.status_code == 200
    data = response.json()
    assert "active_profile" in data
    assert "available_profiles" in data
    assert "virtual_devices" in data
    assert len(data["virtual_devices"]) >= 3


def test_simulator_inject_condition():
    """Verify simulator condition injection produces compliant telemetry packet."""
    payload = {
        "motor_id": "MTR-775-002",
        "device_id": "sim-node-002",
        "condition": "warning_temp",
    }
    response = client.post("/api/v1/simulator/inject", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["health_status"] == "warning"
    assert data["sensors"]["temperature_c"] > 50.0
