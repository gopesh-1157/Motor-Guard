import pytest
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.security import create_access_token
from backend.app.api.v1.endpoints.websocket import ws_manager


def test_websocket_anonymous_rejected():
    """Verify WebSocket client without token is rejected with policy violation (1008)."""
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/telemetry"):
            pass
    assert exc_info.value.code == 1008


def test_websocket_invalid_token_rejected():
    """Verify WebSocket client with invalid token is rejected with 1008."""
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/telemetry?token=invalid.malformed.token"):
            pass
    assert exc_info.value.code == 1008


def test_websocket_authenticated_connection():
    """Verify authenticated WebSocket client connects, sends messages, and cleans up on exit."""
    client = TestClient(app)
    token = create_access_token(data={"sub": "technician_bob", "role": "Technician"})

    with client.websocket_connect(f"/ws/telemetry?token={token}") as websocket:
        assert ws_manager.connection_count >= 1
        websocket.send_text("ping")

    # After exit, client should be disconnected and cleaned up
    assert ws_manager.connection_count == 0


@pytest.mark.asyncio
async def test_websocket_broadcast_delivery():
    """Verify ws_manager.broadcast delivers payload to connected authenticated clients."""
    client = TestClient(app)
    token = create_access_token(data={"sub": "technician_bob", "role": "Technician"})

    with client.websocket_connect(f"/ws/telemetry?token={token}") as websocket:
        # Simulate broadcast with direct assignment to technician_bob
        test_payload = {
            "motor_id": "MTR-TEST",
            "source": "simulator",
            "status": "healthy",
            "assigned_to": "technician_bob",
        }
        await ws_manager.broadcast(test_payload)

        data = websocket.receive_json()
        assert data["motor_id"] == "MTR-TEST"
        assert data["source"] == "simulator"
        assert data["status"] == "healthy"


def test_websocket_subprotocol_authentication_no_url_leak():
    """Verify client authenticates via Sec-WebSocket-Protocol without query parameter token leakage."""
    client = TestClient(app)
    token = create_access_token(data={"sub": "tech_dave", "role": "Technician"})

    with client.websocket_connect("/ws/telemetry", subprotocols=["access_token", token]) as websocket:
        assert ws_manager.connection_count >= 1
        websocket.send_text("status")
    assert ws_manager.connection_count == 0


def test_websocket_header_authentication():
    """Verify client authenticates via standard Authorization: Bearer header."""
    client = TestClient(app)
    token = create_access_token(data={"sub": "admin_alice", "role": "Admin"})

    with client.websocket_connect("/ws/telemetry", headers={"Authorization": f"Bearer {token}"}) as websocket:
        assert ws_manager.connection_count >= 1
    assert ws_manager.connection_count == 0


def test_websocket_inactive_user_rejected():
    """Verify inactive/disabled user account is rejected even with cryptographically valid unexpired JWT."""
    from unittest.mock import AsyncMock
    from backend.app.core.auth import get_user_service
    from backend.app.schemas.user import UserInDB
    from datetime import datetime, timezone

    client = TestClient(app)
    token = create_access_token(data={"sub": "locked_user", "role": "Technician"})

    mock_svc = AsyncMock()
    mock_svc.get_by_username.return_value = UserInDB(
        id="mock_locked_id",
        username="locked_user",
        email="locked@motorguard.local",
        password_hash="...",
        role="Technician",
        assigned_sites=[],
        assigned_motors=[],
        is_active=False,  # DEACTIVATED
        created_at=datetime.now(timezone.utc),
    )

    app.dependency_overrides[get_user_service] = lambda: mock_svc
    try:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/telemetry?token={token}"):
                pass
        assert exc_info.value.code == 1008
    finally:
        app.dependency_overrides.clear()


def test_websocket_unauthorized_role_rejected():
    """Verify user with role outside allowed roles cannot open telemetry streaming connection."""
    from unittest.mock import AsyncMock, MagicMock
    from backend.app.core.auth import get_user_service

    client = TestClient(app)
    token = create_access_token(data={"sub": "auditor_guest", "role": "ExternalAuditor"})

    mock_user = MagicMock()
    mock_user.id = "mock_auditor_id"
    mock_user.username = "auditor_guest"
    mock_user.email = "auditor@motorguard.local"
    mock_user.role = "ExternalAuditor"  # Disallowed role
    mock_user.assigned_sites = []
    mock_user.assigned_motors = []
    mock_user.is_active = True
    mock_user.created_at = None
    mock_user.last_login_at = None

    mock_svc = AsyncMock()
    mock_svc.get_by_username.return_value = mock_user

    app.dependency_overrides[get_user_service] = lambda: mock_svc
    try:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/telemetry?token={token}"):
                pass
        assert exc_info.value.code == 1008
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_websocket_site_and_motor_authorization_isolation():
    """
    MG-F01 Regression Test:
    Verify cross-site and cross-motor isolation on WebSocket broadcasts.
    Operator at Site A (assigned to Motor A) must receive only Motor A telemetry.
    Operator at Site B (assigned to Motor B) must receive only Motor B telemetry.
    """
    from unittest.mock import MagicMock, AsyncMock
    from backend.app.schemas.user import UserOut

    user_a = UserOut(
        id="usr_site_a",
        username="op_plant_a",
        email="op_a@motorguard.local",
        role="Technician",
        assigned_sites=["SITE-PLANT-A"],
        assigned_motors=["MTR-A-01"],
        is_active=True,
    )

    user_b = UserOut(
        id="usr_site_b",
        username="op_plant_b",
        email="op_b@motorguard.local",
        role="Technician",
        assigned_sites=["SITE-PLANT-B"],
        assigned_motors=["MTR-B-01"],
        is_active=True,
    )

    ws_mock_a = AsyncMock()
    ws_mock_b = AsyncMock()

    await ws_manager.connect(ws_mock_a, user=user_a)
    await ws_manager.connect(ws_mock_b, user=user_b)

    try:
        # Event for Motor A at Site A
        event_a = {
            "type": "telemetry",
            "data": {
                "motor_id": "MTR-A-01",
                "site_id": "SITE-PLANT-A",
                "temperature": 45.0,
            },
        }

        # Event for Motor B at Site B
        event_b = {
            "type": "telemetry",
            "data": {
                "motor_id": "MTR-B-01",
                "site_id": "SITE-PLANT-B",
                "temperature": 52.0,
            },
        }

        # Broadcast event A
        await ws_manager.broadcast(event_a)
        assert ws_mock_a.send_text.call_count == 1
        assert ws_mock_b.send_text.call_count == 0

        # Broadcast event B
        await ws_manager.broadcast(event_b)
        assert ws_mock_a.send_text.call_count == 1  # Still 1
        assert ws_mock_b.send_text.call_count == 1  # Now 1
    finally:
        await ws_manager.disconnect(ws_mock_a)
        await ws_manager.disconnect(ws_mock_b)


