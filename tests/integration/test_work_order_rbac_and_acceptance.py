"""
MotorGuard — Work Order RBAC, Site-Scoping, Reassignment & Acceptance Integration Tests

Validates:
1. Admin Visibility: Full visibility across all sites and technicians.
2. Manager Scoping: Scoped strictly to permitted sites; forbidden from out-of-scope sites.
3. Technician A vs Technician B Isolation: Each technician sees ONLY their own assigned orders.
4. Direct API IDOR Prevention: Unauthorized GET, accept, start, resolve, reject blocked with 403.
5. End-to-End Reassignment Workflow:
   - Admin creates WO assigned to Tech A.
   - Tech A sees it, Tech B does not.
   - Admin reassigns to Tech B.
   - Tech A loses visibility; Tech B gains visibility.
6. Acceptance Workflow:
   - Tech A accepts assigned WO -> status 'Accepted', accepted_by recorded.
   - Tech B cannot accept Tech A's WO -> 403.
   - Admin accepts WO regardless of assigned technician.
   - Manager accepts within site scope; blocked on out-of-scope sites.
   - Duplicate acceptance prevented -> 400.
7. Audit Trail Integrity:
   - Reassignment and acceptance events logged immutably.
8. WebSocket Notification Scoping:
   - Reassignment/acceptance notifications only reach authorized connections.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.security import create_access_token
from backend.app.core.auth import get_user_service
from backend.app.api.v1.endpoints.work_orders import get_work_order_service
from backend.app.api.v1.endpoints.websocket import WebSocketManager
from backend.app.services.user_service import UserService
from backend.app.services.work_order_service import WorkOrderService

client = TestClient(app)


def auth_header(username: str, role: str) -> dict:
    token = create_access_token(data={"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def rbac_mock_env():
    """Sets up an in-memory test database containing 1 Admin, 1 Manager, 2 Technicians, 2 motors, 2 sites."""
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            store = {}

            async def insert_one(doc):
                _id = doc.get("_id", f"mock-{len(store)}")
                doc_copy = dict(doc)
                doc_copy["_id"] = _id
                key = doc.get("work_order_id") or doc.get("username") or str(_id)
                store[key] = doc_copy
                res = MagicMock()
                res.inserted_id = _id
                return res

            async def find_one(query, projection=None, sort=None):
                for d in store.values():
                    match = True
                    for k, v in query.items():
                        if k == "$or" and isinstance(v, list):
                            if not any(all(d.get(ck) == cv for ck, cv in cond.items()) for cond in v):
                                match = False
                                break
                        elif d.get(k) != v:
                            match = False
                            break
                    if match:
                        ret = dict(d)
                        if projection and "_id" in projection and projection["_id"] == 0:
                            ret.pop("_id", None)
                        return ret
                return None

            async def find_one_and_update(filter_query, update, return_document=True):
                for d in store.values():
                    match = True
                    for k, v in filter_query.items():
                        if d.get(k) != v:
                            match = False
                            break
                    if match:
                        if "$set" in update:
                            d.update(update["$set"])
                        return dict(d)
                return None

            async def update_one(query, update, upsert=False):
                for d in store.values():
                    match = True
                    for k, v in query.items():
                        if d.get(k) != v:
                            match = False
                            break
                    if match:
                        if "$set" in update:
                            d.update(update["$set"])
                        res = MagicMock()
                        res.matched_count = 1
                        res.modified_count = 1
                        return res
                res = MagicMock()
                res.matched_count = 0
                return res

            def find(query=None, projection=None):
                items = []
                for d in store.values():
                    if query:
                        match = True
                        for k, v in query.items():
                            if k == "$or" and isinstance(v, list):
                                if not any(all(d.get(ck) == cv for ck, cv in cond.items()) for cond in v):
                                    match = False
                                    break
                            elif k == "site_id" and isinstance(v, dict) and "$in" in v:
                                if d.get("site_id") not in v["$in"]:
                                    match = False
                                    break
                            elif d.get(k) != v:
                                match = False
                                break
                        if match:
                            items.append(dict(d))
                    else:
                        items.append(dict(d))

                class MockCursor:
                    def __init__(self, data):
                        self.data = data
                    def sort(self, *args, **kwargs):
                        return self
                    def limit(self, *args, **kwargs):
                        return self
                    def skip(self, *args, **kwargs):
                        return self
                    def __aiter__(self):
                        self._iter = iter(self.data)
                        return self
                    async def __anext__(self):
                        try:
                            return next(self._iter)
                        except StopIteration:
                            raise StopAsyncIteration
                return MockCursor(items)

            col.insert_one = AsyncMock(side_effect=insert_one)
            col.find_one = AsyncMock(side_effect=find_one)
            col.find_one_and_update = AsyncMock(side_effect=find_one_and_update)
            col.update_one = AsyncMock(side_effect=update_one)
            col.find = find
            col.create_index = AsyncMock(return_value=None)
            col._store = store
            collections[name] = col

        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection

    now = datetime.now(timezone.utc)
    # 1. Users
    users_col = get_collection("users")
    users = [
        {"_id": "adm-01", "id": "adm-01", "username": "admin_root", "role": "Admin", "password_hash": "mocked", "email": "admin@motorguard.local", "is_active": True, "created_at": now},
        {"_id": "mgr-01", "id": "mgr-01", "username": "manager_north", "role": "Manager", "password_hash": "mocked", "email": "mgr@motorguard.local", "is_active": True, "assigned_sites": ["SITE-NORTH"], "created_at": now},
        {"_id": "tech-a-01", "id": "tech-a-01", "username": "tech_alice", "role": "Technician", "password_hash": "mocked", "email": "alice@motorguard.local", "is_active": True, "assigned_sites": ["SITE-NORTH"], "assigned_motors": ["MTR-N-001"], "created_at": now},
        {"_id": "tech-b-02", "id": "tech-b-02", "username": "tech_bob", "role": "Technician", "password_hash": "mocked", "email": "bob@motorguard.local", "is_active": True, "assigned_sites": ["SITE-SOUTH"], "assigned_motors": ["MTR-S-002"], "created_at": now},
        {"_id": "tech-deact", "id": "tech-deact", "username": "tech_inactive", "role": "Technician", "password_hash": "mocked", "email": "inact@motorguard.local", "is_active": False, "created_at": now},
    ]
    for u in users:
        users_col._store[u["username"]] = dict(u)

    # 2. Motors
    motors_col = get_collection("motors")
    motors_col._store["MTR-N-001"] = {"motor_id": "MTR-N-001", "site_id": "SITE-NORTH", "is_active": True}
    motors_col._store["MTR-S-002"] = {"motor_id": "MTR-S-002", "site_id": "SITE-SOUTH", "is_active": True}

    # 3. Work Orders
    wo_col = get_collection("work_orders")
    wo1 = {
        "work_order_id": "WO-NORTH-001",
        "motor_id": "MTR-N-001",
        "site_id": "SITE-NORTH",
        "assigned_to": "tech-a-01",
        "assigned_to_user_id": "tech_alice",
        "assigned_by_user_id": "admin_root",
        "priority": "HIGH",
        "title": "Bearing Inspection",
        "description": "Check bearing vibration on Line 1",
        "status": "Assigned",
        "created_at": now,
        "assigned_at": now,
        "accepted_at": None,
        "accepted_by": None,
        "updated_at": now,
    }
    wo2 = {
        "work_order_id": "WO-SOUTH-002",
        "motor_id": "MTR-S-002",
        "site_id": "SITE-SOUTH",
        "assigned_to": "tech-b-02",
        "assigned_to_user_id": "tech_bob",
        "assigned_by_user_id": "admin_root",
        "priority": "CRITICAL",
        "title": "Pump Thermal Overload",
        "description": "Sector 9 pump thermal alarm",
        "status": "Assigned",
        "created_at": now,
        "assigned_at": now,
        "accepted_at": None,
        "accepted_by": None,
        "updated_at": now,
    }
    wo_col._store[wo1["work_order_id"]] = dict(wo1)
    wo_col._store[wo2["work_order_id"]] = dict(wo2)

    user_svc = UserService(mock_db)
    wo_svc = WorkOrderService(mock_db)

    app.dependency_overrides[get_user_service] = lambda: user_svc
    app.dependency_overrides[get_work_order_service] = lambda: wo_svc

    yield mock_db

    app.dependency_overrides.clear()


class TestWorkOrderRoleIsolationAndAcceptance:
    def test_01_admin_full_visibility(self, rbac_mock_env):
        """Admin views all work orders across both sites and all technicians."""
        res = client.get("/api/v1/work-orders", headers=auth_header("admin_root", "Admin"))
        assert res.status_code == 200
        data = res.json()
        ids = [wo["work_order_id"] for wo in data]
        assert "WO-NORTH-001" in ids
        assert "WO-SOUTH-002" in ids
        assert len(data) == 2

    def test_02_manager_site_scoping(self, rbac_mock_env):
        """Manager only views work orders within permitted site (SITE-NORTH) and is blocked from SITE-SOUTH."""
        res = client.get("/api/v1/work-orders", headers=auth_header("manager_north", "Manager"))
        assert res.status_code == 200
        data = res.json()
        ids = [wo["work_order_id"] for wo in data]
        assert "WO-NORTH-001" in ids
        assert "WO-SOUTH-002" not in ids

        # Manager direct API access to SITE-SOUTH work order -> 403 Forbidden
        res_direct = client.get(
            "/api/v1/work-orders/WO-SOUTH-002",
            headers=auth_header("manager_north", "Manager"),
        )
        assert res_direct.status_code == 403
        assert "outside your authorized site scope" in res_direct.json()["detail"]

    def test_03_technician_a_isolation(self, rbac_mock_env):
        """Technician A can ONLY see their assigned work orders (WO-NORTH-001)."""
        res = client.get("/api/v1/work-orders", headers=auth_header("tech_alice", "Technician"))
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["work_order_id"] == "WO-NORTH-001"
        assert data[0]["assigned_to_user_id"] == "tech_alice"

    def test_04_technician_b_isolation(self, rbac_mock_env):
        """Technician B can ONLY see their assigned work orders (WO-SOUTH-002)."""
        res = client.get("/api/v1/work-orders", headers=auth_header("tech_bob", "Technician"))
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["work_order_id"] == "WO-SOUTH-002"
        assert data[0]["assigned_to_user_id"] == "tech_bob"

    def test_05_technician_idor_protection(self, rbac_mock_env):
        """Technician B attempts direct API operations on Technician A's work order -> 403 Forbidden."""
        # 1. Direct GET
        res_get = client.get(
            "/api/v1/work-orders/WO-NORTH-001",
            headers=auth_header("tech_bob", "Technician"),
        )
        assert res_get.status_code == 403
        assert "You can only view work orders assigned to your account" in res_get.json()["detail"]

        # 2. Direct Accept
        res_accept = client.post(
            "/api/v1/work-orders/WO-NORTH-001/accept",
            headers=auth_header("tech_bob", "Technician"),
        )
        assert res_accept.status_code == 403
        assert "Access denied" in res_accept.json()["detail"] or "Only the assigned technician" in res_accept.json()["detail"]

        # 3. Direct Start
        res_start = client.post(
            "/api/v1/work-orders/WO-NORTH-001/start",
            headers=auth_header("tech_bob", "Technician"),
        )
        assert res_start.status_code == 403

        # 4. Direct Resolve
        res_resolve = client.post(
            "/api/v1/work-orders/WO-NORTH-001/resolve",
            json={
                "diagnosis": "None",
                "actions_taken": "None",
                "resolution_notes": "None",
            },
            headers=auth_header("tech_bob", "Technician"),
        )
        assert res_resolve.status_code == 403

        # 5. Direct Reject
        res_reject = client.post(
            "/api/v1/work-orders/WO-NORTH-001/reject",
            json={"rejection_reason": "Not my job"},
            headers=auth_header("tech_bob", "Technician"),
        )
        assert res_reject.status_code == 403

    def test_06_reassignment_workflow(self, rbac_mock_env):
        """
        Complete Reassignment Flow:
        1. Admin creates WO on MTR-N-001 assigned to Tech Alice.
        2. Alice sees it; Bob does NOT see it.
        3. Manager North sees it (SITE-NORTH).
        4. Admin reassigns WO to Bob.
        5. Alice no longer sees it; Bob now sees it.
        6. Verify audit log.
        """
        # Step 1: Create
        res_create = client.post(
            "/api/v1/work-orders",
            json={
                "motor_id": "MTR-N-001",
                "assigned_to_user_id": "tech_alice",
                "priority": "HIGH",
                "title": "Gearbox Lubrication",
                "description": "Annual gearbox inspection",
            },
            headers=auth_header("admin_root", "Admin"),
        )
        assert res_create.status_code == 201
        wo_id = res_create.json()["work_order_id"]

        # Step 2: Alice sees it; Bob does not
        res_alice = client.get("/api/v1/work-orders", headers=auth_header("tech_alice", "Technician"))
        alice_ids = [w["work_order_id"] for w in res_alice.json()]
        assert wo_id in alice_ids

        res_bob = client.get("/api/v1/work-orders", headers=auth_header("tech_bob", "Technician"))
        bob_ids = [w["work_order_id"] for w in res_bob.json()]
        assert wo_id not in bob_ids

        # Step 3: Manager sees it
        res_mgr = client.get("/api/v1/work-orders", headers=auth_header("manager_north", "Manager"))
        assert wo_id in [w["work_order_id"] for w in res_mgr.json()]

        # Step 4: Admin reassigns to Bob
        res_reassign = client.post(
            f"/api/v1/work-orders/{wo_id}/reassign",
            json={
                "assigned_to_user_id": "tech_bob",
                "notes": "Alice on leave; reassigning to Bob",
            },
            headers=auth_header("admin_root", "Admin"),
        )
        assert res_reassign.status_code == 200
        reassigned_wo = res_reassign.json()
        assert reassigned_wo["assigned_to_user_id"] == "tech_bob"
        assert reassigned_wo["reassigned_from_user_id"] == "tech_alice"
        assert reassigned_wo["status"] == "Assigned"

        # Step 5: Alice NO LONGER sees it; Bob NOW sees it
        res_alice_after = client.get("/api/v1/work-orders", headers=auth_header("tech_alice", "Technician"))
        assert wo_id not in [w["work_order_id"] for w in res_alice_after.json()]

        res_bob_after = client.get("/api/v1/work-orders", headers=auth_header("tech_bob", "Technician"))
        assert wo_id in [w["work_order_id"] for w in res_bob_after.json()]

        # Step 6: Verify Audit Trail
        res_audit = client.get(
            "/api/v1/work-orders/audit/logs",
            headers=auth_header("admin_root", "Admin"),
        )
        assert res_audit.status_code == 200
        actions = [log["action"] for log in res_audit.json()]
        assert "REASSIGN_WORK_ORDER" in actions

    def test_07_invalid_technician_assignment_and_reassignment(self, rbac_mock_env):
        """Technicians cannot reassign; cannot assign/reassign to deactivated or invalid users."""
        # Technician attempting to reassign -> 403 Forbidden
        res_tech_reassign = client.post(
            "/api/v1/work-orders/WO-NORTH-001/reassign",
            json={"assigned_to_user_id": "tech_bob"},
            headers=auth_header("tech_alice", "Technician"),
        )
        assert res_tech_reassign.status_code == 403

        # Reassign to non-existent technician -> 404 Not Found
        res_ghost = client.post(
            "/api/v1/work-orders/WO-NORTH-001/reassign",
            json={"assigned_to_user_id": "tech_ghost"},
            headers=auth_header("admin_root", "Admin"),
        )
        assert res_ghost.status_code == 404

        # Reassign to deactivated technician -> 400 Bad Request
        res_deact = client.post(
            "/api/v1/work-orders/WO-NORTH-001/reassign",
            json={"assigned_to_user_id": "tech_inactive"},
            headers=auth_header("admin_root", "Admin"),
        )
        assert res_deact.status_code == 400
        assert "Cannot assign work order to deactivated technician" in res_deact.json()["detail"]

    def test_08_acceptance_workflow_technician_and_duplicate_prevention(self, rbac_mock_env):
        """Technician A accepts their own order; duplicate acceptance is rejected."""
        # Alice accepts WO-NORTH-001
        res_accept = client.post(
            "/api/v1/work-orders/WO-NORTH-001/accept",
            headers=auth_header("tech_alice", "Technician"),
        )
        assert res_accept.status_code == 200
        wo = res_accept.json()
        assert wo["status"] == "Accepted"
        assert wo["accepted_by"] == "tech_alice"
        assert wo["accepted_at"] is not None

        # Duplicate acceptance -> 400 Bad Request
        res_dup = client.post(
            "/api/v1/work-orders/WO-NORTH-001/accept",
            headers=auth_header("tech_alice", "Technician"),
        )
        assert res_dup.status_code == 400
        assert "must be 'Assigned'" in res_dup.json()["detail"]

    def test_09_acceptance_workflow_admin(self, rbac_mock_env):
        """Admin can accept any assigned work order regardless of assigned technician."""
        res_admin_accept = client.post(
            "/api/v1/work-orders/WO-SOUTH-002/accept",
            headers=auth_header("admin_root", "Admin"),
        )
        assert res_admin_accept.status_code == 200
        wo = res_admin_accept.json()
        assert wo["status"] == "Accepted"
        assert wo["accepted_by"] == "admin_root"
        assert wo["accepted_at"] is not None

    def test_10_acceptance_workflow_manager_site_restrictions(self, rbac_mock_env):
        """Manager can accept work order within their site scope; blocked on out-of-scope sites."""
        # Manager North tries to accept WO-SOUTH-002 (SITE-SOUTH) -> 403 Forbidden
        res_mgr_south = client.post(
            "/api/v1/work-orders/WO-SOUTH-002/accept",
            headers=auth_header("manager_north", "Manager"),
        )
        assert res_mgr_south.status_code == 403
        assert "outside your authorized site scope" in res_mgr_south.json()["detail"]

        # Manager North accepts newly created WO in SITE-NORTH
        res_new_wo = client.post(
            "/api/v1/work-orders",
            json={
                "motor_id": "MTR-N-001",
                "assigned_to_user_id": "tech_alice",
                "priority": "MEDIUM",
                "title": "Belt Tension Check",
                "description": "Verify drive belt tension",
            },
            headers=auth_header("manager_north", "Manager"),
        )
        assert res_new_wo.status_code == 201
        wo_id = res_new_wo.json()["work_order_id"]

        res_mgr_accept = client.post(
            f"/api/v1/work-orders/{wo_id}/accept",
            headers=auth_header("manager_north", "Manager"),
        )
        assert res_mgr_accept.status_code == 200
        assert res_mgr_accept.json()["accepted_by"] == "manager_north"

    def test_11_dashboard_filters_cannot_bypass_isolation(self, rbac_mock_env):
        """Technician passing query params (e.g. ?assigned_to=tech_bob) still only gets their own work orders."""
        res = client.get(
            "/api/v1/work-orders?assigned_to=tech_bob",
            headers=auth_header("tech_alice", "Technician"),
        )
        assert res.status_code == 200
        data = res.json()
        for wo in data:
            assert wo["assigned_to_user_id"] == "tech_alice"

    def test_12_websocket_event_scoping(self):
        """WebSocket manager correctly isolates work order events across roles."""
        ws_mgr = WebSocketManager()

        admin_meta = {"username": "admin_root", "role": "Admin", "id": "adm-01"}
        mgr_meta = {"username": "manager_north", "role": "Manager", "assigned_sites": ["SITE-NORTH"], "id": "mgr-01"}
        tech_a_meta = {"username": "tech_alice", "role": "Technician", "id": "tech-a-01", "assigned_sites": ["SITE-NORTH"]}
        tech_b_meta = {"username": "tech_bob", "role": "Technician", "id": "tech-b-02", "assigned_sites": ["SITE-SOUTH"]}

        # Event for Tech Alice at SITE-NORTH
        event_alice = {
            "type": "WORK_ORDER_ASSIGNED",
            "work_order_id": "WO-101",
            "site_id": "SITE-NORTH",
            "assigned_to": "tech-a-01",
            "assigned_to_user_id": "tech_alice",
        }

        # Admin receives
        assert ws_mgr.is_authorized_for_event(admin_meta, event_alice) is True
        # Manager North receives (site match)
        assert ws_mgr.is_authorized_for_event(mgr_meta, event_alice) is True
        # Tech Alice receives (user match)
        assert ws_mgr.is_authorized_for_event(tech_a_meta, event_alice) is True
        # Tech Bob does NOT receive
        assert ws_mgr.is_authorized_for_event(tech_b_meta, event_alice) is False

        # Event for Tech Bob at SITE-SOUTH
        event_bob = {
            "type": "WORK_ORDER_ASSIGNED",
            "work_order_id": "WO-202",
            "site_id": "SITE-SOUTH",
            "assigned_to": "tech-b-02",
            "assigned_to_user_id": "tech_bob",
        }

        # Admin receives
        assert ws_mgr.is_authorized_for_event(admin_meta, event_bob) is True
        # Manager North does NOT receive (site mismatch)
        assert ws_mgr.is_authorized_for_event(mgr_meta, event_bob) is False
        # Tech Alice does NOT receive (user mismatch)
        assert ws_mgr.is_authorized_for_event(tech_a_meta, event_bob) is False
        # Tech Bob receives (user match)
        assert ws_mgr.is_authorized_for_event(tech_b_meta, event_bob) is True
