"""
MotorGuard — ESP32 Device Registry & Assignment Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.schemas.device import DeviceEnroll, DeviceAssign, DeviceOut, DeviceStatusOut
from backend.app.schemas.user import UserOut
from backend.app.services.device_service import DeviceService
from backend.app.core.auth import require_roles, get_current_active_user
from backend.app.db.mongodb import db_manager

router = APIRouter()


def get_device_service() -> DeviceService:
    if db_manager.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    return DeviceService(db_manager.db)


@router.get("", response_model=List[DeviceOut], summary="List enrolled devices")
async def list_devices(
    current_user: UserOut = Depends(get_current_active_user),
    device_service: DeviceService = Depends(get_device_service),
):
    """List all enrolled ESP32 microcontroller edge nodes (Requires authenticated user)."""
    return await device_service.list_devices(current_user=current_user)


@router.post("/enroll", response_model=DeviceOut, status_code=status.HTTP_201_CREATED, summary="Enroll new ESP32 device")
async def enroll_device(
    data: DeviceEnroll,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    device_service: DeviceService = Depends(get_device_service),
):
    """Enroll a physical ESP32 node into the plant registry (Requires Admin or Manager)."""
    return await device_service.enroll_device(data, username=current_user)


@router.get("/{device_id}", response_model=DeviceOut, summary="Get device details")
async def get_device(
    device_id: str,
    current_user: UserOut = Depends(get_current_active_user),
    device_service: DeviceService = Depends(get_device_service),
):
    """Retrieve single device details with RBAC scoping."""
    device = await device_service.get_device(device_id, current_user=current_user)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")
    return device


@router.post("/{device_id}/assign", response_model=DeviceOut, summary="Assign device to motor")
async def assign_device(
    device_id: str,
    data: DeviceAssign,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    device_service: DeviceService = Depends(get_device_service),
):
    """Assign an enrolled ESP32 edge device to an industrial motor (1-to-1 association)."""
    return await device_service.assign_device(device_id, data.motor_id, username=current_user)


@router.post("/{device_id}/unassign", response_model=DeviceOut, summary="Unassign device")
async def unassign_device(
    device_id: str,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    device_service: DeviceService = Depends(get_device_service),
):
    """Unassign an ESP32 edge device from its current motor."""
    return await device_service.unassign_device(device_id, username=current_user)


@router.get("/{device_id}/status", response_model=DeviceStatusOut, summary="Get device connection status")
async def get_device_status(
    device_id: str,
    current_user: UserOut = Depends(get_current_active_user),
    device_service: DeviceService = Depends(get_device_service),
):
    """Query live availability, heartbeat freshness, and last recorded telemetry (Requires authenticated user)."""
    return await device_service.get_device_status(device_id, current_user=current_user)

