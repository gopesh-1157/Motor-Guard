"""
MotorGuard — Motor Management REST API Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.schemas.motor import MotorCreate, MotorUpdate, MotorOut
from backend.app.schemas.user import UserOut
from backend.app.services.motor_service import MotorService
from backend.app.core.auth import require_roles, get_current_active_user
from backend.app.db.mongodb import db_manager

router = APIRouter()


def get_motor_service() -> MotorService:
    if db_manager.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    return MotorService(db_manager.db)


@router.get("", response_model=List[MotorOut], summary="List all registered motors")
async def list_motors(
    site_id: Optional[str] = Query(None, description="Filter by plant site ID"),
    current_user: UserOut = Depends(get_current_active_user),
    motor_service: MotorService = Depends(get_motor_service),
):
    """List all registered motor assets with operational and health status (Requires authenticated user)."""
    return await motor_service.list_motors(site_id=site_id)



@router.post("", response_model=MotorOut, status_code=status.HTTP_201_CREATED, summary="Register new motor")
async def create_motor(
    data: MotorCreate,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    motor_service: MotorService = Depends(get_motor_service),
):
    """Register a new industrial motor asset into the plant registry (Requires Admin or Manager)."""
    return await motor_service.create_motor(data, username=current_user.username)


@router.get("/audit", summary="Get motor configuration audit trail")
async def get_audit_trail(
    limit: int = Query(50, ge=1, le=200),
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    motor_service: MotorService = Depends(get_motor_service),
):
    """Retrieve immutable audit log of motor creation, config edits, and device reassignments."""
    return await motor_service.get_audit_trail(limit=limit)


@router.get("/{motor_id}", response_model=MotorOut, summary="Get motor details")
async def get_motor(
    motor_id: str,
    current_user: UserOut = Depends(get_current_active_user),
    motor_service: MotorService = Depends(get_motor_service),
):
    """Retrieve full configuration and live operational status for a single motor (Requires authenticated user)."""
    motor = await motor_service.get_motor(motor_id)
    if not motor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found")
    return motor


@router.patch("/{motor_id}", response_model=MotorOut, summary="Update motor details/config")
async def update_motor(
    motor_id: str,
    data: MotorUpdate,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    motor_service: MotorService = Depends(get_motor_service),
):
    """Update motor specifications, thresholds, or device assignments (Requires Admin or Manager)."""
    return await motor_service.update_motor_config(motor_id, data, username=current_user.username)


@router.get("/{motor_id}/configuration", summary="Get motor configuration JSON")
async def get_motor_configuration(
    motor_id: str,
    current_user: UserOut = Depends(get_current_active_user),
    motor_service: MotorService = Depends(get_motor_service),
):
    """Export clean non-secret hardware sensor mappings, thresholds, and AI profile."""
    motor = await motor_service.get_motor(motor_id)
    if not motor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Motor '{motor_id}' not found")
    return {
        "motor_id": motor.motor_id,
        "configuration_version": motor.configuration_version,
        "assigned_device_id": motor.assigned_device_id,
        "electrical_specs": motor.electrical_specs.model_dump(),
        "sensors_config": motor.sensors_config.model_dump(),
        "thresholds": motor.thresholds.model_dump(),
        "edge_impulse_config": motor.edge_impulse_config.model_dump(),
    }


@router.patch("/{motor_id}/configuration", response_model=MotorOut, summary="Patch motor configuration")
async def patch_motor_configuration(
    motor_id: str,
    data: MotorUpdate,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    motor_service: MotorService = Depends(get_motor_service),
):
    """Patch specific hardware parameters or safety thresholds."""
    return await motor_service.update_motor_config(motor_id, data, username=current_user.username)


@router.post("/{motor_id}/disable", response_model=MotorOut, summary="Disable motor")
async def disable_motor(
    motor_id: str,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    motor_service: MotorService = Depends(get_motor_service),
):
    """Deactivate motor asset and prevent further operational dispatch."""
    return await motor_service.disable_motor(motor_id, username=current_user.username)
