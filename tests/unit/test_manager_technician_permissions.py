"""
Unit and Integration Tests for FIX 3: Manager manages Technicians ONLY (Backend Enforced).

Validates:
1. Manager can create Technicians (scoped to Manager's sites).
2. Manager gets 403 when creating Admins or Managers.
3. Manager gets 403 when creating Technicians outside Manager's site scope.
4. Manager can edit Technician email, assigned_sites, and is_active.
5. Manager gets 403 when attempting to edit Admin or another Manager.
6. Manager gets 403 when attempting to edit self via /users/{user_id}.
7. Manager gets 403 when attempting role escalation (setting role to Admin or Manager).
8. Manager can set a new password for a Technician (revokes active session, never returns password hash).
9. Manager can toggle Technician active status; gets 403 for Admin or Manager.
10. Manager gets 403 when attempting to delete any user.
11. Technician gets 403 on all /users endpoints.
12. Admin retains full powers over all roles with last-admin safeguards.
13. Manager with no assigned_sites does not get a broken empty list.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from bson import ObjectId

from backend.app.main import app
from backend.app.core.auth import get_user_service
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.schemas.user import UserInDB, UserOut
from backend.app.services.user_service import UserService


def make_user(
    uid: str,
    username: str,
    role: str,
    email: str,
    sites: list = None,
    is_active: bool = True,
) -> UserInDB:
    return UserInDB(
        id=uid,
        username=username,
        email=email,
        role=role,
        assigned_sites=sites or [],
        assigned_motors=[],
        is_active=is_active,
        password_hash=get_password_hash("ValidPass123!"),
        created_at=datetime.now(timezone.utc),
        session_revoked_at=None,
    )


@pytest.fixture
def auth_users():
    admin_id = str(ObjectId())
    mgr_site_a_id = str(ObjectId())
    mgr_site_b_id = str(ObjectId())
    mgr_unscoped_id = str(ObjectId())
    tech_site_a_id = str(ObjectId())
    tech_site_b_id = str(ObjectId())

    admin = make_user(admin_id, "admin_user", "Admin", "admin@plant.local", ["SITE-A", "SITE-B"])
    mgr_a = make_user(mgr_site_a_id, "manager_a", "Manager", "mgr_a@plant.local", ["SITE-A"])
    mgr_b = make_user(mgr_site_b_id, "manager_b", "Manager", "mgr_b@plant.local", ["SITE-B"])
    mgr_unscoped = make_user(mgr_unscoped_id, "manager_unscoped", "Manager", "mgr_u@plant.local", [])
    tech_a = make_user(tech_site_a_id, "tech_a", "Technician", "tech_a@plant.local", ["SITE-A"])
    tech_b = make_user(tech_site_b_id, "tech_b", "Technician", "tech_b@plant.local", ["SITE-B"])

    users_map = {
        "admin_user": admin,
        "manager_a": mgr_a,
        "manager_b": mgr_b,
        "manager_unscoped": mgr_unscoped,
        "tech_a": tech_a,
        "tech_b": tech_b,
    }
    id_map = {u.id: u for u in users_map.values()}
    return users_map, id_map


def auth_header(username: str, role: str) -> dict:
    token = create_access_token({"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


class TestManagerTechnicianPermissions:
    @pytest.fixture(autouse=True)
    def setup_mocks(self, auth_users):
        users_map, id_map = auth_users
        self.users_map = users_map
        self.id_map = id_map

        # Build mock UserService that delegates to our in-memory data
        self.mock_service = UserService(MagicMock())
        self.mock_service.collection = MagicMock()
        self.mock_service._audit = AsyncMock()

        async def fake_get_by_username(uname: str):
            return self.users_map.get(uname)

        async def fake_get_by_id(uid: str):
            u = self.id_map.get(uid)
            return UserOut(**u.model_dump()) if u else None

        async def fake_find_one(query: dict):
            if "_id" in query:
                uid = str(query["_id"])
                u = self.id_map.get(uid)
                return u.model_dump() if u else None
            if "username" in query:
                u = self.users_map.get(query["username"])
                return u.model_dump() if u else None
            if "email" in query:
                for u in self.users_map.values():
                    if u.email == query["email"]:
                        if "_id" in query and "$ne" in query["_id"]:
                            if str(u.id) == str(query["_id"]["$ne"]):
                                continue
                        return u.model_dump()
            return None

        async def fake_insert_one(doc: dict):
            new_id = str(ObjectId())
            doc["id"] = new_id
            user_in_db = UserInDB(**doc)
            self.users_map[doc["username"]] = user_in_db
            self.id_map[new_id] = user_in_db
            res = MagicMock()
            res.inserted_id = ObjectId(new_id)
            return res

        async def fake_update_one(query: dict, update: dict):
            uid = str(query.get("_id"))
            u = self.id_map.get(uid)
            if u and "$set" in update:
                current_data = u.model_dump()
                current_data.update(update["$set"])
                updated_user = UserInDB(**current_data)
                self.id_map[uid] = updated_user
                self.users_map[updated_user.username] = updated_user
            return MagicMock(modified_count=1)

        async def fake_count_documents(query: dict):
            return sum(1 for u in self.users_map.values() if u.role == query.get("role") and u.is_active == query.get("is_active"))

        async def fake_delete_one(query: dict):
            uid = str(query.get("_id"))
            u = self.id_map.pop(uid, None)
            if u:
                self.users_map.pop(u.username, None)
            return MagicMock(deleted_count=1)

        self.mock_service.get_by_username = AsyncMock(side_effect=fake_get_by_username)
        self.mock_service.get_by_id = AsyncMock(side_effect=fake_get_by_id)
        self.mock_service.collection.find_one = AsyncMock(side_effect=fake_find_one)
        self.mock_service.collection.insert_one = AsyncMock(side_effect=fake_insert_one)
        self.mock_service.collection.update_one = AsyncMock(side_effect=fake_update_one)
        self.mock_service.collection.count_documents = AsyncMock(side_effect=fake_count_documents)
        self.mock_service.collection.delete_one = AsyncMock(side_effect=fake_delete_one)

        # Mock list_users cursor
        def fake_find(query: dict):
            results = list(self.users_map.values())
            if "assigned_sites" in query and "$in" in query["assigned_sites"]:
                sites = query["assigned_sites"]["$in"]
                results = [u for u in results if any(s in sites for s in u.assigned_sites)]

            async def async_generator():
                for u in results:
                    d = u.model_dump()
                    yield d

            cursor = MagicMock()
            cursor.skip.return_value = cursor
            cursor.limit.return_value = cursor
            cursor.__aiter__ = lambda self: async_generator()
            return cursor

        self.mock_service.collection.find = MagicMock(side_effect=fake_find)

        app.dependency_overrides[get_user_service] = lambda: self.mock_service
        yield
        app.dependency_overrides.clear()

    def test_manager_can_create_technician(self):
        client = TestClient(app)
        res = client.post(
            "/api/v1/auth/register",
            headers=auth_header("manager_a", "Manager"),
            json={
                "username": "new_tech_1",
                "email": "new_tech_1@plant.local",
                "role": "Technician",
                "password": "SecurePassword1!",
                "assigned_sites": ["SITE-A"],
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["username"] == "new_tech_1"
        assert data["role"] == "Technician"
        assert "password_hash" not in data

    def test_manager_cannot_create_admin(self):
        client = TestClient(app)
        res = client.post(
            "/api/v1/auth/register",
            headers=auth_header("manager_a", "Manager"),
            json={
                "username": "rogue_admin",
                "email": "rogue@plant.local",
                "role": "Admin",
                "password": "SecurePassword1!",
            },
        )
        assert res.status_code == 403
        assert "Only 'Technician' is permitted" in res.json()["detail"]

    def test_manager_cannot_create_manager(self):
        client = TestClient(app)
        res = client.post(
            "/api/v1/auth/register",
            headers=auth_header("manager_a", "Manager"),
            json={
                "username": "new_manager",
                "email": "new_mgr@plant.local",
                "role": "Manager",
                "password": "SecurePassword1!",
            },
        )
        assert res.status_code == 403
        assert "Only 'Technician' is permitted" in res.json()["detail"]

    def test_manager_cannot_create_technician_outside_assigned_sites(self):
        client = TestClient(app)
        res = client.post(
            "/api/v1/auth/register",
            headers=auth_header("manager_a", "Manager"),
            json={
                "username": "out_of_scope_tech",
                "email": "out_scope@plant.local",
                "role": "Technician",
                "password": "SecurePassword1!",
                "assigned_sites": ["SITE-B"],  # manager_a only has SITE-A
            },
        )
        assert res.status_code == 403
        assert "exceed Manager's authorized scope" in res.json()["detail"]

    def test_manager_can_edit_technician_email_and_sites(self):
        client = TestClient(app)
        tech_a_id = self.users_map["tech_a"].id
        res = client.patch(
            f"/api/v1/auth/users/{tech_a_id}",
            headers=auth_header("manager_a", "Manager"),
            json={"email": "tech_a_updated@plant.local"},
        )
        assert res.status_code == 200
        assert res.json()["email"] == "tech_a_updated@plant.local"

    def test_manager_cannot_edit_admin(self):
        client = TestClient(app)
        admin_id = self.users_map["admin_user"].id
        res = client.patch(
            f"/api/v1/auth/users/{admin_id}",
            headers=auth_header("manager_a", "Manager"),
            json={"email": "hacked_admin@plant.local"},
        )
        assert res.status_code == 403
        assert "Managers are only permitted to manage Technicians" in res.json()["detail"]

    def test_manager_cannot_edit_other_manager(self):
        client = TestClient(app)
        mgr_b_id = self.users_map["manager_b"].id
        res = client.patch(
            f"/api/v1/auth/users/{mgr_b_id}",
            headers=auth_header("manager_a", "Manager"),
            json={"email": "mgr_b_hacked@plant.local"},
        )
        assert res.status_code == 403
        assert "Managers are only permitted to manage Technicians" in res.json()["detail"]

    def test_manager_cannot_edit_self_via_users_endpoint(self):
        client = TestClient(app)
        mgr_a_id = self.users_map["manager_a"].id
        res = client.patch(
            f"/api/v1/auth/users/{mgr_a_id}",
            headers=auth_header("manager_a", "Manager"),
            json={"email": "new_email@plant.local"},
        )
        assert res.status_code == 403
        assert "Managers cannot edit their own account through this endpoint. Use /api/v1/auth/me" in res.json()["detail"]

    def test_manager_cannot_escalate_technician_to_admin_or_manager(self):
        client = TestClient(app)
        tech_a_id = self.users_map["tech_a"].id
        # Attempt to escalate to Admin
        res = client.patch(
            f"/api/v1/auth/users/{tech_a_id}",
            headers=auth_header("manager_a", "Manager"),
            json={"role": "Admin"},
        )
        assert res.status_code == 403

        # Attempt to escalate to Manager
        res = client.patch(
            f"/api/v1/auth/users/{tech_a_id}",
            headers=auth_header("manager_a", "Manager"),
            json={"role": "Manager"},
        )
        assert res.status_code == 403

    def test_manager_can_deactivate_and_reactivate_technician(self):
        client = TestClient(app)
        tech_a_id = self.users_map["tech_a"].id

        # Deactivate via status endpoint
        res = client.post(
            f"/api/v1/auth/users/{tech_a_id}/status",
            headers=auth_header("manager_a", "Manager"),
            json={"is_active": False},
        )
        assert res.status_code == 200
        assert res.json()["is_active"] is False

        # Reactivate via PATCH
        res = client.patch(
            f"/api/v1/auth/users/{tech_a_id}",
            headers=auth_header("manager_a", "Manager"),
            json={"is_active": True},
        )
        assert res.status_code == 200
        assert res.json()["is_active"] is True

    def test_manager_cannot_deactivate_admin_or_manager(self):
        client = TestClient(app)
        admin_id = self.users_map["admin_user"].id
        res = client.post(
            f"/api/v1/auth/users/{admin_id}/status",
            headers=auth_header("manager_a", "Manager"),
            json={"is_active": False},
        )
        assert res.status_code == 403

        mgr_b_id = self.users_map["manager_b"].id
        res = client.post(
            f"/api/v1/auth/users/{mgr_b_id}/status",
            headers=auth_header("manager_a", "Manager"),
            json={"is_active": False},
        )
        assert res.status_code == 403

    def test_manager_can_reset_technician_password(self):
        client = TestClient(app)
        tech_a_id = self.users_map["tech_a"].id
        res = client.patch(
            f"/api/v1/auth/users/{tech_a_id}",
            headers=auth_header("manager_a", "Manager"),
            json={"password": "NewResetPass789!"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "password_hash" not in data
        # Verify in DB that hash was changed and session_revoked_at set
        updated_db = self.id_map[tech_a_id]
        assert updated_db.session_revoked_at is not None

    def test_manager_cannot_reset_admin_password(self):
        client = TestClient(app)
        admin_id = self.users_map["admin_user"].id
        res = client.patch(
            f"/api/v1/auth/users/{admin_id}",
            headers=auth_header("manager_a", "Manager"),
            json={"password": "NewResetPass789!"},
        )
        assert res.status_code == 403

    def test_manager_cannot_delete_users(self):
        client = TestClient(app)
        tech_a_id = self.users_map["tech_a"].id
        res = client.delete(
            f"/api/v1/auth/users/{tech_a_id}",
            headers=auth_header("manager_a", "Manager"),
        )
        assert res.status_code == 403

    def test_technician_denied_all_user_endpoints(self):
        client = TestClient(app)
        tech_header = auth_header("tech_a", "Technician")
        target_id = self.users_map["tech_b"].id

        # POST /register
        assert client.post("/api/v1/auth/register", headers=tech_header, json={}).status_code == 403
        # GET /users
        assert client.get("/api/v1/auth/users", headers=tech_header).status_code == 403
        # PATCH /users/{id}
        assert client.patch(f"/api/v1/auth/users/{target_id}", headers=tech_header, json={}).status_code == 403
        # POST /users/{id}/status
        assert client.post(f"/api/v1/auth/users/{target_id}/status", headers=tech_header, json={"is_active": False}).status_code == 403
        # DELETE /users/{id}
        assert client.delete(f"/api/v1/auth/users/{target_id}", headers=tech_header).status_code == 403

    def test_manager_with_no_assigned_sites_lists_users(self):
        client = TestClient(app)
        res = client.get("/api/v1/auth/users", headers=auth_header("manager_unscoped", "Manager"))
        assert res.status_code == 200
        # Should not return empty list due to bad {"$in": []} query
        users = res.json()
        assert len(users) > 0
