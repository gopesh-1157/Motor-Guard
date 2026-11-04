import pytest
from datetime import datetime, timezone
from bson import ObjectId
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.auth import get_user_service
from backend.app.core.security import get_password_hash, create_access_token, verify_password
from backend.app.schemas.user import UserInDB
from backend.app.services.user_service import UserService

client = TestClient(app)

def test_full_endpoint_current_password_flow():
    user_id = str(ObjectId())
    user_doc = {
        "_id": ObjectId(user_id),
        "username": "tech_verifier",
        "email": "verifier@plant.local",
        "role": "Technician",
        "password_hash": get_password_hash("InitialPass123!"),
        "is_active": True,
        "assigned_sites": ["SITE-PLANT-A"],
        "assigned_motors": [],
        "created_at": datetime.now(timezone.utc),
    }

    from unittest.mock import MagicMock, AsyncMock
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

    # Mock user retrieval for auth dependency
    user_in_db = UserInDB(
        id=user_id,
        username=user_doc["username"],
        email=user_doc["email"],
        role=user_doc["role"],
        password_hash=user_doc["password_hash"],
        created_at=user_doc["created_at"],
        is_active=True,
    )

    user_service.get_by_username = AsyncMock(return_value=user_in_db)
    user_service.get_by_id = AsyncMock(return_value=user_in_db)
    mock_users_col.find_one = AsyncMock(return_value=user_doc.copy())

    app.dependency_overrides[get_user_service] = lambda: user_service

    token = create_access_token({"sub": "tech_verifier", "role": "Technician"})
    headers = {"Authorization": f"Bearer {token}"}

    try:
        # Case 1: Missing current_password
        res_missing = client.patch(
            "/api/v1/auth/me",
            json={"password": "NewSecretPass456!"},
            headers=headers,
        )
        assert res_missing.status_code == 400
        assert "Current password is required" in res_missing.json()["detail"]

        # Case 2: Wrong current_password
        res_wrong = client.patch(
            "/api/v1/auth/me",
            json={
                "current_password": "WrongPassword999!",
                "password": "NewSecretPass456!",
            },
            headers=headers,
        )
        assert res_wrong.status_code == 400
        assert "Incorrect current password" in res_wrong.json()["detail"]

        # Case 3: Right current_password
        updated_doc = user_doc.copy()
        def fake_update(f, u):
            updated_doc.update(u.get("$set", {}))
            return MagicMock(modified_count=1)

        mock_users_col.update_one = AsyncMock(side_effect=fake_update)
        mock_users_col.find_one = AsyncMock(side_effect=[user_doc.copy(), updated_doc])

        res_ok = client.patch(
            "/api/v1/auth/me",
            json={
                "current_password": "InitialPass123!",
                "password": "NewSecretPass456!",
            },
            headers=headers,
        )
        assert res_ok.status_code == 200

        # Case 4: Verify old password fails and new password passes
        new_hash = updated_doc["password_hash"]
        assert verify_password("InitialPass123!", new_hash) is False
        assert verify_password("NewSecretPass456!", new_hash) is True
        assert "session_revoked_at" in updated_doc

    finally:
        app.dependency_overrides.clear()
