"""
MotorGuard — Maintenance Record Pydantic Schemas
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

ServiceType = Literal["INSPECTION", "LUBRICATION", "REPLACEMENT", "CALIBRATION", "REPAIR"]


class MaintenanceRecordBase(BaseModel):
    motor_id: str
    service_type: ServiceType
    summary: str = Field(..., min_length=3, max_length=200)
    details: str = Field(..., min_length=5)
    parts_replaced: List[str] = Field(default_factory=list)
    downtime_minutes: int = Field(default=0, ge=0)


class MaintenanceRecordCreate(MaintenanceRecordBase):
    pass


class MaintenanceRecordOut(MaintenanceRecordBase):
    id: Optional[str] = None
    record_id: str
    technician_id: str
    technician_name: str
    timestamp: datetime
