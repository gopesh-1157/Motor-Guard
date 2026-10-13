"""
MotorGuard — Historical Telemetry, Aggregation & Export Tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.mongodb import db_manager
from backend.app.core.security import create_access_token

client = TestClient(app)


@pytest.fixture
def mock_db():
    db = MagicMock()
    original_db = db_manager.db
    db_manager.db = db
    yield db
    db_manager.db = original_db


def test_historical_telemetry_query(mock_db):
    """Verify querying historical telemetry with filter criteria."""
    cursor_mock = MagicMock()
    cursor_mock.sort.return_value = cursor_mock
    cursor_mock.limit.return_value = cursor_mock
    cursor_mock.to_list = AsyncMock(return_value=[
        {
            "event_id": "evt-001",
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "source": "hardware",
            "seq": 1,
            "timestamp": "2026-10-10T12:00:00Z",
            "sensors": {"temperature_c": 35.2, "current_a": 1.25, "vibration_g_rms": 0.052},
            "inference": {"health_status": "healthy", "confidence": 0.98},
        }
    ])

    telemetry_col = MagicMock()
    telemetry_col.find.return_value = cursor_mock
    mock_db.__getitem__.return_value = telemetry_col

    response = client.get("/api/v1/telemetry/historical?motor_id=MTR-775-001&limit=50")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["telemetry"][0]["motor_id"] == "MTR-775-001"


def test_motor_aggregates_query(mock_db):
    """Verify statistical aggregates calculation endpoint."""
    telemetry_col = MagicMock()
    telemetry_col.aggregate.side_effect = [
        # First call: stats pipeline
        MagicMock(to_list=AsyncMock(return_value=[{
            "count": 42,
            "avg_temp": 36.4,
            "min_temp": 31.0,
            "max_temp": 44.5,
            "avg_current": 1.45,
            "min_current": 0.8,
            "max_current": 2.1,
            "avg_vibration": 0.065,
            "min_vibration": 0.02,
            "max_vibration": 0.12,
        }])),
        # Second call: health distribution pipeline
        MagicMock(to_list=AsyncMock(return_value=[
            {"_id": "healthy", "count": 40},
            {"_id": "warning", "count": 2},
        ])),
    ]
    mock_db.__getitem__.return_value = telemetry_col

    response = client.get("/api/v1/telemetry/aggregates?motor_id=MTR-775-001")
    assert response.status_code == 200
    data = response.json()
    assert data["motor_id"] == "MTR-775-001"
    assert data["statistics"]["count"] == 42
    assert data["statistics"]["avg_temp"] == 36.4
    assert data["health_distribution"]["healthy"] == 40


def test_export_telemetry_csv(mock_db):
    """Verify industrial CSV export with engineering headers."""
    cursor_mock = MagicMock()
    cursor_mock.sort.return_value = cursor_mock
    cursor_mock.limit.return_value = cursor_mock
    cursor_mock.to_list = AsyncMock(return_value=[
        {
            "event_id": "evt-001",
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "source": "hardware",
            "seq": 10,
            "timestamp": "2026-10-10T12:00:00Z",
            "sensors": {"temperature_c": 35.2, "current_a": 1.25, "vibration_g_rms": 0.052},
            "inference": {"health_status": "healthy", "confidence": 0.98, "model_version": "ei-motoguard-v1.0.1"},
            "diagnostics": {"wifi_rssi_dbm": -55, "free_heap_bytes": 180000, "uptime_seconds": 1200},
        }
    ])

    telemetry_col = MagicMock()
    telemetry_col.find.return_value = cursor_mock
    mock_db.__getitem__.return_value = telemetry_col

    response = client.get("/api/v1/telemetry/export?motor_id=MTR-775-001&export_format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment; filename=" in response.headers["content-disposition"]
    csv_text = response.text
    assert "Timestamp_UTC,Motor_ID,Device_ID" in csv_text
    assert "MTR-775-001" in csv_text
    assert "35.2" in csv_text


def test_export_telemetry_json(mock_db):
    """Verify JSON export format."""
    cursor_mock = MagicMock()
    cursor_mock.sort.return_value = cursor_mock
    cursor_mock.limit.return_value = cursor_mock
    cursor_mock.to_list = AsyncMock(return_value=[
        {
            "event_id": "evt-001",
            "motor_id": "MTR-775-001",
            "device_id": "esp32-node-001",
            "source": "hardware",
            "timestamp": "2026-10-10T12:00:00Z",
        }
    ])

    telemetry_col = MagicMock()
    telemetry_col.find.return_value = cursor_mock
    mock_db.__getitem__.return_value = telemetry_col

    response = client.get("/api/v1/telemetry/export?motor_id=MTR-775-001&export_format=json")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["event_id"] == "evt-001"


def test_reopen_alert_lifecycle():
    """Verify alert reopen endpoint transitions state back to ACTIVE."""
    from backend.app.api.v1.endpoints.alerts import get_alert_service
    from backend.app.schemas.alert import AlertOut

    mock_alert = AlertOut(
        id="alt-id-001",
        alert_id="ALT-20261010-001",
        motor_id="MTR-775-001",
        device_id="esp32-node-001",
        severity="WARNING",
        trigger_type="THRESHOLD_OVERTEMPERATURE",
        trigger_value=54.2,
        threshold_limit=50.0,
        unit="°C",
        message="Overtemperature warning",
        state="ACTIVE",
        triggered_at="2026-10-10T12:00:00Z",
        reopened_at="2026-10-10T13:00:00Z",
        reopened_by="manager_alice",
        reopen_reason="Temperature anomaly re-occurred",
    )

    mock_service = MagicMock()
    mock_service.reopen_alert = AsyncMock(return_value=mock_alert)

    from backend.app.core.auth import get_user_service
    from backend.app.schemas.user import UserInDB
    from datetime import datetime, timezone

    mock_user = UserInDB(
        id="usr-001",
        username="manager_alice",
        email="alice@factory.local",
        role="Manager",
        password_hash="mockhash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )
    mock_user_service = MagicMock()
    mock_user_service.get_by_username = AsyncMock(return_value=mock_user)

    app.dependency_overrides[get_alert_service] = lambda: mock_service
    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    token = create_access_token(data={"sub": "manager_alice", "role": "Manager"})

    response = client.post(
        "/api/v1/alerts/ALT-20261010-001/reopen",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Temperature anomaly re-occurred"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["state"] == "ACTIVE"
    assert res_data["reopened_by"] == "manager_alice"
