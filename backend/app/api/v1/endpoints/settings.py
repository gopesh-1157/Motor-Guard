"""
MotorGuard — Operational Safety Limits & Threshold Settings Endpoints

Provides authenticated retrieval and persistence of edge gateway safety thresholds.
Modifications require Admin or Manager RBAC authorization and record audit metadata.
"""

from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.schemas.settings import OperationalLimitsOut, OperationalLimitsUpdate
from backend.app.schemas.user import UserOut
from backend.app.core.auth import get_current_active_user, require_roles
from backend.app.db.mongodb import db_manager

logger = logging.getLogger("motorguard.api.settings")
router = APIRouter()

SETTINGS_COLLECTION = "system_settings"
SETTINGS_DOC_ID = "gateway_operational_limits"


@router.get(
    "/thresholds",
    response_model=OperationalLimitsOut,
    summary="Retrieve Operational Safety Limits",
)
async def get_operational_thresholds(
    current_user: UserOut = Depends(get_current_active_user),
) -> OperationalLimitsOut:
    """Retrieve persisted operational safety limits and timeout parameters."""
    if db_manager.db is None:
        # Fallback to default thresholds when database is not connected (e.g. testing)
        return OperationalLimitsOut()

    doc = await db_manager.db[SETTINGS_COLLECTION].find_one({"_id": SETTINGS_DOC_ID})
    if not doc:
        return OperationalLimitsOut()

    doc.pop("_id", None)
    return OperationalLimitsOut(**doc)


@router.post(
    "/thresholds",
    response_model=OperationalLimitsOut,
    summary="Update Operational Safety Limits",
)
async def update_operational_thresholds(
    limits: OperationalLimitsUpdate,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
) -> OperationalLimitsOut:
    """
    Persist modified operational thresholds in MongoDB.
    Restricted strictly to Admin and Manager roles.
    Records updated_by and updated_at audit metadata.
    """
    if db_manager.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    data = limits.model_dump()
    data["updated_by"] = current_user.username
    data["updated_at"] = datetime.now(timezone.utc)

    await db_manager.db[SETTINGS_COLLECTION].update_one(
        {"_id": SETTINGS_DOC_ID},
        {"$set": data},
        upsert=True,
    )

    logger.info(
        "Operational safety thresholds updated by '%s' (%s): Temp=(%s, %s)°C, Curr=(%s, %s)A, Vib=(%s, %s)g",
        current_user.username,
        current_user.role,
        limits.temperature_warning_c,
        limits.temperature_critical_c,
        limits.current_warning_a,
        limits.current_critical_a,
        limits.vibration_warning_g,
        limits.vibration_critical_g,
    )

    return OperationalLimitsOut(**data)
