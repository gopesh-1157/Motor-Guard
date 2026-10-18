import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root discovery endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["version"] == "1.0.0"
    assert data["health"] == "/api/v1/health/live"


def test_health_live_endpoint():
    """Phase 1 Criterion: GET /api/v1/health/live returns HTTP 200 with status ok and version 1.0.0."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok", "version": "1.0.0"}


@pytest.mark.asyncio
async def test_health_ready_healthy():
    """When backing services are reachable, readiness probe returns HTTP 200 and ok status."""
    mock_subscriber = MagicMock()
    mock_subscriber.stats = {"connected": True, "messages_processed": 42, "validation_errors": 0}

    with (
        patch("backend.app.api.v1.endpoints.health.db_manager.ping", new_callable=AsyncMock) as mock_ping,
        patch("backend.app.api.v1.endpoints.health.mqtt_subscriber", mock_subscriber),
    ):
        mock_ping.return_value = (True, 1.45, None)
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
        assert data["dependencies"]["mongodb"]["status"] == "healthy"
        assert data["dependencies"]["mqtt_broker"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_ready_strict_fails_when_mongodb_down():
    """When MongoDB is down in strict mode, readiness probe returns HTTP 503."""
    mock_subscriber = MagicMock()
    mock_subscriber.stats = {"connected": True, "messages_processed": 0, "validation_errors": 0}

    with (
        patch("backend.app.api.v1.endpoints.health.db_manager.ping", new_callable=AsyncMock) as mock_ping,
        patch("backend.app.api.v1.endpoints.health.mqtt_subscriber", mock_subscriber),
    ):
        mock_ping.return_value = (False, 2000.0, "Connection refused")
        response = client.get("/api/v1/health/ready?strict=true")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unavailable"
        assert data["dependencies"]["mongodb"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_health_ready_dev_degraded_when_mongodb_down():
    """In development mode without strict flag, readiness probe returns 200 with degraded status."""
    mock_subscriber = MagicMock()
    mock_subscriber.stats = {"connected": False, "messages_processed": 0, "validation_errors": 0}

    with (
        patch("backend.app.api.v1.endpoints.health.db_manager.ping", new_callable=AsyncMock) as mock_ping,
        patch("backend.app.api.v1.endpoints.health.mqtt_subscriber", mock_subscriber),
    ):
        mock_ping.return_value = (False, 2000.0, "Connection timed out")
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["dependencies"]["mongodb"]["status"] == "unavailable"
        assert data["dependencies"]["mqtt_broker"]["status"] == "unavailable"


def test_security_headers_present():
    """Verify security headers are applied to HTTP responses."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    headers = response.headers
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-XSS-Protection"] == "1; mode=block"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert headers["Server"] == "MotorGuard-Gateway"

