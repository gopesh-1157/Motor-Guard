"""
MotorGuard — Operational Thresholds & Gateway Settings Schemas

Defines validation and serialization for industrial motor safety limits,
sensor threshold margins, and gateway connectivity parameters.
"""

from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class OperationalLimitsBase(BaseModel):
    temperature_warning_c: float = Field(
        default=50.0,
        ge=15.0,
        le=95.0,
        description="Temperature warning alert threshold in Celsius (°C) [DHT11 sensor]",
    )
    temperature_critical_c: float = Field(
        default=65.0,
        ge=20.0,
        le=110.0,
        description="Temperature emergency trip cutoff in Celsius (°C)",
    )
    ambient_temp_warning_c: Optional[float] = Field(
        default=45.0,
        ge=15.0,
        le=95.0,
        description="Ambient air warning threshold in Celsius (°C)",
    )
    ambient_temp_critical_c: Optional[float] = Field(
        default=55.0,
        ge=20.0,
        le=110.0,
        description="Ambient air critical cutoff in Celsius (°C)",
    )
    casing_temp_warning_c: Optional[float] = Field(
        default=None,
        ge=20.0,
        le=130.0,
        description="Motor casing contact warning threshold in Celsius (°C)",
    )
    casing_temp_critical_c: Optional[float] = Field(
        default=None,
        ge=25.0,
        le=150.0,
        description="Motor casing contact critical cutoff in Celsius (°C)",
    )
    current_warning_a: float = Field(
        default=3.5,
        ge=0.5,
        le=18.0,
        description="Load current warning limit in Amperes (A) for 12V RS-775 motor [ACS712-20A]",
    )
    current_critical_a: float = Field(
        default=4.0,
        ge=1.0,
        le=20.0,
        description="Overcurrent trip cutoff limit in Amperes (A)",
    )
    current_hard_limit_a: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=25.0,
        description="Hardware hard cutoff ceiling in Amperes (only if circuit breaker / fast fuse installed)",
    )
    vibration_warning_g: float = Field(
        default=0.20,
        ge=0.01,
        le=5.0,
        description="ADXL345 RMS vibration warning limit in earth gravity (g) units [not m/s²]",
    )
    vibration_critical_g: float = Field(
        default=0.80,
        ge=0.05,
        le=10.0,
        description="ADXL345 RMS vibration severe trip cutoff in earth gravity (g) units [not m/s²]",
    )
    stale_timeout_sec: int = Field(
        default=15,
        ge=5,
        le=120,
        description="Device telemetry stale warning threshold in seconds",
    )
    offline_timeout_sec: int = Field(
        default=35,
        ge=10,
        le=300,
        description="Device offline disconnection timeout in seconds",
    )
    startup_grace_period_sec: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Startup inrush current transient grace period in seconds",
    )
    calibration_status: Literal[
        "manufacturer_verified", "measured_and_calibrated", "provisional", "unconfigured"
    ] = Field(
        default="provisional",
        description="Calibration certainty: manufacturer_verified, measured_and_calibrated, provisional, unconfigured",
    )
    provenance: str = Field(
        default="Gateway operational baseline (provisional)",
        description="Provenance of limits (bench run ID, manufacturer spec sheet, or provisional)",
    )

    @model_validator(mode="after")
    def validate_safety_margins(self) -> "OperationalLimitsBase":
        """Enforce strict monotonic ordering: warning alert < critical emergency trip."""
        if self.temperature_warning_c >= self.temperature_critical_c:
            raise ValueError(
                f"Temperature warning ({self.temperature_warning_c}°C) must be less than critical trip ({self.temperature_critical_c}°C)"
            )
        if self.current_warning_a >= self.current_critical_a:
            raise ValueError(
                f"Current warning ({self.current_warning_a}A) must be less than critical trip ({self.current_critical_a}A)"
            )
        if self.vibration_warning_g >= self.vibration_critical_g:
            raise ValueError(
                f"Vibration warning ({self.vibration_warning_g}g) must be less than critical trip ({self.vibration_critical_g}g)"
            )
        if self.stale_timeout_sec >= self.offline_timeout_sec:
            raise ValueError(
                f"Stale timeout ({self.stale_timeout_sec}s) must be less than offline timeout ({self.offline_timeout_sec}s)"
            )
        return self


class OperationalLimitsUpdate(OperationalLimitsBase):
    """Payload for updating operational threshold limits."""
    pass


class OperationalLimitsOut(OperationalLimitsBase):
    """Response payload containing active thresholds and audit metadata."""
    updated_by: Optional[str] = Field(
        default="system_default",
        description="Username of operator or system that last modified settings",
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of last threshold modification",
    )
