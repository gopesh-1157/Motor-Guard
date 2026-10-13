"""
MotorGuard — Maintenance Records REST Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from backend.app.schemas.maintenance import MaintenanceRecordCreate, MaintenanceRecordOut
from backend.app.schemas.user import UserOut
from backend.app.services.maintenance_service import MaintenanceService
from backend.app.core.auth import get_current_active_user, require_roles
from backend.app.db.mongodb import db_manager

router = APIRouter()


def get_maintenance_service() -> MaintenanceService:
    if db_manager.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    return MaintenanceService(db_manager.db)


@router.get("", response_model=List[MaintenanceRecordOut])
async def list_all_maintenance_records(
    limit: int = Query(50, ge=1, le=200),
    current_user: UserOut = Depends(get_current_active_user),
    maintenance_service: MaintenanceService = Depends(get_maintenance_service),
):
    """List maintenance records across the fleet."""
    return await maintenance_service.list_records(motor_id=None, limit=limit)


@router.get("/motors/{motor_id}", response_model=List[MaintenanceRecordOut])
async def list_motor_maintenance_records(
    motor_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: UserOut = Depends(get_current_active_user),
    maintenance_service: MaintenanceService = Depends(get_maintenance_service),
):
    """List maintenance history for a specific motor."""
    return await maintenance_service.list_records(motor_id=motor_id, limit=limit)


@router.post(
    "/motors/{motor_id}",
    response_model=MaintenanceRecordOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_motor_maintenance_record(
    motor_id: str,
    record_in: MaintenanceRecordCreate,
    current_user: UserOut = Depends(require_roles("Admin", "Technician")),
    maintenance_service: MaintenanceService = Depends(get_maintenance_service),
):
    """
    Log a maintenance intervention on a motor (Requires 'Admin' or 'Technician' role).
    Operators are strictly forbidden.
    """
    if record_in.motor_id != motor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path motor_id '{motor_id}' does not match body motor_id '{record_in.motor_id}'",
        )

    return await maintenance_service.create_record(record_in, current_user)
