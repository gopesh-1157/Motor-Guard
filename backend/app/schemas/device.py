"""
MotorGuard — ESP32 Device Registration & Assignment Schemas
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class DeviceEnroll(BaseModel):
    device_id: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]{3,32}$")
    device_type: Literal["ESP32", "ESP32-S3", "Virtual-ESP32"] = "ESP32"
    board_variant: str = Field(default="ESP32-D0WD-V3", max_length=50)
    firmware_version: str = Field(default="1.0.1-AP", max_length=50)
    site_id: str = Field(default="SITE-PLANT-A", max_length=50)
    assigned_motor_id: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{3,32}$")
    mqtt_client_id: Optional[str] = Field(default=None, max_length=64)


class DeviceAssign(BaseModel):
    motor_id: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]{3,32}$")


class DeviceOut(BaseModel):
    device_id: str
    device_type: str
    board_variant: str
    firmware_version: str
    site_id: str
    assigned_motor_id: Optional[str] = None
    enrollment_status: Literal["enrolled", "pending", "revoked"] = "enrolled"
    availability: Literal["online", "offline", "unknown"] = "unknown"
    last_seen: Optional[datetime] = None
    configuration_version: int = 1
    created_at: datetime
    updated_at: datetime


class DeviceStatusOut(BaseModel):
    device_id: str
    availability: str
    last_seen: Optional[datetime] = None
    assigned_motor_id: Optional[str] = None
    telemetry_count: int = 0
    last_telemetry: Optional[dict] = None
