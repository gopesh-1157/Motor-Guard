import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.v1.endpoints.websocket import ws_manager


def test_websocket_telemetry_connection():
    """Verify WebSocket client can connect to /ws/telemetry and receive broadcasted messages."""
    client = TestClient(app)

    with client.websocket_connect("/ws/telemetry") as websocket:
        assert ws_manager.connection_count >= 1

        # Test sending a ping or client message
        websocket.send_text("ping")

    # After exit, client should be disconnected
    assert ws_manager.connection_count == 0


@pytest.mark.asyncio
async def test_websocket_broadcast_delivery():
    """Verify ws_manager.broadcast delivers payload to connected clients."""
    client = TestClient(app)

    with client.websocket_connect("/ws/telemetry") as websocket:
        # Simulate broadcast
        test_payload = {
            "motor_id": "MTR-TEST",
            "source": "simulator",
            "status": "healthy",
        }
        await ws_manager.broadcast(test_payload)

        data = websocket.receive_json()
        assert data["motor_id"] == "MTR-TEST"
        assert data["source"] == "simulator"
        assert data["status"] == "healthy"
