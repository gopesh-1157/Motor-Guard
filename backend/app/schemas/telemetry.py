import re
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, field_validator, model_validator


class SensorsPayload(BaseModel):
    temperature_c: Optional[float] = Field(
        default=None,
        ge=-20.0,
        le=120.0,
        description="Ambient/nearby air temperature in Celsius (DHT11, backward-compatible field)",
    )
    ambient_temperature_c: Optional[float] = Field(
        default=None,
        ge=-20.0,
        le=120.0,
        description="Ambient air temperature in Celsius (DHT11)",
    )
    case_temperature_c: Optional[float] = Field(
        default=None,
        ge=-20.0,
        le=150.0,
        description="Motor casing contact temperature in Celsius (None if no contact probe fitted)",
    )
    current_a: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=30.0,
        description="Armature current in Amperes from ACS712",
    )
    current_peak_a: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=50.0,
        description="Short-term peak current across sampling window in Amperes",
    )
    vibration_g_rms: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=16.0,
        description="Dynamic acceleration RMS across 3 axes in standard Earth gravity (g) with mean removed",
    )
    vibration_g_peak: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=32.0,
        description="Peak instantaneous dynamic acceleration vector in standard Earth gravity (g)",
    )

    @model_validator(mode="after")
    def sync_ambient_temperature(self) -> "SensorsPayload":
        """Maintain bidirectional compatibility between temperature_c and ambient_temperature_c."""
        if self.ambient_temperature_c is None and self.temperature_c is not None:
            self.ambient_temperature_c = self.temperature_c
        elif self.temperature_c is None and self.ambient_temperature_c is not None:
            self.temperature_c = self.ambient_temperature_c
        return self


class SensorStatusPayload(BaseModel):
    temperature: Literal["OK", "UNAVAILABLE", "DISCONNECTED", "OUT_OF_RANGE", "STALE"]
    current: Literal["OK", "UNAVAILABLE", "DISCONNECTED", "OUT_OF_RANGE", "STALE", "UNCALIBRATED"]
    vibration: Literal["OK", "UNAVAILABLE", "DISCONNECTED", "OUT_OF_RANGE", "STALE"]
    current_calibrated: Optional[bool] = Field(
        default=None,
        description="Whether ACS712 zero-point offset passed valid boot calibration",
    )
    current_zero_offset_v: Optional[float] = Field(
        default=None,
        description="Calibrated zero-current sensor output voltage",
    )


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
    input_feature_version: Optional[str] = "1.0.0-3f"
    inference_time_ms: Optional[int] = Field(default=None, ge=0)


class SafetyPayload(BaseModel):
    status: Literal["SAFE", "WARNING", "CRITICAL", "UNKNOWN"] = Field(
        default="SAFE",
        description="Independent deterministic safety trip status (never suppressed by ML)",
    )
    current_state: Literal["NORMAL", "WARNING", "CRITICAL", "UNKNOWN"] = "NORMAL"
    vibration_state: Literal["NORMAL", "WARNING", "CRITICAL", "UNKNOWN"] = "NORMAL"
    temperature_state: Literal["NORMAL", "WARNING", "CRITICAL", "UNKNOWN"] = "NORMAL"
    active_reasons: List[str] = Field(
        default_factory=list,
        description="Explicit rule-based alert violation descriptions",
    )
    configuration_version: int = Field(default=1, ge=1)
    calibration_status: Literal[
        "manufacturer_verified", "measured_and_calibrated", "provisional", "unconfigured"
    ] = Field(
        default="provisional",
        description="Rigorous threshold provenance: manufacturer_verified, measured_and_calibrated, provisional, unconfigured",
    )


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
    safety: Optional[SafetyPayload] = None
    diagnostics: Optional[DiagnosticsPayload] = None

    @field_validator("timestamp")
    @classmethod
    def validate_utc_timestamp(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("Timestamp must end with 'Z' indicating UTC")
        try:
            datetime.fromisoformat(v.rstrip("Z"))
        except Exception:
            raise ValueError("Invalid ISO-8601 timestamp string")
        return v
