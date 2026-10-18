"""
MotorGuard — Work Orders REST Endpoints

Exposes the full workflow:
Admin/Manager -> Create & Assign -> Technician Accepts -> Starts -> Resolves / Rejects
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from backend.app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderAcceptRequest,
    WorkOrderStartRequest,
    WorkOrderResolveRequest,
    WorkOrderRejectRequest,
)
from backend.app.schemas.audit import AuditLogOut
from backend.app.schemas.user import UserOut
from backend.app.services.work_order_service import WorkOrderService
from backend.app.core.auth import get_current_active_user, require_roles
from backend.app.db.mongodb import db_manager

router = APIRouter()


def get_work_order_service() -> WorkOrderService:
    if db_manager.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    return WorkOrderService(db_manager.db)


@router.post("", response_model=WorkOrderOut, status_code=status.HTTP_201_CREATED)
async def create_work_order(
    payload: WorkOrderCreate,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    service: WorkOrderService = Depends(get_work_order_service),
):
    """Create and assign a maintenance work order to an eligible technician (Requires Admin or Manager)."""
    return await service.create_work_order(payload, current_user)


@router.get("", response_model=List[WorkOrderOut])
async def list_work_orders(
    status: Optional[str] = Query(None, description="Filter by status (Assigned, Accepted, In Progress, Resolved, Rejected)"),
    motor_id: Optional[str] = Query(None, description="Filter by motor ID"),
    limit: int = Query(100, ge=1, le=200),
    current_user: UserOut = Depends(require_roles("Admin", "Manager", "Technician")),
    service: WorkOrderService = Depends(get_work_order_service),
):
    """
    List work orders.
    - Technicians are isolated: only work orders assigned to their username are returned.
    - Admins and Managers can inspect all work orders across the plant fleet.
    """
    return await service.list_work_orders(
        current_user=current_user,
        status_filter=status,
        motor_id=motor_id,
        limit=limit,
    )


@router.get("/audit/logs", response_model=List[AuditLogOut])
async def get_audit_logs(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    service: WorkOrderService = Depends(get_work_order_service),
):
    """View tamper-resistant audit logs (Requires Admin or Manager)."""
    return await service.list_audit_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )


@router.get("/{work_order_id}", response_model=WorkOrderOut)
async def get_work_order(
    work_order_id: str,
    current_user: UserOut = Depends(require_roles("Admin", "Manager", "Technician")),
    service: WorkOrderService = Depends(get_work_order_service),
):
    """Retrieve details for a specific work order."""
    return await service.get_work_order(work_order_id, current_user)


@router.post("/{work_order_id}/accept", response_model=WorkOrderOut)
async def accept_work_order(
    work_order_id: str,
    payload: WorkOrderAcceptRequest = WorkOrderAcceptRequest(),
    current_user: UserOut = Depends(require_roles("Technician", "Admin")),
    service: WorkOrderService = Depends(get_work_order_service),
):
    """Technician acknowledges & accepts assignment (Assigned -> Accepted)."""
    return await service.accept_work_order(work_order_id, current_user, notes=payload.notes)


@router.post("/{work_order_id}/start", response_model=WorkOrderOut)
async def start_work_order(
    work_order_id: str,
    payload: WorkOrderStartRequest = WorkOrderStartRequest(),
    current_user: UserOut = Depends(require_roles("Technician", "Admin")),
    service: WorkOrderService = Depends(get_work_order_service),
):
    """Technician begins maintenance intervention (Accepted -> In Progress)."""
    return await service.start_work_order(work_order_id, current_user, notes=payload.notes)


@router.post("/{work_order_id}/resolve", response_model=WorkOrderOut)
async def resolve_work_order(
    work_order_id: str,
    payload: WorkOrderResolveRequest,
    current_user: UserOut = Depends(require_roles("Technician", "Admin")),
    service: WorkOrderService = Depends(get_work_order_service),
):
    """
    Technician resolves work order: records root cause diagnosis, replaced parts,
    downtime minutes, and notes. Automatically resolves linked alert.
    """
    return await service.resolve_work_order(work_order_id, payload, current_user)


@router.post("/{work_order_id}/reject", response_model=WorkOrderOut)
async def reject_work_order(
    work_order_id: str,
    payload: WorkOrderRejectRequest,
    current_user: UserOut = Depends(require_roles("Technician", "Admin")),
    service: WorkOrderService = Depends(get_work_order_service),
):
    """Technician rejects assignment with detailed reason."""
    return await service.reject_work_order(work_order_id, payload, current_user)
