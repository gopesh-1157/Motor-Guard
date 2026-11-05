"""
Gravitas End-to-End Verification Runner for Work Order Operations
Tests all 12 operational capabilities and RBAC invariant rules across Admin, Manager, and Technicians.
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.security import create_access_token
from backend.app.api.v1.endpoints.websocket import WebSocketManager

def auth_header(username: str, role: str) -> dict:
    token = create_access_token(data={"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}

class VerificationSuite:
    def __init__(self):
        self.results = []

    def record(self, step_id: str, description: str, passed: bool, evidence: str):
        self.results.append({
            "id": step_id,
            "description": description,
            "passed": passed,
            "evidence": evidence
        })
        status_str = "PASS" if passed else "FAIL"
        print(f"[{status_str}] {step_id}: {description}")
        print(f"       EVIDENCE: {evidence}")

    def summary(self) -> bool:
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        print("\n" + "="*70)
        print(f"GRAVITAS VERIFICATION SUMMARY: {passed}/{total} Passed, {failed} Failed")
        print("="*70)
        return failed == 0

def run_verification() -> bool:
    suite = VerificationSuite()
    print("Starting Gravitas Comprehensive Operational Verification...\n")

    with TestClient(app) as client:
        # 1. Admin Full Fleet Visibility
        res = client.get("/api/v1/work-orders", headers=auth_header("admin", "Admin"))
        if res.status_code == 200:
            orders = res.json()
            techs_seen = {o.get("assigned_to_user_id") for o in orders if o.get("assigned_to_user_id")}
            suite.record(
                "OP-01",
                "Admin Fleet-Wide Visibility (Retrieves all orders across all technicians)",
                passed=len(orders) >= 2,
                evidence=f"Status: {res.status_code}, Found {len(orders)} orders for technicians: {techs_seen}"
            )
        else:
            suite.record("OP-01", "Admin Fleet-Wide Visibility", False, f"HTTP {res.status_code}: {res.text}")

        # 2. Admin Create Work Order
        create_payload = {
            "motor_id": "MTR-775-001",
            "assigned_to_user_id": "Rathinam",
            "priority": "HIGH",
            "title": "Vibration Damping Inspection",
            "description": "Inspect neoprene vibration mounts and verify alignment under load."
        }
        res = client.post("/api/v1/work-orders", json=create_payload, headers=auth_header("admin", "Admin"))
        created_wo_id = None
        if res.status_code == 201:
            data = res.json()
            created_wo_id = data["work_order_id"]
            suite.record(
                "OP-02",
                "Admin Create Work Order (Dispatches order to technician with correct initial state)",
                passed=(data["status"] == "Assigned" and data["assigned_to_user_id"] == "Rathinam"),
                evidence=f"Created {created_wo_id}, status={data['status']}, assigned_to_user_id={data['assigned_to_user_id']}"
            )
        else:
            suite.record("OP-02", "Admin Create Work Order", False, f"HTTP {res.status_code}: {res.text}")

        # 3. Technician Isolation - Rathinam sees the order
        res_rathinam = client.get("/api/v1/work-orders", headers=auth_header("Rathinam", "Technician"))
        rathinam_order_ids = [o["work_order_id"] for o in res_rathinam.json()] if res_rathinam.status_code == 200 else []
        suite.record(
            "OP-03",
            "Technician Isolation - Assignee Visibility (Rathinam sees newly dispatched order)",
            passed=(created_wo_id in rathinam_order_ids),
            evidence=f"Rathinam orders count: {len(rathinam_order_ids)}, created_wo_id present: {created_wo_id in rathinam_order_ids}"
        )

        # 4. Technician Isolation - tech_dave CANNOT see Rathinam's order
        res_dave = client.get("/api/v1/work-orders", headers=auth_header("tech_dave", "Technician"))
        dave_order_ids = [o["work_order_id"] for o in res_dave.json()] if res_dave.status_code == 200 else []
        suite.record(
            "OP-04",
            "Technician Isolation - Unassigned Technician Exclusion (tech_dave cannot see Rathinam's order)",
            passed=(created_wo_id not in dave_order_ids),
            evidence=f"tech_dave orders count: {len(dave_order_ids)}, created_wo_id present: {created_wo_id in dave_order_ids}"
        )

        # 5. IDOR Protection - tech_dave direct operations on Rathinam's order return 403 Forbidden
        res_idor_get = client.get(f"/api/v1/work-orders/{created_wo_id}", headers=auth_header("tech_dave", "Technician"))
        res_idor_accept = client.post(f"/api/v1/work-orders/{created_wo_id}/accept", headers=auth_header("tech_dave", "Technician"))
        res_idor_start = client.post(f"/api/v1/work-orders/{created_wo_id}/start", headers=auth_header("tech_dave", "Technician"))
        res_idor_resolve = client.post(
            f"/api/v1/work-orders/{created_wo_id}/resolve",
            json={
                "diagnosis": "Worn bearing race",
                "actions_taken": "Attempted illicit repair",
                "parts_replaced": [],
                "downtime_minutes": 10,
                "resolution_notes": "Unauthorized attempt",
            },
            headers=auth_header("tech_dave", "Technician"),
        )
        idor_passed = all(r.status_code == 403 for r in [res_idor_get, res_idor_accept, res_idor_start, res_idor_resolve])
        suite.record(
            "OP-05",
            "IDOR Defenses - Unauthorized Technician Mutation Blocked (403 Forbidden on GET, accept, start, resolve)",
            passed=idor_passed,
            evidence=f"GET: {res_idor_get.status_code}, accept: {res_idor_accept.status_code}, start: {res_idor_start.status_code}, resolve: {res_idor_resolve.status_code}"
        )

        # 6. Acceptance Workflow - Rathinam accepts assigned order
        res_accept = client.post(f"/api/v1/work-orders/{created_wo_id}/accept", headers=auth_header("Rathinam", "Technician"))
        accepted_data = res_accept.json() if res_accept.status_code == 200 else {}
        accept_passed = (
            res_accept.status_code == 200 and
            accepted_data.get("status") == "Accepted" and
            accepted_data.get("accepted_by") == "Rathinam" and
            accepted_data.get("accepted_at") is not None
        )
        suite.record(
            "OP-06",
            "Acceptance Workflow - Valid Acceptance (Status becomes 'Accepted', records accepted_by and accepted_at)",
            passed=accept_passed,
            evidence=f"Status: {accepted_data.get('status')}, accepted_by: {accepted_data.get('accepted_by')}, accepted_at: {accepted_data.get('accepted_at')}"
        )

        # 7. Duplicate Acceptance Prevention - Returns 400 or 409
        res_dup_accept = client.post(f"/api/v1/work-orders/{created_wo_id}/accept", headers=auth_header("Rathinam", "Technician"))
        suite.record(
            "OP-07",
            "Duplicate Acceptance Defense (Blocked when already accepted)",
            passed=(res_dup_accept.status_code in (400, 409)),
            evidence=f"Status code: {res_dup_accept.status_code}, detail: {res_dup_accept.json().get('detail')}"
        )

        # 8. Start Maintenance Work - Status transitions to 'In Progress'
        res_start = client.post(f"/api/v1/work-orders/{created_wo_id}/start", headers=auth_header("Rathinam", "Technician"))
        start_data = res_start.json() if res_start.status_code == 200 else {}
        suite.record(
            "OP-08",
            "Technician Start Work (Status transitions to 'In Progress', records started_at timestamp)",
            passed=(res_start.status_code == 200 and start_data.get("status") == "In Progress"),
            evidence=f"Status: {start_data.get('status')}, started_at: {start_data.get('started_at')}"
        )

        # 9. Reassignment Workflow - Admin reassigns from Rathinam to tech_dave
        reassign_payload = {
            "assigned_to_user_id": "tech_dave",
            "notes": "Rathinam reassigned to critical emergency line; transferring ticket to Dave."
        }
        res_reassign = client.post(f"/api/v1/work-orders/{created_wo_id}/reassign", json=reassign_payload, headers=auth_header("admin", "Admin"))
        reassign_data = res_reassign.json() if res_reassign.status_code == 200 else {}
        reassign_passed = (
            res_reassign.status_code == 200 and
            reassign_data.get("status") == "Assigned" and
            reassign_data.get("assigned_to_user_id") == "tech_dave" and
            reassign_data.get("reassigned_from_user_id") == "Rathinam" and
            reassign_data.get("accepted_by") is None and
            reassign_data.get("accepted_at") is None
        )
        suite.record(
            "OP-09",
            "Reassignment Workflow (Resets status to 'Assigned', clears accepted_by/at, sets new assignee)",
            passed=reassign_passed,
            evidence=f"New assigned: {reassign_data.get('assigned_to_user_id')}, from: {reassign_data.get('reassigned_from_user_id')}, accepted_by: {reassign_data.get('accepted_by')}, status: {reassign_data.get('status')}"
        )

        # 10. Isolation Inversion after Reassignment - tech_dave now sees it, Rathinam loses visibility
        res_dave_after = client.get("/api/v1/work-orders", headers=auth_header("tech_dave", "Technician"))
        res_rathinam_after = client.get("/api/v1/work-orders", headers=auth_header("Rathinam", "Technician"))
        dave_after_ids = [o["work_order_id"] for o in res_dave_after.json()] if res_dave_after.status_code == 200 else []
        rathinam_after_ids = [o["work_order_id"] for o in res_rathinam_after.json()] if res_rathinam_after.status_code == 200 else []
        inversion_passed = (created_wo_id in dave_after_ids) and (created_wo_id not in rathinam_after_ids)
        suite.record(
            "OP-10",
            "Post-Reassignment Visibility Inversion (tech_dave now sees order; Rathinam no longer sees it)",
            passed=inversion_passed,
            evidence=f"Present in tech_dave list: {created_wo_id in dave_after_ids}, present in Rathinam list: {created_wo_id in rathinam_after_ids}"
        )

        # 11. New Assignee Tech Dave Accepts & Resolves the Order
        res_dave_accept = client.post(f"/api/v1/work-orders/{created_wo_id}/accept", headers=auth_header("tech_dave", "Technician"))
        res_dave_start = client.post(f"/api/v1/work-orders/{created_wo_id}/start", headers=auth_header("tech_dave", "Technician"))
        resolve_payload = {
            "diagnosis": "Replaced fatigued neoprene isolation damper.",
            "actions_taken": "Torqued damper bolts to 10 Nm, validated zero resonant harmonic frequency.",
            "parts_replaced": ["Vibration Damping Neoprene Mounts"],
            "downtime_minutes": 25,
            "resolution_notes": "Equipment test pass; normal operational baseline restored."
        }
        res_dave_resolve = client.post(f"/api/v1/work-orders/{created_wo_id}/resolve", json=resolve_payload, headers=auth_header("tech_dave", "Technician"))
        resolve_data = res_dave_resolve.json() if res_dave_resolve.status_code == 200 else {}
        resolve_passed = (
            res_dave_resolve.status_code == 200 and
            resolve_data.get("status") == "Resolved" and
            resolve_data.get("downtime_minutes") == 25 and
            "Vibration Damping Neoprene Mounts" in resolve_data.get("parts_replaced", [])
        )
        suite.record(
            "OP-11",
            "Resolution Lifecycle (tech_dave accepts, starts, and resolves order with full audit details)",
            passed=resolve_passed,
            evidence=f"Status: {resolve_data.get('status')}, parts: {resolve_data.get('parts_replaced')}, downtime: {resolve_data.get('downtime_minutes')}"
        )

        # 12. WebSocket Scoping Logic
        ws_mgr = WebSocketManager()
        admin_meta = {"username": "admin", "role": "Admin", "id": "adm-01"}
        mgr_meta = {"username": "manager_alice", "role": "Manager", "assigned_sites": ["SITE-PLANT-A"]}
        tech_dave_meta = {"username": "tech_dave", "role": "Technician", "id": "6ac971f186c00d8644aa7fc6", "assigned_sites": ["SITE-PLANT-A"]}
        tech_rathinam_meta = {"username": "Rathinam", "role": "Technician", "id": "6adaaa8f72dec0a3174e80d1", "assigned_sites": ["SITE-PLANT-A"]}

        event_for_dave = {
            "type": "WORK_ORDER_ASSIGNED",
            "work_order_id": created_wo_id,
            "site_id": "SITE-PLANT-A",
            "assigned_to": "6ac971f186c00d8644aa7fc6",
            "assigned_to_user_id": "tech_dave"
        }

        ws_admin = ws_mgr.is_authorized_for_event(admin_meta, event_for_dave)
        ws_mgr_auth = ws_mgr.is_authorized_for_event(mgr_meta, event_for_dave)
        ws_dave_auth = ws_mgr.is_authorized_for_event(tech_dave_meta, event_for_dave)
        ws_rathinam_auth = ws_mgr.is_authorized_for_event(tech_rathinam_meta, event_for_dave)

        ws_passed = (ws_admin is True) and (ws_mgr_auth is True) and (ws_dave_auth is True) and (ws_rathinam_auth is False)
        suite.record(
            "OP-12",
            "Real-Time WebSocket Authorization Isolation (Admin: YES, Manager: YES, Dave: YES, Rathinam: NO)",
            passed=ws_passed,
            evidence=f"Admin={ws_admin}, Mgr={ws_mgr_auth}, Dave={ws_dave_auth}, Rathinam={ws_rathinam_auth}"
        )

        return suite.summary()

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
