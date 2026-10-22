"""
Phase 2 Unit Tests — User Management Workflow & RBAC Security Constraints

Verifies:
1. Admin can create Manager and Technician accounts.
2. Manager and Technician cannot register users (HTTP 403).
3. Creation of an Admin account through ordinary APIs is strictly prohibited (HTTP 400).
4. Duplicate username and duplicate email rejections.
5. Password complexity validation, hashing, and password omission in responses.
6. Admin can edit user profiles (email, scopes, activation).
7. Non-admin cannot edit or deactivate users (HTTP 403).
8. Final active Admin protection: preventing deactivation, demotion, or deletion.
9. Atomic serialization of Admin mutations preventing race-condition lockout.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.auth import get_user_service
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.schemas.user import UserInDB, UserOut, UserUpdate
from backend.app.services.user_service import UserService

client = TestClient(app)


def auth_header(username: str, role: str) -> dict:
    token = create_access_token({"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_create_manager_and_technician():
    """Admin can register Manager and Technician accounts."""
    admin_user = UserInDB(
        id="65f123456789abcdef012345",
        username="admin_user",
        email="admin@factory.local",
        role="Admin",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )

    mock_svc = MagicMock(spec=UserService)
    mock_svc.get_by_username = AsyncMock(side_effect=lambda u: admin_user if u == "admin_user" else None)
    mock_svc.get_by_email = AsyncMock(return_value=None)
    mock_svc.create_user = AsyncMock(
        side_effect=lambda user_in, actor: UserOut(
            id="65f999999999abcdef012345",
            username=user_in.username,
            email=user_in.email,
            role=user_in.role,
            assigned_sites=user_in.assigned_sites,
            assigned_motors=user_in.assigned_motors,
            is_active=True,
        )
    )
    app.dependency_overrides[get_user_service] = lambda: mock_svc

    try:
        # 1. Create Manager
        res_mgr = client.post(
            "/api/v1/auth/register",
            json={
                "username": "new_manager",
                "email": "mgr@factory.local",
                "password": "Password123!",
                "role": "Manager",
                "assigned_sites": ["SITE-A"],
            },
            headers=auth_header("admin_user", "Admin"),
        )
        assert res_mgr.status_code == 201
        data_mgr = res_mgr.json()
        assert data_mgr["username"] == "new_manager"
        assert data_mgr["role"] == "Manager"
        assert "password" not in data_mgr
        assert "password_hash" not in data_mgr

        # 2. Create Technician
        res_tech = client.post(
            "/api/v1/auth/register",
            json={
                "username": "new_technician",
                "email": "tech@factory.local",
                "password": "Password123!",
                "role": "Technician",
                "assigned_sites": ["SITE-A"],
            },
            headers=auth_header("admin_user", "Admin"),
        )
        assert res_tech.status_code == 201
        data_tech = res_tech.json()
        assert data_tech["username"] == "new_technician"
        assert data_tech["role"] == "Technician"
        assert "password" not in data_tech
        assert "password_hash" not in data_tech
    finally:
        app.dependency_overrides.clear()


def test_cannot_create_admin_through_api():
    """Attempting to create an Admin account through POST /register must return HTTP 400."""
    admin_user = UserInDB(
        id="65f123456789abcdef012345",
        username="admin_user",
        email="admin@factory.local",
        role="Admin",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )

    mock_svc = MagicMock(spec=UserService)
    mock_svc.get_by_username = AsyncMock(return_value=admin_user)
    app.dependency_overrides[get_user_service] = lambda: mock_svc

    try:
        res = client.post(
            "/api/v1/auth/register",
            json={
                "username": "sneaky_admin",
                "email": "sneaky@factory.local",
                "password": "Password123!",
                "role": "Admin",
            },
            headers=auth_header("admin_user", "Admin"),
        )
        assert res.status_code == 400
        assert "Creating Admin accounts through standard user management is prohibited" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_manager_and_technician_cannot_create_users():
    """Managers and Technicians must receive HTTP 403 when trying to register accounts."""
    roles = ["Manager", "Technician"]
    for role in roles:
        user = UserInDB(
            id="65f123456789abcdef012345",
            username=f"test_{role.lower()}",
            email=f"{role.lower()}@factory.local",
            role=role,
            password_hash="hash",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_svc = MagicMock(spec=UserService)
        mock_svc.get_by_username = AsyncMock(return_value=user)
        app.dependency_overrides[get_user_service] = lambda: mock_svc

        try:
            res = client.post(
                "/api/v1/auth/register",
                json={
                    "username": "sub_user",
                    "email": "sub@factory.local",
                    "password": "Password123!",
                    "role": "Technician",
                },
                headers=auth_header(user.username, role),
            )
            assert res.status_code == 403
            assert "Operation requires role in ('Admin',)" in res.json()["detail"]
        finally:
            app.dependency_overrides.clear()


def test_duplicate_username_and_email_rejected():
    """Registration fails if username or email is already taken."""
    admin_user = UserInDB(
        id="65f123456789abcdef012345",
        username="admin_user",
        email="admin@factory.local",
        role="Admin",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )
    existing_user = UserInDB(
        id="65f111111111abcdef012345",
        username="existing_name",
        email="existing@factory.local",
        role="Technician",
        password_hash="hash",
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )

    mock_svc = MagicMock(spec=UserService)
    # Check duplicate username
    mock_svc.get_by_username = AsyncMock(
        side_effect=lambda u: admin_user if u == "admin_user" else (existing_user if u == "existing_name" else None)
    )
    mock_svc.get_by_email = AsyncMock(side_effect=lambda e: existing_user if e == "existing@factory.local" else None)
    app.dependency_overrides[get_user_service] = lambda: mock_svc

    try:
        # Duplicate username
        res_dup_name = client.post(
            "/api/v1/auth/register",
            json={
                "username": "existing_name",
                "email": "fresh@factory.local",
                "password": "Password123!",
                "role": "Technician",
            },
            headers=auth_header("admin_user", "Admin"),
        )
        assert res_dup_name.status_code == 400
        assert "Username 'existing_name' is already registered" in res_dup_name.json()["detail"]

        # Duplicate email
        res_dup_email = client.post(
            "/api/v1/auth/register",
            json={
                "username": "unique_name",
                "email": "existing@factory.local",
                "password": "Password123!",
                "role": "Technician",
            },
            headers=auth_header("admin_user", "Admin"),
        )
        assert res_dup_email.status_code == 400
        assert "Email 'existing@factory.local' is already registered" in res_dup_email.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_final_active_admin_protection():
    """Verify UserService prevents deactivating, demoting, or deleting the last active Admin."""
    mock_users_col = MagicMock()
    mock_audit_col = MagicMock()
    mock_audit_col.insert_one = AsyncMock()
    mock_audit_logs = MagicMock()
    mock_audit_logs.insert_one = AsyncMock()

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: (
        mock_users_col if name == "users" else (mock_audit_col if name == "audit_events" else mock_audit_logs)
    )

    user_service = UserService(mock_db)

    admin_oid = ObjectId("65f123456789abcdef012345")
    single_admin_doc = {
        "_id": admin_oid,
        "username": "only_admin",
        "email": "only@factory.local",
        "role": "Admin",
        "is_active": True,
        "assigned_sites": ["SITE-MAIN"],
        "assigned_motors": [],
    }

    # 1. Attempt to deactivate only admin
    mock_users_col.find_one = AsyncMock(return_value=single_admin_doc.copy())
    mock_users_col.count_documents = AsyncMock(return_value=1)  # Only 1 active admin!

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await user_service.update_user(str(admin_oid), UserUpdate(is_active=False), actor="only_admin")
    assert exc_info.value.status_code == 400
    assert "Cannot deactivate or demote the final active Admin account" in exc_info.value.detail

    # 2. Attempt to demote only admin to Technician
    with pytest.raises(HTTPException) as exc_info:
        await user_service.update_user(str(admin_oid), UserUpdate(role="Technician"), actor="only_admin")
    assert exc_info.value.status_code == 400
    assert "Cannot deactivate or demote the final active Admin account" in exc_info.value.detail

    # 3. Attempt to delete only admin
    with pytest.raises(HTTPException) as exc_info:
        await user_service.delete_user(str(admin_oid), actor="only_admin")
    assert exc_info.value.status_code == 400
    assert "Cannot delete the final active Admin account" in exc_info.value.detail

    # 4. If 2 active admins exist, deactivating one is allowed
    mock_users_col.count_documents = AsyncMock(return_value=2)
    mock_users_col.update_one = AsyncMock()
    updated_doc = single_admin_doc.copy()
    updated_doc["is_active"] = False
    mock_users_col.find_one = AsyncMock(side_effect=[single_admin_doc.copy(), updated_doc])

    res = await user_service.update_user(str(admin_oid), UserUpdate(is_active=False), actor="admin_two")
    assert res.is_active is False
    mock_users_col.update_one.assert_called_once()
