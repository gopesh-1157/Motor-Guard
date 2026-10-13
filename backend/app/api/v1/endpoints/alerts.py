"""
MotorGuard — Alerts REST Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from backend.app.schemas.alert import (
    AlertOut,
    AlertState,
    AlertSeverity,
    AlertAcknowledgeRequest,
    AlertAssignRequest,
    AlertResolveRequest,
    AlertReopenRequest,
)
from backend.app.schemas.user import UserOut
from backend.app.services.alert_service import AlertService
from backend.app.core.auth import get_current_active_user, require_roles
from backend.app.db.mongodb import db_manager

router = APIRouter()


def get_alert_service() -> AlertService:
    if db_manager.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    return AlertService(db_manager.db)


@router.get("", response_model=List[AlertOut])
async def list_alerts(
    motor_id: Optional[str] = Query(None, description="Filter by motor ID"),
    state: Optional[AlertState] = Query(None, description="Filter by alert state"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserOut = Depends(get_current_active_user),
    alert_service: AlertService = Depends(get_alert_service),
):
    """List motor alerts with optional filtering."""
    return await alert_service.list_alerts(
        motor_id=motor_id,
        state=state,
        severity=severity,
        limit=limit,
    )


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert_by_id(
    alert_id: str,
    current_user: UserOut = Depends(get_current_active_user),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Retrieve details for a single alert record."""
    alert = await alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found",
        )
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledgeRequest = AlertAcknowledgeRequest(),
    current_user: UserOut = Depends(require_roles("Admin", "Manager", "Technician")),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Acknowledge an active alert (Requires Technician, Manager, or Admin role)."""
    alert = await alert_service.acknowledge_alert(
        alert_id=alert_id,
        acknowledged_by=current_user.username,
    )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Alert '{alert_id}' not found or already acknowledged/resolved",
        )
    return alert


@router.post("/{alert_id}/assign", response_model=AlertOut)
async def assign_alert(
    alert_id: str,
    payload: AlertAssignRequest,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Assign an active or critical alert to a technician (Requires Manager or Admin role)."""
    alert = await alert_service.assign_alert(
        alert_id=alert_id,
        assigned_to=payload.technician_username,
        assigned_by=current_user.username,
        priority=payload.priority,
        instructions=payload.instructions,
    )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found",
        )
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: str,
    payload: AlertResolveRequest,
    current_user: UserOut = Depends(require_roles("Admin", "Manager", "Technician")),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Resolve an alert with required resolution notes (Requires Technician, Manager, or Admin role)."""
    alert = await alert_service.resolve_alert(
        alert_id=alert_id,
        resolved_by=current_user.username,
        resolution_notes=payload.resolution_notes,
    )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Alert '{alert_id}' not found or already resolved",
        )
    return alert


@router.post("/{alert_id}/reopen", response_model=AlertOut)
async def reopen_alert(
    alert_id: str,
    payload: AlertReopenRequest = AlertReopenRequest(),
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Reopen a previously resolved alert if recurrence is observed (Requires Manager or Admin role)."""
    alert = await alert_service.reopen_alert(
        alert_id=alert_id,
        reopened_by=current_user.username,
        reason=payload.reason,
    )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Alert '{alert_id}' not found or not currently resolved",
        )
    return alert
