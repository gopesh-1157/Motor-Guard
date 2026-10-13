import re
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class SensorsPayload(BaseModel):
    temperature_c: Optional[float] = Field(
        default=None,
        ge=-20.0,
        le=120.0,
        description="Chassis temperature in Celsius",
    )
    current_a: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=30.0,
        description="Total DC armature current in Amperes",
    )
    vibration_g_rms: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=16.0,
        description="Dynamic acceleration RMS across 3 axes in standard Earth gravity (g)",
    )


class SensorStatusPayload(BaseModel):
    temperature: Literal["OK", "UNAVAILABLE", "DISCONNECTED", "OUT_OF_RANGE", "STALE"]
    current: Literal["OK", "UNAVAILABLE", "DISCONNECTED", "OUT_OF_RANGE", "STALE"]
    vibration: Literal["OK", "UNAVAILABLE", "DISCONNECTED", "OUT_OF_RANGE", "STALE"]


class InferenceProbabilities(BaseModel):
    healthy: float = Field(..., ge=0.0, le=1.0)
    warning: float = Field(..., ge=0.0, le=1.0)
    critical: float = Field(..., ge=0.0, le=1.0)


class InferencePayload(BaseModel):
    status: Literal["PREDICTED", "MODEL_UNAVAILABLE", "INPUT_INVALID", "SKIPPED", "MODEL_ERROR"]
    health_status: Literal["healthy", "warning", "critical", "unknown"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    probabilities: Optional[InferenceProbabilities] = None
    model_version: Optional[str] = None
    inference_time_ms: Optional[int] = Field(default=None, ge=0)


class DiagnosticsPayload(BaseModel):
    wifi_rssi_dbm: Optional[int] = None
    free_heap_bytes: Optional[int] = None
    uptime_seconds: Optional[int] = None


class TelemetryMessage(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    event_id: str = Field(..., description="UUIDv4 idempotent identifier")
    device_id: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]{3,32}$")
    motor_id: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]{3,32}$")
    source: Literal["hardware", "simulator"]
    seq: int = Field(..., ge=0)
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp ending in Z")
    sensors: SensorsPayload
    sensor_status: SensorStatusPayload
    inference: InferencePayload
    diagnostics: Optional[DiagnosticsPayload] = None

    @field_validator("timestamp")
    @classmethod
    def validate_utc_timestamp(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("Timestamp must end with 'Z' indicating UTC")
        # Validate ISO parsing
        try:
            # Remove Z for fromisoformat
            datetime.fromisoformat(v.rstrip("Z"))
        except Exception:
            raise ValueError("Invalid ISO-8601 timestamp string")
        return v
