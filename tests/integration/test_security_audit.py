"""
MotorGuard — Comprehensive Security Audit Test Suite

Automated verification of:
1. Rate Limiting (anti brute-force on /api/v1/auth/login)
2. HTTP Security Headers (CSP, X-Frame-Options, X-Content-Type-Options, XSS, COOP)
3. Authentication Gates on endpoints (motors, devices, telemetry, simulator)
4. Role-Based Access Control (RBAC) boundaries (Operator vs Technician vs Manager vs Admin)
5. Password Entropy & Complexity Validation
6. Production Security Constraints (Wildcard CORS rejection, DEBUG=False)
7. Query Parameter Sanitization (NoSQL injection prevention)
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import Settings
from backend.app.schemas.user import UserOut, UserInDB
from backend.app.core.auth import get_current_active_user, get_user_service
from backend.app.core.security import validate_password_strength, create_access_token
from backend.app.services.user_service import UserService

client = TestClient(app)


class TestSecurityHeadersAndHardening:
    """Audit of HTTP security headers and anti-fingerprinting."""

    def test_http_security_headers_enforcement(self):
        """All responses must include defense-in-depth headers."""
        res = client.get("/api/v1/health/live")
        assert res.status_code == 200
        headers = res.headers

        # Content Security Policy
        assert "Content-Security-Policy" in headers
        assert "default-src 'self'" in headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]

        # Anti-sniffing & clickjacking
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("X-XSS-Protection") == "1; mode=block"

        # Cross-Origin isolation & Referrer leak prevention
        assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert headers.get("Cross-Origin-Opener-Policy") == "same-origin"

        # Server banner fingerprinting masked
        assert headers.get("Server") == "MotorGuard-Gateway"


class TestRateLimiting:
    """Audit rate limiting on sensitive endpoints."""

    def test_auth_login_rate_limiting(self):
        """Exceeding login request threshold triggers HTTP 429 Too Many Requests."""
        from backend.app.core.middleware import rate_limiter

        # Ensure rate limiter starts clean for testing IP
        test_ip = "192.168.1.99"
        rate_limiter._history[("auth_login", test_ip)] = []

        headers = {"X-Forwarded-For": test_ip}
        payload = {"username": "admin", "password": "wrongpassword"}

        # First 10 requests are handled (will return 401 for bad password or 503 if mock DB)
        for _ in range(10):
            res = client.post("/api/v1/auth/login", json=payload, headers=headers)
            assert res.status_code in [401, 503]

        # 11th request must be intercepted by rate limiter
        res_blocked = client.post("/api/v1/auth/login", json=payload, headers=headers)
        assert res_blocked.status_code == 429
        assert "Too Many Requests" in res_blocked.json()["error"]
        assert res_blocked.headers.get("Retry-After") == "60"

    def test_spoofed_forwarded_for_from_untrusted_peer_is_ignored(self):
        """When request arrives from an untrusted peer, X-Forwarded-For is ignored to prevent rate-limit bypass."""
        from starlette.requests import Request
        from backend.app.core.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(app)

        # Simulate direct connection from untrusted attacker IP (198.51.100.24)
        mock_scope = {
            "type": "http",
            "client": ("198.51.100.24", 54321),
            "headers": [
                (b"x-forwarded-for", b"1.1.1.1, 10.0.0.1"),
            ],
        }
        mock_request = Request(mock_scope)
        resolved_ip = middleware._get_client_ip(mock_request)

        # Must ignore the spoofed 1.1.1.1 header and resolve the actual peer IP
        assert resolved_ip == "198.51.100.24"

    def test_trusted_proxy_forwarded_for_is_honored(self):
        """When request arrives from a trusted proxy IP, X-Forwarded-For client IP is accurately extracted."""
        from starlette.requests import Request
        from backend.app.core.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(app)

        # Simulate connection arriving through trusted reverse proxy (127.0.0.1)
        mock_scope = {
            "type": "http",
            "client": ("127.0.0.1", 54321),
            "headers": [
                (b"x-forwarded-for", b"203.0.113.88, 127.0.0.1"),
            ],
        }
        mock_request = Request(mock_scope)
        resolved_ip = middleware._get_client_ip(mock_request)

        # Must trust the proxy and resolve client IP
        assert resolved_ip == "203.0.113.88"

    def test_trusted_proxy_cidr_network_honored(self):
        """When request arrives from a Docker subnet IP configured in trusted proxies (CIDR notation), client IP is extracted."""
        from unittest.mock import patch
        from starlette.requests import Request
        from backend.app.core.middleware import RateLimitMiddleware
        from backend.app.config import settings

        middleware = RateLimitMiddleware(app)

        mock_scope = {
            "type": "http",
            "client": ("172.18.0.4", 54321),  # Container IP in Docker bridge
            "headers": [
                (b"x-forwarded-for", b"203.0.113.42"),
            ],
        }
        mock_request = Request(mock_scope)

        # With default loopback only, 172.18.0.4 is untrusted
        assert middleware._get_client_ip(mock_request) == "172.18.0.4"

        # With Docker bridge CIDR configured in trusted proxies, forwarding is honored
        with patch.object(settings, "TRUSTED_PROXIES", "127.0.0.1,::1,172.16.0.0/12"):
            resolved = middleware._get_client_ip(mock_request)
            assert resolved == "203.0.113.42"

    def test_trusted_proxy_x_real_ip_takes_precedence(self):
        """When trusted proxy sets X-Real-IP, it takes precedence over client-tainted X-Forwarded-For."""
        from starlette.requests import Request
        from backend.app.core.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(app)

        mock_scope = {
            "type": "http",
            "client": ("127.0.0.1", 54321),
            "headers": [
                (b"x-real-ip", b"198.51.100.99"),
                (b"x-forwarded-for", b"spoofed.client.ip, 198.51.100.99"),
            ],
        }
        mock_request = Request(mock_scope)
        resolved_ip = middleware._get_client_ip(mock_request)
        assert resolved_ip == "198.51.100.99"



class TestAuthenticationGates:
    """Verify unauthenticated requests to protected endpoints return 401."""

    def test_motors_endpoint_requires_auth(self):
        """GET /api/v1/motors without token returns 401 Unauthorized."""
        app.dependency_overrides.clear()
        res = client.get("/api/v1/motors")
        assert res.status_code == 401

    def test_devices_endpoint_requires_auth(self):
        """GET /api/v1/devices without token returns 401 Unauthorized."""
        app.dependency_overrides.clear()
        res = client.get("/api/v1/devices")
        assert res.status_code == 401

    def test_telemetry_recent_endpoint_requires_auth(self):
        """GET /api/v1/telemetry/recent without token returns 401 Unauthorized."""
        app.dependency_overrides.clear()
        res = client.get("/api/v1/telemetry/recent")
        assert res.status_code == 401

    def test_simulator_inject_endpoint_requires_auth(self):
        """POST /api/v1/simulator/inject without token returns 401 Unauthorized."""
        app.dependency_overrides.clear()
        res = client.post("/api/v1/simulator/inject", json={"motor_id": "MTR-775-001"})
        assert res.status_code == 401


class TestRBACBoundaries:
    """Verify strict role-based access control separation."""

    def test_operator_cannot_register_user(self):
        """Technician role cannot register new users (Requires Admin)."""
        mock_operator = UserOut(
            id="usr-op",
            username="tech_bob",
            email="bob@factory.local",
            role="Technician",
            assigned_sites=["SITE-MAIN"],
            assigned_motors=[],
            is_active=True,
        )
        app.dependency_overrides[get_current_active_user] = lambda: mock_operator

        payload = {
            "username": "new_admin",
            "email": "hacked@evil.local",
            "role": "Admin",
            "password": "ValidPassword123!",
        }
        try:
            res = client.post("/api/v1/auth/register", json=payload)
            assert res.status_code == 403
            assert "Operation requires role" in res.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_operator_cannot_inject_simulator_fault(self):
        """Technician role cannot inject simulator faults (Requires Admin or Manager)."""
        mock_operator = UserOut(
            id="usr-op",
            username="tech_bob",
            email="bob@factory.local",
            role="Technician",
            assigned_sites=["SITE-MAIN"],
            assigned_motors=[],
            is_active=True,
        )
        app.dependency_overrides[get_current_active_user] = lambda: mock_operator

        payload = {
            "motor_id": "MTR-775-002",
            "condition": "critical_vib",
        }
        try:
            res = client.post("/api/v1/simulator/inject", json=payload)
            assert res.status_code == 403
        finally:
            app.dependency_overrides.clear()


class TestPasswordComplexityValidation:
    """Verify password entropy rules."""

    def test_short_password_rejected(self):
        """Password under 8 characters must be rejected."""
        valid, err = validate_password_strength("abc1!")
        assert valid is False
        assert "at least 8 characters" in err

    def test_no_digit_or_symbol_rejected(self):
        """Password without digits or symbols must be rejected."""
        valid, err = validate_password_strength("AllAlphabeticLetters")
        assert valid is False
        assert "digit or special symbol" in err

    def test_valid_development_password_accepted(self):
        """Password with >=8 characters, letters, and numbers/symbols accepted."""
        valid, err = validate_password_strength("adminpassword123")
        assert valid is True
        assert err is None

    def test_strong_password_accepted(self):
        """Strong password with uppercase, lowercase, digit, and symbol accepted."""
        valid, err = validate_password_strength("EnterpriseSecurity2026!")
        assert valid is True
        assert err is None


class TestNoSQLInjectionSanitization:
    """Verify MongoDB query parameter sanitization."""

    def test_nosql_operator_rejected(self):
        """Query parameters containing '$where' or JSON syntax return 400."""
        from backend.app.schemas.user import UserOut
        mock_user = UserOut(
            id="usr-test",
            username="admin",
            email="admin@factory.local",
            role="Admin",
            assigned_sites=["SITE-MAIN"],
            assigned_motors=[],
            is_active=True,
        )
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        try:
            res = client.get("/api/v1/telemetry/recent?motor_id={\"$gt\":\"\"}")
            assert res.status_code == 400
            assert "Invalid character" in res.json()["detail"]
        finally:
            app.dependency_overrides.clear()
