"""
MotorGuard — Security Middleware & Defense-in-Depth Layer

Provides:
1. SecurityHeadersMiddleware:
   - Content Security Policy (CSP) against XSS & clickjacking
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: DENY
   - X-XSS-Protection: 1; mode=block
   - Strict-Transport-Security (HSTS)
   - Referrer-Policy: strict-origin-when-cross-origin
   - Permissions-Policy
   - Cross-Origin-Opener-Policy: same-origin
   - Server banner masking (anti-fingerprinting)

2. RateLimitingMiddleware:
   - In-memory sliding-window rate limiting per client IP
   - Anti-brute-force protection for /api/v1/auth/login
   - Resource exhaustion protection for export, ingestion & simulation APIs
   - Standard HTTP 429 Too Many Requests with Retry-After header
"""

import time
import logging
import ipaddress
from collections import defaultdict
from typing import Dict, List, Tuple
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from backend.app.config import settings

logger = logging.getLogger("motorguard.security_middleware")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces defense-in-depth HTTP response security headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # 1. Content Security Policy (CSP)
        csp_directives = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com data:",
            "img-src 'self' data: blob:",
            "connect-src 'self' ws: wss: http: https:",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # 2. MIME sniffing protection
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 3. Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # 4. Legacy XSS filter protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 5. Referrer leak prevention
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 6. Feature / Permissions policy
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # 7. Cross-Origin isolation
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # 8. Server fingerprint hiding
        response.headers["Server"] = "MotorGuard-Gateway"

        # 9. HSTS in production environments
        if settings.ENVIRONMENT.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RateLimiter:
    """Thread-safe sliding-window in-memory rate limiter."""

    def __init__(self):
        # Map of (category, client_ip) -> list of timestamps
        self._history: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def _cleanup_old_records(self, now: float, window_seconds: float = 60.0):
        """Purge entries older than window to bound memory footprint."""
        if now - self._last_cleanup < 30.0:
            return
        cutoff = now - window_seconds
        keys_to_delete = []
        for key, timestamps in self._history.items():
            valid_ts = [t for t in timestamps if t > cutoff]
            if valid_ts:
                self._history[key] = valid_ts
            else:
                keys_to_delete.append(key)
        for k in keys_to_delete:
            del self._history[k]
        self._last_cleanup = now

    def is_allowed(self, category: str, client_ip: str, limit: int, window_seconds: float = 60.0) -> Tuple[bool, int]:
        """
        Check if request from client_ip is allowed within window_seconds.
        Returns (is_allowed, remaining_quota).
        """
        now = time.time()
        self._cleanup_old_records(now, window_seconds)

        key = (category, client_ip)
        cutoff = now - window_seconds
        # Filter existing timestamps to active window
        timestamps = [t for t in self._history[key] if t > cutoff]

        if len(timestamps) >= limit:
            self._history[key] = timestamps
            return False, 0

        timestamps.append(now)
        self._history[key] = timestamps
        return True, limit - len(timestamps)


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces IP-based rate limiting on sensitive API endpoints."""

    def _is_trusted_peer(self, peer_ip: str, trusted_list: list) -> bool:
        if peer_ip in trusted_list:
            return True
        try:
            peer_addr = ipaddress.ip_address(peer_ip)
            for entry in trusted_list:
                if "/" in entry:
                    try:
                        if peer_addr in ipaddress.ip_network(entry, strict=False):
                            return True
                    except ValueError:
                        continue
        except ValueError:
            pass
        return False

    def _get_client_ip(self, request: Request) -> str:
        client_host = request.client.host if request.client else "127.0.0.1"
        trusted_proxies = getattr(settings, "trusted_proxies_list", ["127.0.0.1", "::1", "testclient"])

        # Strictly verify direct peer is in trusted proxies before honoring forwarded headers
        if self._is_trusted_peer(client_host, trusted_proxies):
            real_ip = request.headers.get("X-Real-IP")
            if real_ip and real_ip.strip():
                return real_ip.strip()

            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                parts = [p.strip() for p in forwarded.split(",") if p.strip()]
                if parts:
                    return parts[0]

        return client_host

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting if disabled in settings (e.g. testing)
        if not getattr(settings, "RATELIMIT_ENABLED", True):
            return await call_next(request)

        path = request.url.path
        client_ip = self._get_client_ip(request)

        # 1. Strict limit for authentication (anti brute force)
        if path.startswith("/api/v1/auth/login"):
            limit = getattr(settings, "RATELIMIT_LOGIN_PER_MIN", 10)
            category = "auth_login"
            allowed, remaining = rate_limiter.is_allowed(category, client_ip, limit, window_seconds=60.0)
            if not allowed:
                logger.warning("Rate limit exceeded for %s on %s from IP %s", category, path, client_ip)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "detail": "Login rate limit exceeded. Please wait 60 seconds before retrying.",
                        "retry_after": 60,
                    },
                    headers={"Retry-After": "60"},
                )

        # 2. Strict limit for large telemetry exports (anti DoS / data scraping)
        elif path.startswith("/api/v1/telemetry/export"):
            limit = 10
            category = "telemetry_export"
            allowed, _ = rate_limiter.is_allowed(category, client_ip, limit, window_seconds=60.0)
            if not allowed:
                logger.warning("Rate limit exceeded for %s from IP %s", category, client_ip)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "detail": "Data export rate limit reached. Please wait before requesting additional exports.",
                        "retry_after": 60,
                    },
                    headers={"Retry-After": "60"},
                )

        # 3. Limit for simulator fault injection
        elif path.startswith("/api/v1/simulator/inject"):
            limit = 30
            category = "sim_inject"
            allowed, _ = rate_limiter.is_allowed(category, client_ip, limit, window_seconds=60.0)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "detail": "Simulator injection rate limit exceeded.",
                        "retry_after": 60,
                    },
                    headers={"Retry-After": "60"},
                )

        # 4. General API limit
        elif path.startswith("/api/v1/"):
            limit = getattr(settings, "RATELIMIT_GENERAL_PER_MIN", 180)
            category = "api_general"
            allowed, _ = rate_limiter.is_allowed(category, client_ip, limit, window_seconds=60.0)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "detail": "General API request limit exceeded.",
                        "retry_after": 60,
                    },
                    headers={"Retry-After": "60"},
                )

        response = await call_next(request)
        return response
