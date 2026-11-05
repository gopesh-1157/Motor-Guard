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
    WorkOrderReassignRequest,
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
        await self.collection.create_index([("assigned_to", 1), ("status", 1)])
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
        from bson import ObjectId
        target_tech = data.assigned_to_user_id.strip()
        assigned_user = await self.users_col.find_one({"username": target_tech})
        if not assigned_user:
            try:
                assigned_user = await self.users_col.find_one({"_id": ObjectId(target_tech)})
            except Exception:
                pass
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

        tech_username = assigned_user.get("username", target_tech)
        tech_db_id = str(assigned_user.get("_id", assigned_user.get("id", tech_username)))

        wo_doc = {
            "work_order_id": wo_id,
            "motor_id": data.motor_id,
            "site_id": motor_site,
            "alert_id": data.alert_id,
            "assigned_to": tech_db_id,
            "assigned_to_user_id": tech_username,
            "assigned_by_user_id": current_user.username,
            "priority": data.priority,
            "title": data.title,
            "description": data.description,
            "status": "Assigned",
            "created_at": now,
            "assigned_at": now,
            "accepted_at": None,
            "accepted_by": None,
            "started_at": None,
            "resolved_at": None,
            "rejected_at": None,
            "reassigned_from_user_id": None,
            "reassigned_at": None,
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
                        "assigned_to": tech_username,
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
                "assigned_to": tech_username,
                "assigned_to_id": tech_db_id,
                "priority": data.priority,
            },
        )

        try:
            from backend.app.api.v1.endpoints.websocket import ws_manager
            await ws_manager.broadcast({
                "type": "WORK_ORDER_CREATED",
                "work_order_id": wo_id,
                "motor_id": data.motor_id,
                "site_id": motor_site,
                "alert_id": data.alert_id,
                "assigned_to": tech_db_id,
                "assigned_to_user_id": tech_username,
                "priority": data.priority,
                "status": "Assigned",
                "created_at": now.isoformat(),
            })
        except Exception:
            pass

        wo_doc.pop("_id", None)
        return WorkOrderOut(**wo_doc)

    async def list_work_orders(
        self,
        current_user: UserOut,
        status_filter: Optional[str] = None,
        motor_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 100,
    ) -> List[WorkOrderOut]:
        """List work orders with role-based and site isolation."""
        query: Dict[str, Any] = {}

        # STRICT ISOLATION: Technicians can ONLY view work orders assigned to their authenticated identity
        if current_user.role == "Technician":
            tech_id = current_user.id
            tech_username = current_user.username
            clauses = [{"assigned_to_user_id": tech_username}]
            if tech_id:
                clauses.append({"assigned_to": tech_id})
                clauses.append({"assigned_to_user_id": tech_id})
                clauses.append({"assigned_to": tech_username})
            query["$or"] = clauses
        elif current_user.role == "Manager":
            from backend.app.config import settings
            if not current_user.assigned_sites:
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    return []
            else:
                query["site_id"] = {"$in": current_user.assigned_sites}
            if assigned_to:
                target_str = assigned_to.strip()
                query["$or"] = [
                    {"assigned_to_user_id": target_str},
                    {"assigned_to": target_str},
                ]
        elif current_user.role == "Admin":
            if assigned_to:
                target_str = assigned_to.strip()
                query["$or"] = [
                    {"assigned_to_user_id": target_str},
                    {"assigned_to": target_str},
                ]

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
        if current_user.role == "Technician":
            is_assigned = (
                doc.get("assigned_to") == current_user.id
                or doc.get("assigned_to_user_id") == current_user.username
                or (current_user.id and doc.get("assigned_to_user_id") == current_user.id)
                or doc.get("assigned_to") == current_user.username
            )
            if not is_assigned:
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
        """Acknowledge & accept assignment (Assigned -> Accepted). Admin, Manager, or assigned Technician."""
        doc = await self.get_work_order(work_order_id, current_user)

        # Role-based authorization check
        if current_user.role == "Technician":
            is_assigned = (
                doc.assigned_to == current_user.id
                or doc.assigned_to_user_id == current_user.username
                or (current_user.id and doc.assigned_to_user_id == current_user.id)
                or doc.assigned_to == current_user.username
            )
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Only the assigned technician can accept this work order",
                )
        elif current_user.role == "Manager":
            if not current_user.assigned_sites:
                from backend.app.config import settings
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Unscoped Manager cannot accept work orders",
                    )
            elif doc.site_id and doc.site_id not in current_user.assigned_sites:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Work order site '{doc.site_id}' is outside your authorized site scope",
                )
        elif current_user.role == "Admin":
            pass
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to accept work orders",
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
                    "accepted_by": current_user.username,
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
            details={"accepted_by": current_user.username, "notes": notes},
        )
        try:
            from backend.app.api.v1.endpoints.websocket import ws_manager
            await ws_manager.broadcast({
                "type": "WORK_ORDER_ACCEPTED",
                "work_order_id": work_order_id,
                "motor_id": doc.motor_id,
                "site_id": doc.site_id,
                "assigned_to": doc.assigned_to or (updated.get("assigned_to") if updated else None),
                "assigned_to_user_id": doc.assigned_to_user_id,
                "accepted_by": current_user.username,
                "status": "Accepted",
                "accepted_at": now.isoformat(),
            })
        except Exception:
            pass
        updated.pop("_id", None)
        return WorkOrderOut(**updated)

    async def start_work_order(
        self, work_order_id: str, current_user: UserOut, notes: Optional[str] = None
    ) -> WorkOrderOut:
        """Begin maintenance intervention (Accepted / Assigned -> In Progress)."""
        doc = await self.get_work_order(work_order_id, current_user)
        if current_user.role == "Technician":
            is_assigned = (
                doc.assigned_to == current_user.id
                or doc.assigned_to_user_id == current_user.username
                or (current_user.id and doc.assigned_to_user_id == current_user.id)
                or doc.assigned_to == current_user.username
            )
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Only the assigned technician can start this work order",
                )
        elif current_user.role == "Manager":
            if not current_user.assigned_sites:
                from backend.app.config import settings
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Unscoped Manager cannot start work orders",
                    )
            elif doc.site_id and doc.site_id not in current_user.assigned_sites:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Work order site '{doc.site_id}' is outside your authorized site scope",
                )
        elif current_user.role == "Admin":
            pass
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to start work orders",
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
        try:
            from backend.app.api.v1.endpoints.websocket import ws_manager
            await ws_manager.broadcast({
                "type": "WORK_ORDER_STARTED",
                "work_order_id": work_order_id,
                "motor_id": doc.motor_id,
                "site_id": doc.site_id,
                "assigned_to": doc.assigned_to or (updated.get("assigned_to") if updated else None),
                "assigned_to_user_id": doc.assigned_to_user_id,
                "status": "In Progress",
                "started_at": now.isoformat(),
            })
        except Exception:
            pass
        updated.pop("_id", None)
        return WorkOrderOut(**updated)

    async def resolve_work_order(
        self, work_order_id: str, data: WorkOrderResolveRequest, current_user: UserOut
    ) -> WorkOrderOut:
        """Resolve work order with root cause diagnosis, actions taken, parts, and downtime."""
        doc = await self.get_work_order(work_order_id, current_user)
        if current_user.role == "Technician":
            is_assigned = (
                doc.assigned_to == current_user.id
                or doc.assigned_to_user_id == current_user.username
                or (current_user.id and doc.assigned_to_user_id == current_user.id)
                or doc.assigned_to == current_user.username
            )
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Only the assigned technician can resolve this work order",
                )
        elif current_user.role == "Manager":
            if not current_user.assigned_sites:
                from backend.app.config import settings
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Unscoped Manager cannot resolve work orders",
                    )
            elif doc.site_id and doc.site_id not in current_user.assigned_sites:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Work order site '{doc.site_id}' is outside your authorized site scope",
                )
        elif current_user.role == "Admin":
            pass
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to resolve work orders",
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

        try:
            from backend.app.api.v1.endpoints.websocket import ws_manager
            await ws_manager.broadcast({
                "type": "WORK_ORDER_RESOLVED",
                "work_order_id": work_order_id,
                "motor_id": doc.motor_id,
                "site_id": doc.site_id,
                "assigned_to": doc.assigned_to or (updated.get("assigned_to") if updated else None),
                "assigned_to_user_id": doc.assigned_to_user_id,
                "status": "Resolved",
                "resolved_at": now.isoformat(),
            })
        except Exception:
            pass

        updated.pop("_id", None)
        return WorkOrderOut(**updated)

    async def reject_work_order(
        self, work_order_id: str, data: WorkOrderRejectRequest, current_user: UserOut
    ) -> WorkOrderOut:
        """Reject work order assignment with detailed reason."""
        doc = await self.get_work_order(work_order_id, current_user)
        if current_user.role == "Technician":
            is_assigned = (
                doc.assigned_to == current_user.id
                or doc.assigned_to_user_id == current_user.username
                or (current_user.id and doc.assigned_to_user_id == current_user.id)
                or doc.assigned_to == current_user.username
            )
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Only the assigned technician can reject this work order",
                )
        elif current_user.role == "Manager":
            if not current_user.assigned_sites:
                from backend.app.config import settings
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Unscoped Manager cannot reject work orders",
                    )
            elif doc.site_id and doc.site_id not in current_user.assigned_sites:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Work order site '{doc.site_id}' is outside your authorized site scope",
                )
        elif current_user.role == "Admin":
            pass
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to reject work orders",
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
        try:
            from backend.app.api.v1.endpoints.websocket import ws_manager
            await ws_manager.broadcast({
                "type": "WORK_ORDER_REJECTED",
                "work_order_id": work_order_id,
                "motor_id": doc.motor_id,
                "site_id": doc.site_id,
                "assigned_to": doc.assigned_to or (updated.get("assigned_to") if updated else None),
                "assigned_to_user_id": doc.assigned_to_user_id,
                "status": "Rejected",
                "rejected_at": now.isoformat(),
            })
        except Exception:
            pass
        updated.pop("_id", None)
        return WorkOrderOut(**updated)

    async def reassign_work_order(
        self, work_order_id: str, data: WorkOrderReassignRequest, current_user: UserOut
    ) -> WorkOrderOut:
        """Reassign work order to another eligible technician (Admin or authorized Manager)."""
        if current_user.role not in ["Admin", "Manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only Administrators and Managers can reassign work orders",
            )

        doc = await self.get_work_order(work_order_id, current_user)
        if current_user.role == "Manager":
            from backend.app.config import settings
            if not current_user.assigned_sites:
                if settings.ENVIRONMENT.lower() == "production" or not getattr(settings, "ALLOW_UNSCOPED_MANAGERS", False):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Unscoped Manager cannot reassign work orders",
                    )
            elif doc.site_id and doc.site_id not in current_user.assigned_sites:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Work order site '{doc.site_id}' is outside your authorized site scope",
                )

        if doc.status == "Resolved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reassign an already resolved work order",
            )

        from bson import ObjectId
        target = data.assigned_to_user_id.strip()
        new_tech = await self.users_col.find_one({"username": target})
        if not new_tech:
            try:
                new_tech = await self.users_col.find_one({"_id": ObjectId(target)})
            except Exception:
                pass

        if not new_tech:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Technician user '{target}' not found",
            )
        if not new_tech.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot assign work order to deactivated technician '{target}'",
            )
        if new_tech.get("role") != "Technician":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{target}' has role '{new_tech.get('role')}', only 'Technician' accounts can receive work orders",
            )

        # Site scoping check for new technician if Manager
        if current_user.role == "Manager" and current_user.assigned_sites:
            tech_sites = new_tech.get("assigned_sites") or []
            if tech_sites and doc.site_id and doc.site_id not in tech_sites:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Technician '{target}' is not assigned to site '{doc.site_id}'",
                )

        now = datetime.now(timezone.utc)
        new_tech_username = new_tech.get("username", target)
        new_tech_id = str(new_tech.get("_id", new_tech.get("id", new_tech_username)))
        old_tech_user = doc.assigned_to_user_id

        update_fields = {
            "assigned_to": new_tech_id,
            "assigned_to_user_id": new_tech_username,
            "reassigned_from_user_id": old_tech_user,
            "reassigned_at": now,
            "assigned_by_user_id": current_user.username,
            "assigned_at": now,
            "status": "Assigned",
            "accepted_at": None,
            "accepted_by": None,
            "updated_at": now,
        }
        updated = await self.collection.find_one_and_update(
            {"work_order_id": work_order_id},
            {"$set": update_fields},
            return_document=True,
        )

        if doc.alert_id:
            await self.alerts_col.update_one(
                {"alert_id": doc.alert_id},
                {
                    "$set": {
                        "assigned_to": new_tech_username,
                        "assigned_by": current_user.username,
                        "assigned_at": now,
                    }
                },
            )

        await self.log_audit(
            actor=current_user.username,
            action="REASSIGN_WORK_ORDER",
            entity_type="work_order",
            entity_id=work_order_id,
            site_id=doc.site_id,
            details={
                "previous_technician": old_tech_user,
                "new_technician": new_tech_username,
                "new_technician_id": new_tech_id,
                "reassigned_by": current_user.username,
                "notes": data.notes,
            },
        )

        try:
            from backend.app.api.v1.endpoints.websocket import ws_manager
            await ws_manager.broadcast({
                "type": "WORK_ORDER_REASSIGNED",
                "work_order_id": work_order_id,
                "motor_id": doc.motor_id,
                "site_id": doc.site_id,
                "previous_technician": old_tech_user,
                "assigned_to": new_tech_id,
                "assigned_to_user_id": new_tech_username,
                "status": "Assigned",
                "reassigned_at": now.isoformat(),
            })
        except Exception:
            pass

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
                "REASSIGN_WORK_ORDER",
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
