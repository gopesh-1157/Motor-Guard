"""
MotorGuard — Alert Schemas & Models
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

AlertSeverity = Literal["INFO", "WARNING", "CRITICAL"]
AlertState = Literal["ACTIVE", "ACKNOWLEDGED", "RESOLVED"]
AlertTriggerType = Literal[
    "THRESHOLD_OVERCURRENT",
    "THRESHOLD_OVERTEMPERATURE",
    "THRESHOLD_HIGH_VIBRATION",
    "CRITICAL_INFERENCE_FAULT",
    "DEVICE_OFFLINE",
    "SENSOR_DISCONNECTED",
    "SENSOR_UNCALIBRATED",
    "HARD_OVERCURRENT_TRIP",
]


class AlertBase(BaseModel):
    motor_id: str
    device_id: str
    severity: AlertSeverity
    trigger_type: AlertTriggerType
    trigger_value: float
    threshold_limit: float
    unit: str
    message: str


class AlertCreate(AlertBase):
    alert_id: Optional[str] = None


class AlertAcknowledgeRequest(BaseModel):
    notes: Optional[str] = None


class AlertAssignRequest(BaseModel):
    technician_username: str = Field(..., min_length=2)
    priority: Literal["NORMAL", "HIGH", "URGENT", "CRITICAL"] = "URGENT"
    instructions: Optional[str] = None


class AlertResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=3)


class AlertReopenRequest(BaseModel):
    reason: str = Field("Recurrence detected or investigation incomplete", min_length=3)


class AlertCompleteRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=3)
    parts_replaced: List[str] = Field(default_factory=list)
    downtime_minutes: int = Field(default=0, ge=0)


class AlertOut(AlertBase):
    id: Optional[str] = None
    alert_id: str
    state: AlertState
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_by: Optional[str] = None
    assigned_at: Optional[datetime] = None
    priority: Optional[str] = None
    instructions: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    reopened_at: Optional[datetime] = None
    reopened_by: Optional[str] = None
    reopen_reason: Optional[str] = None
