"""
MotorGuard — Alert Schemas & Models
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

AlertSeverity = Literal["INFO", "WARNING", "CRITICAL"]
AlertState = Literal["ACTIVE", "ACKNOWLEDGED", "RESOLVED"]
AlertCategory = Literal["SAFETY_THRESHOLD", "ML_INFERENCE", "SENSOR_DIAGNOSTIC", "CONNECTIVITY"]
AlertTriggerType = Literal[
    "THRESHOLD_OVERCURRENT",
    "THRESHOLD_OVERTEMPERATURE",
    "THRESHOLD_HIGH_VIBRATION",
    "CRITICAL_INFERENCE_FAULT",
    "DEVICE_OFFLINE",
    "SENSOR_DISCONNECTED",
    "SENSOR_TEMPERATURE_DISCONNECTED",
    "SENSOR_CURRENT_DISCONNECTED",
    "SENSOR_VIBRATION_DISCONNECTED",
    "SENSOR_UNCALIBRATED",
    "HARD_OVERCURRENT_TRIP",
    "THRESHOLD_HIGH_VIBRATION_RMS",
    "THRESHOLD_HIGH_VIBRATION_PEAK",
    "WARNING_INFERENCE_ANOMALY",
    "INFERENCE_DIAGNOSTIC_FAILURE",
]

TRIGGER_TYPE_TO_CATEGORY: dict[str, AlertCategory] = {
    "THRESHOLD_OVERCURRENT": "SAFETY_THRESHOLD",
    "THRESHOLD_OVERTEMPERATURE": "SAFETY_THRESHOLD",
    "THRESHOLD_HIGH_VIBRATION": "SAFETY_THRESHOLD",
    "THRESHOLD_HIGH_VIBRATION_RMS": "SAFETY_THRESHOLD",
    "THRESHOLD_HIGH_VIBRATION_PEAK": "SAFETY_THRESHOLD",
    "HARD_OVERCURRENT_TRIP": "SAFETY_THRESHOLD",
    "CRITICAL_INFERENCE_FAULT": "ML_INFERENCE",
    "WARNING_INFERENCE_ANOMALY": "ML_INFERENCE",
    "SENSOR_DISCONNECTED": "SENSOR_DIAGNOSTIC",
    "SENSOR_TEMPERATURE_DISCONNECTED": "SENSOR_DIAGNOSTIC",
    "SENSOR_CURRENT_DISCONNECTED": "SENSOR_DIAGNOSTIC",
    "SENSOR_VIBRATION_DISCONNECTED": "SENSOR_DIAGNOSTIC",
    "SENSOR_UNCALIBRATED": "SENSOR_DIAGNOSTIC",
    "INFERENCE_DIAGNOSTIC_FAILURE": "SENSOR_DIAGNOSTIC",
    "DEVICE_OFFLINE": "CONNECTIVITY",
}


class AlertBase(BaseModel):
    motor_id: str
    device_id: str
    severity: AlertSeverity
    trigger_type: AlertTriggerType
    trigger_value: float
    threshold_limit: float
    unit: str
    message: str
    site_id: Optional[str] = None
    category: Optional[AlertCategory] = None
    configuration_snapshot: Optional[dict] = None
    last_observed_at: Optional[datetime] = None
    source: Optional[str] = None

    def model_post_init(self, __context) -> None:
        if self.category is None:
            self.category = TRIGGER_TYPE_TO_CATEGORY.get(self.trigger_type, "SAFETY_THRESHOLD")


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
