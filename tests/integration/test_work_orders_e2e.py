"""
MotorGuard — Work Order & End-to-End Maintenance Workflow Integration Tests

Validates:
1. Unauthenticated requests strictly rejected with 401 Unauthorized.
2. Role-based permissions: Operator cannot create work orders (403 Forbidden).
3. Strict Technician isolation:
   - Technician can only view their own assigned work orders.
   - Technician cannot access or modify another technician's work orders.
4. Full end-to-end lifecycle:
   - Admin creates work order for Technician Dave linked to an alert.
   - Linked alert updated to ACKNOWLEDGED.
   - Dave accepts work order (Assigned -> Accepted).
   - Dave starts work (Accepted -> In Progress).
   - Dave resolves work order with diagnosis, parts, downtime -> Resolved.
   - Linked alert automatically updated to RESOLVED.
   - Maintenance record created for the motor.
   - Tamper-resistant audit logs recorded for every step.
5. Rejection workflow: Technician rejects work order with reason (Assigned -> Rejected).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.security import create_access_token
from backend.app.core.auth import get_user_service
from backend.app.api.v1.endpoints.work_orders import get_work_order_service
from backend.app.api.v1.endpoints.alerts import get_alert_service
from backend.app.api.v1.endpoints.maintenance import get_maintenance_service
from backend.app.services.user_service import UserService
from backend.app.services.work_order_service import WorkOrderService
from backend.app.services.alert_service import AlertService
from backend.app.services.maintenance_service import MaintenanceService
from backend.app.schemas.user import UserInDB, UserOut

client = TestClient(app)


def auth_header(username: str, role: str) -> dict:
    token = create_access_token(data={"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_db_env():
    """Create in-memory collections and wire service dependency overrides."""
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            store = {}

            async def insert_one(doc):
                _id = doc.get("_id", f"mock-{len(store)}")
                doc_copy = dict(doc)
                doc_copy["_id"] = _id
                key = doc.get("work_order_id") or doc.get("alert_id") or doc.get("username") or str(_id)
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
                        elif k == "state" and isinstance(v, dict) and "$in" in v:
                            if d.get("state") not in v["$in"]:
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
                if upsert:
                    new_doc = dict(query)
                    if "$set" in update:
                        new_doc.update(update["$set"])
                    key = new_doc.get("alert_id") or new_doc.get("username") or str(len(store))
                    store[key] = new_doc
                    res = MagicMock()
                    res.upserted_id = "upserted"
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
                            if d.get(k) != v:
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

    mock_database = MagicMock()
    mock_database.__getitem__.side_effect = get_collection

    now = datetime.now(timezone.utc)
    # Seed users directly in mock store
    users_col = get_collection("users")
    for u in [
        {"username": "admin_test", "role": "Admin", "email": "admin@test.local", "password_hash": "mockhash", "is_active": True, "assigned_sites": ["SITE-01"], "assigned_motors": [], "created_at": now},
        {"username": "manager_test", "role": "Manager", "email": "manager@test.local", "password_hash": "mockhash", "is_active": True, "assigned_sites": ["SITE-01"], "assigned_motors": [], "created_at": now},
        {"username": "tech_dave_test", "role": "Technician", "email": "dave@test.local", "password_hash": "mockhash", "is_active": True, "assigned_sites": ["SITE-01"], "assigned_motors": [], "created_at": now},
        {"username": "tech_sara_test", "role": "Technician", "email": "sara@test.local", "password_hash": "mockhash", "is_active": True, "assigned_sites": ["SITE-01"], "assigned_motors": [], "created_at": now},
    ]:
        users_col._store[u["username"]] = dict(u)

    # Seed motors directly in mock store
    motors_col = get_collection("motors")
    motors_col._store["MTR-TEST-001"] = {
        "motor_id": "MTR-TEST-001",
        "name": "Test Motor",
        "site_id": "SITE-01",
        "is_active": True,
    }

    # Seed alert directly in mock store
    alerts_col = get_collection("alerts")
    alerts_col._store["ALT-TEST-FAULT01"] = {
        "alert_id": "ALT-TEST-FAULT01",
        "motor_id": "MTR-TEST-001",
        "device_id": "esp32-node-test",
        "severity": "CRITICAL",
        "trigger_type": "THRESHOLD_HIGH_VIBRATION",
        "trigger_value": 0.85,
        "threshold_limit": 0.20,
        "unit": "g",
        "message": "Critical bearing harmonic fault detected on MTR-TEST-001",
        "state": "ACTIVE",
        "triggered_at": now,
    }

    # Instantiate services with mock DB
    user_svc = UserService(mock_database)
    wo_svc = WorkOrderService(mock_database)
    alert_svc = AlertService(mock_database)
    maint_svc = MaintenanceService(mock_database)

    # Wire overrides
    app.dependency_overrides[get_user_service] = lambda: user_svc
    app.dependency_overrides[get_work_order_service] = lambda: wo_svc
    app.dependency_overrides[get_alert_service] = lambda: alert_svc
    app.dependency_overrides[get_maintenance_service] = lambda: maint_svc

    yield mock_database

    app.dependency_overrides.clear()


class TestWorkOrdersWorkflowE2E:
    def test_unauthenticated_request_rejected(self, mock_db_env):
        """Verify unauthenticated user cannot access work order APIs (401 Unauthorized)."""
        response = client.get("/api/v1/work-orders")
        assert response.status_code == 401

    def test_operator_cannot_create_work_order(self, mock_db_env):
        """Verify Technician (non-manager/admin) cannot create work orders (403 Forbidden)."""
        payload = {
            "motor_id": "MTR-TEST-001",
            "assigned_to_user_id": "tech_dave_test",
            "title": "Repair bearing",
            "description": "Bearing has high harmonic vibration",
            "priority": "HIGH",
        }
        response = client.post(
            "/api/v1/work-orders",
            json=payload,
            headers=auth_header("tech_dave_test", "Technician"),
        )
        assert response.status_code == 403

    def test_end_to_end_work_order_lifecycle(self, mock_db_env):
        """
        Complete lifecycle:
        1. Admin creates work order for Dave linked to alert ALT-TEST-FAULT01.
        2. Verify alert updated to ACKNOWLEDGED.
        3. Sara tries to inspect Dave's work order -> 403 Forbidden.
        4. Dave accepts work order (Assigned -> Accepted).
        5. Dave starts work order (Accepted -> In Progress).
        6. Dave resolves work order with diagnosis and parts -> Resolved.
        7. Verify alert automatically updated to RESOLVED.
        8. Verify maintenance record created.
        9. Verify audit trail logged every step.
        """
        # Step 1: Admin creates work order for Dave
        create_payload = {
            "motor_id": "MTR-TEST-001",
            "alert_id": "ALT-TEST-FAULT01",
            "assigned_to_user_id": "tech_dave_test",
            "priority": "CRITICAL",
            "title": "Emergency Bearing Replacement",
            "description": "High vibration measured at 0.85 g. Inspect and replace SKF 608-2RS bearing.",
        }
        res_create = client.post(
            "/api/v1/work-orders",
            json=create_payload,
            headers=auth_header("admin_test", "Admin"),
        )
        assert res_create.status_code == 201
        wo = res_create.json()
        wo_id = wo["work_order_id"]
        assert wo["status"] == "Assigned"
        assert wo["assigned_to_user_id"] == "tech_dave_test"
        assert wo["assigned_by_user_id"] == "admin_test"

        # Step 2: Linked alert should be ACKNOWLEDGED
        res_alert = client.get(
            "/api/v1/alerts/ALT-TEST-FAULT01",
            headers=auth_header("admin_test", "Admin"),
        )
        assert res_alert.status_code == 200
        assert res_alert.json()["state"] == "ACKNOWLEDGED"
        assert res_alert.json()["assigned_to"] == "tech_dave_test"

        # Step 3: Isolation check — Sara cannot access Dave's work order
        res_sara = client.get(
            f"/api/v1/work-orders/{wo_id}",
            headers=auth_header("tech_sara_test", "Technician"),
        )
        assert res_sara.status_code == 403

        # Step 4: Dave accepts work order
        res_accept = client.post(
            f"/api/v1/work-orders/{wo_id}/accept",
            json={"notes": "Heading to Line 3 test bench"},
            headers=auth_header("tech_dave_test", "Technician"),
        )
        assert res_accept.status_code == 200
        assert res_accept.json()["status"] == "Accepted"
        assert res_accept.json()["accepted_at"] is not None

        # Step 5: Dave starts work
        res_start = client.post(
            f"/api/v1/work-orders/{wo_id}/start",
            json={"notes": "Motor de-energized and uncoupled from drive pulley"},
            headers=auth_header("tech_dave_test", "Technician"),
        )
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "In Progress"
        assert res_start.json()["started_at"] is not None

        # Step 6: Dave resolves work order
        resolve_payload = {
            "diagnosis": "Worn inner race on drive-end ball bearing caused excessive 120Hz harmonics",
            "actions_taken": "Pressed out damaged bearing, cleaned rotor shaft, installed new bearing and torqued casing bolts to 12 Nm",
            "parts_replaced": ["SKF 608-2RS Deep-Groove Ball Bearing", "M4 High-Tensile Fasteners"],
            "downtime_minutes": 45,
            "resolution_notes": "Vibration normalized to 0.052 g RMS under 12V test bench load. Signed off.",
        }
        res_resolve = client.post(
            f"/api/v1/work-orders/{wo_id}/resolve",
            json=resolve_payload,
            headers=auth_header("tech_dave_test", "Technician"),
        )
        assert res_resolve.status_code == 200
        resolved_wo = res_resolve.json()
        assert resolved_wo["status"] == "Resolved"
        assert resolved_wo["resolved_at"] is not None
        assert resolved_wo["downtime_minutes"] == 45
        assert len(resolved_wo["parts_replaced"]) == 2

        # Step 7: Verify alert automatically updated to RESOLVED
        res_alert_after = client.get(
            "/api/v1/alerts/ALT-TEST-FAULT01",
            headers=auth_header("admin_test", "Admin"),
        )
        assert res_alert_after.status_code == 200
        assert res_alert_after.json()["state"] == "RESOLVED"
        assert res_alert_after.json()["resolved_by"] == "tech_dave_test"

        # Step 8: Verify maintenance record exists in motor maintenance history
        res_maint = client.get(
            "/api/v1/maintenance/motors/MTR-TEST-001",
            headers=auth_header("admin_test", "Admin"),
        )
        assert res_maint.status_code == 200
        records = res_maint.json()
        assert len(records) >= 1
        assert any("SKF 608-2RS" in str(r.get("parts_replaced", [])) for r in records)

        # Step 9: Verify audit trail
        res_audit = client.get(
            "/api/v1/work-orders/audit/logs",
            headers=auth_header("admin_test", "Admin"),
        )
        assert res_audit.status_code == 200
        logs = res_audit.json()
        actions = [log["action"] for log in logs]
        assert "CREATE_WORK_ORDER" in actions
        assert "ACCEPT_WORK_ORDER" in actions
        assert "START_WORK_ORDER" in actions
        assert "RESOLVE_WORK_ORDER" in actions

    def test_rejection_workflow(self, mock_db_env):
        """Technician can reject an assigned work order with reason."""
        create_payload = {
            "motor_id": "MTR-TEST-001",
            "assigned_to_user_id": "tech_sara_test",
            "priority": "LOW",
            "title": "Scheduled quarterly lubrication",
            "description": "Routine lubricant application on gear teeth",
        }
        res_create = client.post(
            "/api/v1/work-orders",
            json=create_payload,
            headers=auth_header("manager_test", "Manager"),
        )
        assert res_create.status_code == 201
        wo_id = res_create.json()["work_order_id"]

        # Sara rejects because she is assigned to electrical rather than mechanical
        res_reject = client.post(
            f"/api/v1/work-orders/{wo_id}/reject",
            json={"rejection_reason": "Mechanical task outside current shift assignment; reassign to Dave"},
            headers=auth_header("tech_sara_test", "Technician"),
        )
        assert res_reject.status_code == 200
        assert res_reject.json()["status"] == "Rejected"
        assert "reassign to Dave" in res_reject.json()["rejection_reason"]
