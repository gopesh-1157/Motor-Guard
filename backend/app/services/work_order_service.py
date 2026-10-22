"""
MotorGuard — Work Order & Maintenance Lifecycle Service

Handles MongoDB persistence, state transitions, technician authorization checks,
linked alert updates, maintenance records, and tamper-resistant audit logging.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo.asynchronous.database import AsyncDatabase
from fastapi import HTTPException, status
from backend.app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderResolveRequest,
    WorkOrderRejectRequest,
)
from backend.app.schemas.audit import AuditLogOut
from backend.app.schemas.user import UserOut

logger = logging.getLogger("motorguard.work_orders")


class WorkOrderService:
    def __init__(self, db: AsyncDatabase):
        self.db = db
        self.collection = db["work_orders"]
        self.alerts_col = db["alerts"]
        self.maintenance_col = db["maintenance_records"]
        self.audit_col = db["audit_logs"]
        self.users_col = db["users"]
        self.motors_col = db["motors"]

    async def ensure_indexes(self):
        """Create high-performance indexes for work orders and audit logs."""
        await self.collection.create_index([("work_order_id", 1)], unique=True)
        await self.collection.create_index([("assigned_to_user_id", 1), ("status", 1)])
        await self.collection.create_index([("motor_id", 1)])
        await self.collection.create_index([("site_id", 1)])
        await self.collection.create_index([("alert_id", 1)])
        await self.collection.create_index([("created_at", -1)])

        await self.audit_col.create_index([("audit_id", 1)], unique=True)
        await self.audit_col.create_index([("entity_type", 1), ("entity_id", 1)])
        await self.audit_col.create_index([("timestamp", -1)])

    async def log_audit(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: Optional[Dict[str, Any]] = None,
        site_id: Optional[str] = None,
    ):
        """Append an immutable audit entry."""
        now = datetime.now(timezone.utc)
        audit_doc = {
            "audit_id": f"AUD-{uuid.uuid4().hex[:10].upper()}",
            "actor_username": actor,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "site_id": site_id,
            "details": details or {},
            "timestamp": now,
        }
        await self.audit_col.insert_one(audit_doc)

    async def create_work_order(
        self, data: WorkOrderCreate, current_user: UserOut
    ) -> WorkOrderOut:
        """Admin or Manager creates and assigns a work order to an eligible technician."""
        # 1. Validate motor exists
        motor = await self.motors_col.find_one({"motor_id": data.motor_id})
        if not motor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Motor '{data.motor_id}' not found",
            )
        motor_site = motor.get("site_id")

        # 2. Enforce Manager site scoping
        if current_user.role == "Manager":
            from backend.app.config import settings
            if not current_user.assigned_sites:
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Unscoped Manager cannot create work orders. Explicit site assignment required.",
                    )
            elif motor_site and motor_site not in current_user.assigned_sites:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Manager is not authorized to create work orders for motor at site '{motor_site}'. Authorized sites: {current_user.assigned_sites}",
                )

        # 3. Validate that assigned technician exists, is active, and has Technician role
        assigned_user = await self.users_col.find_one({"username": data.assigned_to_user_id})
        if not assigned_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Technician user '{data.assigned_to_user_id}' not found",
            )
        if not assigned_user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot assign work order to deactivated technician '{data.assigned_to_user_id}'",
            )
        if assigned_user.get("role") != "Technician":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{data.assigned_to_user_id}' has role '{assigned_user.get('role')}', only 'Technician' accounts can receive work orders",
            )

        # 4. Check technician site alignment if specified
        if current_user.role == "Manager" and current_user.assigned_sites:
            tech_sites = assigned_user.get("assigned_sites") or []
            if tech_sites and motor_site and motor_site not in tech_sites:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Technician '{data.assigned_to_user_id}' is not assigned to site '{motor_site}'",
                )

        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")
        unique_suffix = uuid.uuid4().hex[:6].upper()
        wo_id = f"WO-{date_str}-{unique_suffix}"

        wo_doc = {
            "work_order_id": wo_id,
            "motor_id": data.motor_id,
            "site_id": motor_site,
            "alert_id": data.alert_id,
            "assigned_to_user_id": data.assigned_to_user_id,
            "assigned_by_user_id": current_user.username,
            "priority": data.priority,
            "title": data.title,
            "description": data.description,
            "status": "Assigned",
            "created_at": now,
            "assigned_at": now,
            "accepted_at": None,
            "started_at": None,
            "resolved_at": None,
            "rejected_at": None,
            "diagnosis": None,
            "actions_taken": None,
            "parts_replaced": [],
            "downtime_minutes": 0,
            "resolution_notes": None,
            "rejection_reason": None,
            "updated_at": now,
        }

        await self.collection.insert_one(wo_doc)

        # If linked to an alert, acknowledge and update alert assignment
        if data.alert_id:
            await self.alerts_col.update_one(
                {"alert_id": data.alert_id},
                {
                    "$set": {
                        "state": "ACKNOWLEDGED",
                        "assigned_to": data.assigned_to_user_id,
                        "assigned_by": current_user.username,
                        "assigned_at": now,
                        "priority": data.priority,
                        "instructions": data.description,
                        "acknowledged_at": now,
                        "acknowledged_by": current_user.username,
                    }
                },
            )

        await self.log_audit(
            actor=current_user.username,
            action="CREATE_WORK_ORDER",
            entity_type="work_order",
            entity_id=wo_id,
            site_id=motor_site,
            details={
                "motor_id": data.motor_id,
                "site_id": motor_site,
                "alert_id": data.alert_id,
                "assigned_to": data.assigned_to_user_id,
                "priority": data.priority,
            },
        )

        wo_doc.pop("_id", None)
        return WorkOrderOut(**wo_doc)

    async def list_work_orders(
        self,
        current_user: UserOut,
        status_filter: Optional[str] = None,
        motor_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[WorkOrderOut]:
        """List work orders with role-based and site isolation."""
        query: Dict[str, Any] = {}

        # STRICT ISOLATION: Technicians can ONLY view their own assigned work orders
        if current_user.role == "Technician":
            query["assigned_to_user_id"] = current_user.username
        elif current_user.role == "Manager":
            from backend.app.config import settings
            if not current_user.assigned_sites:
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    return []
            else:
                query["site_id"] = {"$in": current_user.assigned_sites}

        if status_filter:
            query["status"] = status_filter
        if motor_id:
            query["motor_id"] = motor_id

        cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
        results: List[WorkOrderOut] = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(WorkOrderOut(**doc))
        return results

    async def get_work_order(
        self, work_order_id: str, current_user: UserOut
    ) -> WorkOrderOut:
        """Fetch a specific work order with RBAC authorization check."""
        doc = await self.collection.find_one({"work_order_id": work_order_id})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work order '{work_order_id}' not found",
            )

        # STRICT ISOLATION: A technician cannot access another technician's work orders
        if (
            current_user.role == "Technician"
            and doc.get("assigned_to_user_id") != current_user.username
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view work orders assigned to your account",
            )

        # STRICT ISOLATION: Manager cannot access work orders outside authorized site scope
        if current_user.role == "Manager":
            from backend.app.config import settings
            if not current_user.assigned_sites:
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Unscoped Manager cannot access work orders",
                    )
            elif doc.get("site_id") and doc.get("site_id") not in current_user.assigned_sites:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Work order is outside your authorized site scope",
                )

        doc.pop("_id", None)
        return WorkOrderOut(**doc)

    async def accept_work_order(
        self, work_order_id: str, current_user: UserOut, notes: Optional[str] = None
    ) -> WorkOrderOut:
        """Technician accepts an assigned work order (Assigned -> Accepted)."""
        doc = await self.get_work_order(work_order_id, current_user)
        if current_user.role == "Technician" and doc.assigned_to_user_id != current_user.username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only the assigned technician can accept this work order",
            )
        if current_user.role == "Manager":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers cannot accept technician work orders",
            )
        if doc.status != "Assigned":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot accept work order in '{doc.status}' state (must be 'Assigned')",
            )

        now = datetime.now(timezone.utc)
        updated = await self.collection.find_one_and_update(
            {"work_order_id": work_order_id},
            {
                "$set": {
                    "status": "Accepted",
                    "accepted_at": now,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        await self.log_audit(
            actor=current_user.username,
            action="ACCEPT_WORK_ORDER",
            entity_type="work_order",
            entity_id=work_order_id,
            site_id=doc.site_id,
            details={"notes": notes},
        )
        updated.pop("_id", None)
        return WorkOrderOut(**updated)

    async def start_work_order(
        self, work_order_id: str, current_user: UserOut, notes: Optional[str] = None
    ) -> WorkOrderOut:
        """Technician starts work (Accepted / Assigned -> In Progress)."""
        doc = await self.get_work_order(work_order_id, current_user)
        if current_user.role == "Technician" and doc.assigned_to_user_id != current_user.username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only the assigned technician can start this work order",
            )
        if current_user.role == "Manager":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers cannot start technician work orders",
            )
        if doc.status not in ["Assigned", "Accepted"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot start work order in '{doc.status}' state (must be 'Assigned' or 'Accepted')",
            )

        now = datetime.now(timezone.utc)
        updated = await self.collection.find_one_and_update(
            {"work_order_id": work_order_id},
            {
                "$set": {
                    "status": "In Progress",
                    "started_at": now,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        await self.log_audit(
            actor=current_user.username,
            action="START_WORK_ORDER",
            entity_type="work_order",
            entity_id=work_order_id,
            site_id=doc.site_id,
            details={"notes": notes},
        )
        updated.pop("_id", None)
        return WorkOrderOut(**updated)

    async def resolve_work_order(
        self, work_order_id: str, data: WorkOrderResolveRequest, current_user: UserOut
    ) -> WorkOrderOut:
        """Technician marks work resolved with required diagnosis, actions taken, parts replaced, and notes."""
        doc = await self.get_work_order(work_order_id, current_user)
        if current_user.role == "Technician" and doc.assigned_to_user_id != current_user.username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only the assigned technician can resolve this work order",
            )
        if current_user.role == "Manager":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers cannot resolve technician work orders",
            )
        if doc.status not in ["In Progress", "Accepted"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resolve work order in '{doc.status}' state (must be 'In Progress')",
            )

        # Backend validation of required maintenance fields
        if not data.diagnosis or not data.diagnosis.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Root cause diagnosis is required to resolve work order",
            )
        if not data.actions_taken or not data.actions_taken.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Corrective actions summary is required to resolve work order",
            )
        if not data.resolution_notes or not data.resolution_notes.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resolution notes are required to resolve work order",
            )
        if data.downtime_minutes is None or data.downtime_minutes < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Downtime minutes cannot be negative",
            )

        now = datetime.now(timezone.utc)
        updated = await self.collection.find_one_and_update(
            {"work_order_id": work_order_id},
            {
                "$set": {
                    "status": "Resolved",
                    "resolved_at": now,
                    "diagnosis": data.diagnosis.strip(),
                    "actions_taken": data.actions_taken.strip(),
                    "parts_replaced": data.parts_replaced,
                    "downtime_minutes": data.downtime_minutes,
                    "resolution_notes": data.resolution_notes.strip(),
                    "updated_at": now,
                }
            },
            return_document=True,
        )

        # 1. Resolve linked alert if present
        if doc.alert_id:
            await self.alerts_col.update_one(
                {"alert_id": doc.alert_id},
                {
                    "$set": {
                        "state": "RESOLVED",
                        "resolved_at": now,
                        "resolved_by": current_user.username,
                        "resolution_notes": data.resolution_notes.strip(),
                    }
                },
            )

        # 2. Append to permanent maintenance records collection
        maint_doc = {
            "record_id": f"REC-{uuid.uuid4().hex[:8].upper()}",
            "motor_id": doc.motor_id,
            "site_id": doc.site_id,
            "work_order_id": work_order_id,
            "service_type": "REPAIR",
            "summary": data.actions_taken.strip()[:200],
            "details": f"Diagnosis: {data.diagnosis.strip()}\nActions: {data.actions_taken.strip()}\nNotes: {data.resolution_notes.strip()}",
            "parts_replaced": data.parts_replaced,
            "downtime_minutes": data.downtime_minutes,
            "technician_id": current_user.id or current_user.username,
            "technician_name": current_user.username,
            "timestamp": now,
        }
        await self.maintenance_col.insert_one(maint_doc)

        # 3. Append to audit trail
        await self.log_audit(
            actor=current_user.username,
            action="RESOLVE_WORK_ORDER",
            entity_type="work_order",
            entity_id=work_order_id,
            site_id=doc.site_id,
            details={
                "diagnosis": data.diagnosis.strip(),
                "parts_replaced": data.parts_replaced,
                "downtime_minutes": data.downtime_minutes,
            },
        )

        updated.pop("_id", None)
        return WorkOrderOut(**updated)

    async def reject_work_order(
        self, work_order_id: str, data: WorkOrderRejectRequest, current_user: UserOut
    ) -> WorkOrderOut:
        """Technician rejects an assignment with reason."""
        doc = await self.get_work_order(work_order_id, current_user)
        if current_user.role == "Technician" and doc.assigned_to_user_id != current_user.username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only the assigned technician can reject this work order",
            )
        if current_user.role == "Manager":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers cannot reject technician work orders",
            )
        if doc.status != "Assigned":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject work order in '{doc.status}' state (must be 'Assigned')",
            )
        if not data.rejection_reason or not data.rejection_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required",
            )

        now = datetime.now(timezone.utc)
        updated = await self.collection.find_one_and_update(
            {"work_order_id": work_order_id},
            {
                "$set": {
                    "status": "Rejected",
                    "rejected_at": now,
                    "rejection_reason": data.rejection_reason.strip(),
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        await self.log_audit(
            actor=current_user.username,
            action="REJECT_WORK_ORDER",
            entity_type="work_order",
            entity_id=work_order_id,
            site_id=doc.site_id,
            details={"rejection_reason": data.rejection_reason.strip()},
        )
        updated.pop("_id", None)
        return WorkOrderOut(**updated)

    async def list_audit_logs(
        self,
        current_user: UserOut,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditLogOut]:
        """Fetch immutable audit logs with role-based restrictions."""
        if current_user.role == "Technician":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Technicians are not authorized to view audit logs",
            )

        query: Dict[str, Any] = {}

        # Limit Managers to authorized operational events and their site scope
        if current_user.role == "Manager":
            from backend.app.config import settings
            if not current_user.assigned_sites:
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    return []

            OPERATIONAL_ACTIONS = [
                "CREATE_MOTOR",
                "UPDATE_CONFIG",
                "DISABLE_MOTOR",
                "ENROLL_DEVICE",
                "ASSIGN_DEVICE",
                "UNASSIGN_DEVICE",
                "CREATE_WORK_ORDER",
                "ACCEPT_WORK_ORDER",
                "START_WORK_ORDER",
                "RESOLVE_WORK_ORDER",
                "REJECT_WORK_ORDER",
            ]
            query["action"] = {"$in": OPERATIONAL_ACTIONS}

            if current_user.assigned_sites:
                query["$or"] = [
                    {"details.site": {"$in": current_user.assigned_sites}},
                    {"details.site_id": {"$in": current_user.assigned_sites}},
                    {"site_id": {"$in": current_user.assigned_sites}},
                ]

        if entity_type:
            query["entity_type"] = entity_type
        if entity_id:
            query["entity_id"] = entity_id

        cursor = self.audit_col.find(query).sort("timestamp", -1).limit(limit)
        results: List[AuditLogOut] = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(AuditLogOut(**doc))
        return results
