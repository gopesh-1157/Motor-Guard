"""
Phase 1 Unit Tests — 3-Role RBAC Authentication & Legacy Migration

Verifies:
1. Valid login for Admin, Manager, and Technician.
2. Rejection of invalid credentials (HTTP 401).
3. Rejection of deactivated user login (HTTP 401).
4. Rejection of deactivated user token at protected endpoints (HTTP 403).
5. Rejection of obsolete roles (e.g. 'Operator') at protected endpoints.
6. Safe migration of legacy 'Operator' accounts to 'Technician'.
7. Session revocation enforcement (tokens issued prior to revocation are rejected).
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.auth import get_user_service
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.schemas.user import UserInDB, UserOut
from backend.app.services.user_service import UserService
from backend.app.db.migrations import migrate_legacy_roles

client = TestClient(app)


def test_login_success_for_all_three_roles():
    """Verify Admin, Manager, and Technician can authenticate and receive JWT tokens."""
    roles = ["Admin", "Manager", "Technician"]
    for role in roles:
        username = f"test_{role.lower()}"
        mock_user = UserInDB(
            id="65f123456789abcdef012345",
            username=username,
            email=f"{username}@factory.local",
            role=role,
            password_hash=get_password_hash("ValidPass123!"),
            created_at=datetime.now(timezone.utc),
            is_active=True,
            assigned_sites=["SITE-MAIN"],
            assigned_motors=[],
        )

        mock_svc = MagicMock(spec=UserService)
        mock_svc.authenticate = AsyncMock(return_value=mock_user)
        app.dependency_overrides[get_user_service] = lambda: mock_svc

        try:
            res = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "ValidPass123!"},
            )
            assert res.status_code == 200
            data = res.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["user"]["username"] == username
            assert data["user"]["role"] == role
        finally:
            app.dependency_overrides.clear()


def test_login_invalid_credentials_returns_401():
    """Incorrect username or password must return HTTP 401."""
    mock_svc = MagicMock(spec=UserService)
    mock_svc.authenticate = AsyncMock(return_value=None)
    app.dependency_overrides[get_user_service] = lambda: mock_svc

    try:
        res = client.post(
            "/api/v1/auth/login",
            json={"username": "bad_user", "password": "wrong_password"},
        )
        assert res.status_code == 401
        assert "Incorrect username or password" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_login_deactivated_user_returns_401():
    """Deactivated accounts cannot authenticate via /login (HTTP 401)."""
    mock_svc = MagicMock(spec=UserService)
    mock_svc.authenticate = AsyncMock(return_value=None)
    app.dependency_overrides[get_user_service] = lambda: mock_svc

    try:
        res = client.post(
            "/api/v1/auth/login",
            json={"username": "disabled_user", "password": "Password123!"},
        )
        assert res.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_deactivated_user_token_rejected_at_protected_endpoints():
    """An active JWT for an account that was subsequently deactivated must return HTTP 403."""
    mock_user = UserInDB(
        id="65f123456789abcdef012345",
        username="deactivated_tech",
        email="deactivated@factory.local",
        role="Technician",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=False,  # Inactive
    )
    mock_svc = MagicMock(spec=UserService)
    mock_svc.get_by_username = AsyncMock(return_value=mock_user)
    app.dependency_overrides[get_user_service] = lambda: mock_svc

    try:
        token = create_access_token({"sub": "deactivated_tech", "role": "Technician"})
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert "Inactive user account" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_obsolete_role_token_rejected_at_protected_endpoints():
    """A user in DB with obsolete role (e.g., 'Operator') must be rejected with HTTP 403."""
    mock_user = MagicMock()
    mock_user.id = "65f123456789abcdef012345"
    mock_user.username = "legacy_operator"
    mock_user.email = "op@factory.local"
    mock_user.role = "Operator"  # Obsolete role
    mock_user.is_active = True
    mock_user.session_revoked_at = None

    mock_svc = MagicMock(spec=UserService)
    mock_svc.get_by_username = AsyncMock(return_value=mock_user)
    app.dependency_overrides[get_user_service] = lambda: mock_svc

    try:
        token = create_access_token({"sub": "legacy_operator", "role": "Operator"})
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert "deprecated or invalid" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_revoked_session_token_rejected_returns_401():
    """Tokens issued before session_revoked_at timestamp must return HTTP 401."""
    now = datetime.now(timezone.utc)
    revocation_time = now + timedelta(minutes=5)

    mock_user = UserInDB(
        id="65f123456789abcdef012345",
        username="revoked_tech",
        email="revoked@factory.local",
        role="Technician",
        password_hash="hash",
        created_at=now,
        is_active=True,
        session_revoked_at=revocation_time,  # Revoked in the future relative to token creation
    )
    mock_svc = MagicMock(spec=UserService)
    mock_svc.get_by_username = AsyncMock(return_value=mock_user)
    app.dependency_overrides[get_user_service] = lambda: mock_svc

    try:
        # Token created with iat = now, which is < revocation_time
        old_token = create_access_token({"sub": "revoked_tech", "role": "Technician"})
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
        assert res.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_migrate_legacy_roles():
    """Verify migrate_legacy_roles maps Operator to Technician, revokes sessions, and logs audit."""
    mock_users_col = MagicMock()
    mock_audit_col = MagicMock()

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: mock_users_col if name == "users" else mock_audit_col

    legacy_user = {
        "_id": "user_id_123",
        "username": "legacy_operator_bob",
        "role": "Operator",
        "assigned_sites": ["SITE-A", "*"],
        "assigned_motors": ["*"],
    }

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[legacy_user])
    mock_users_col.find.return_value = mock_cursor
    mock_users_col.update_one = AsyncMock()
    mock_audit_col.insert_one = AsyncMock()

    result = await migrate_legacy_roles(mock_db)

    assert result["status"] == "success"
    assert result["migrated_count"] == 1
    assert result["migrated_users"][0]["new_role"] == "Technician"

    # Verify update called with sanitized sites/motors and session revocation
    mock_users_col.update_one.assert_called_once()
    update_call = mock_users_col.update_one.call_args[0]
    assert update_call[0] == {"_id": "user_id_123"}
    update_doc = update_call[1]["$set"]
    assert update_doc["role"] == "Technician"
    assert update_doc["assigned_sites"] == ["SITE-A"]  # '*' removed
    assert update_doc["assigned_motors"] == []  # '*' removed
    assert "session_revoked_at" in update_doc

    # Verify audit event logged
    mock_audit_col.insert_one.assert_called_once()
    audit_doc = mock_audit_col.insert_one.call_args[0][0]
    assert audit_doc["action"] == "MIGRATE_LEGACY_ROLE"
    assert audit_doc["target_id"] == "legacy_operator_bob"
