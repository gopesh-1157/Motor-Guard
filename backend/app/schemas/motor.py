"""
MotorGuard — Motor Specification & Configuration Schemas
"""

import re
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class ElectricalSpecs(BaseModel):
    motor_type: str = Field(default="RS-775 Brushed DC", description="Motor construction type")
    rated_voltage_v: float = Field(..., gt=0.0, description="Rated operating voltage in Volts DC")
    rated_current_a: float = Field(..., gt=0.0, description="Manufacturer rated continuous current in Amperes")
    no_load_current_a: Optional[float] = Field(default=None, ge=0.0, description="No-load armature current in Amperes")
    rated_speed_rpm: Optional[int] = Field(default=None, gt=0, description="Rated speed under load in RPM")
    max_speed_rpm: Optional[int] = Field(default=None, gt=0, description="Maximum no-load speed in RPM")
    rated_power_w: Optional[float] = Field(default=None, gt=0.0, description="Rated continuous output power in Watts")
    motor_supply_type: str = Field(default="External DC supply", min_length=2)
    application_load: Optional[str] = Field(default="Plant Floor Conveyor Feed", description="Target machinery load")


class MechanicalSpecs(BaseModel):
    shaft_diameter_mm: Optional[float] = Field(default=5.0, gt=0.0)
    weight_grams: Optional[float] = Field(default=350.0, gt=0.0)
    mounting_type: Optional[str] = Field(default="Face Mount (M4)")
    cooling_type: Optional[str] = Field(default="Internal Centrifugal Fan")


class SensorDHT11Config(BaseModel):
    sensor_type: Literal["DHT11"] = "DHT11"
    gpio_pin: int = Field(default=4, ge=0, le=39)
    unit: str = "°C"
    sampling_interval_ms: int = Field(default=1500, ge=1000, description="DHT11 requires at least 1000ms")
    enabled: bool = True
    calibration_offset_c: float = 0.0


class SensorADXL345Config(BaseModel):
    sensor_type: Literal["ADXL345"] = "ADXL345"
    i2c_bus: int = Field(default=0, ge=0, le=1)
    sda_pin: int = Field(default=21, ge=0, le=39)
    scl_pin: int = Field(default=22, ge=0, le=39)
    measurement_range_g: Literal["2g", "4g", "8g", "16g"] = "16g"
    sample_frequency_hz: int = Field(default=100, ge=10, le=3200)
    axes: List[str] = Field(default_factory=lambda: ["X", "Y", "Z"])
    output_feature: str = "dynamic_rms_acceleration"
    measurement_unit: str = "g RMS"
    calibration_offset_g: float = 0.0
    enabled: bool = True


class SensorACS712Config(BaseModel):
    sensor_type: Literal["ACS712-20A", "ACS712-5A", "ACS712-30A"] = "ACS712-20A"
    analog_gpio_pin: int = Field(default=34, ge=0, le=39)
    module_supply_v: float = Field(default=5.0, gt=0.0)
    sensitivity_mv_per_a: float = Field(default=100.0, gt=0.0)
    zero_current_voltage_v: float = Field(default=2.50, ge=1.0, le=4.0)
    voltage_divider_ratio: float = Field(default=0.6667, gt=0.0, le=1.0)
    output_unit: str = "A"
    enabled: bool = True


class SensorSH1106Config(BaseModel):
    display_type: Literal["SH1106"] = "SH1106"
    i2c_bus: int = Field(default=1, ge=0, le=1)
    sda_pin: int = Field(default=32, ge=0, le=39)
    scl_pin: int = Field(default=33, ge=0, le=39)
    i2c_address: str = "0x3C"
    enabled: bool = True


class SensorsConfig(BaseModel):
    dht11: SensorDHT11Config = Field(default_factory=SensorDHT11Config)
    adxl345: SensorADXL345Config = Field(default_factory=SensorADXL345Config)
    acs712: SensorACS712Config = Field(default_factory=SensorACS712Config)
    sh1106: SensorSH1106Config = Field(default_factory=SensorSH1106Config)

    @model_validator(mode="after")
    def validate_gpio_conflicts(self):
        """Ensure no two enabled sensors share the same GPIO pin on the ESP32."""
        used_pins: Dict[int, str] = {}

        if self.dht11.enabled:
            pin = self.dht11.gpio_pin
            used_pins[pin] = "DHT11 (Data)"

        if self.acs712.enabled:
            pin = self.acs712.analog_gpio_pin
            if pin in used_pins:
                raise ValueError(f"GPIO {pin} conflict between ACS712 and {used_pins[pin]}")
            used_pins[pin] = "ACS712 (Analog)"

        if self.adxl345.enabled:
            sda, scl = self.adxl345.sda_pin, self.adxl345.scl_pin
            if sda == scl:
                raise ValueError("ADXL345 SDA and SCL cannot use the same pin")
            if sda in used_pins:
                raise ValueError(f"GPIO {sda} conflict between ADXL345 SDA and {used_pins[sda]}")
            used_pins[sda] = "ADXL345 SDA"
            if scl in used_pins:
                raise ValueError(f"GPIO {scl} conflict between ADXL345 SCL and {used_pins[scl]}")
            used_pins[scl] = "ADXL345 SCL"

        if self.sh1106.enabled:
            sda, scl = self.sh1106.sda_pin, self.sh1106.scl_pin
            if sda == scl:
                raise ValueError("SH1106 SDA and SCL cannot use the same pin")
            if sda in used_pins:
                raise ValueError(f"GPIO {sda} conflict between SH1106 SDA and {used_pins[sda]}")
            used_pins[sda] = "SH1106 SDA"
            if scl in used_pins:
                raise ValueError(f"GPIO {scl} conflict between SH1106 SCL and {used_pins[scl]}")
            used_pins[scl] = "SH1106 SCL"

        return self


class HealthThresholds(BaseModel):
    temperature_warning_c: float = Field(default=45.0, ge=0.0, le=120.0)
    temperature_critical_c: float = Field(default=50.0, ge=0.0, le=120.0)
    ambient_temp_warning_c: Optional[float] = Field(default=45.0, ge=0.0, le=120.0)
    ambient_temp_critical_c: Optional[float] = Field(default=55.0, ge=0.0, le=120.0)
    casing_temp_warning_c: Optional[float] = Field(default=None, ge=0.0, le=150.0)
    casing_temp_critical_c: Optional[float] = Field(default=None, ge=0.0, le=150.0)
    current_warning_a: float = Field(default=3.0, ge=0.0, le=30.0)
    current_critical_a: float = Field(default=4.0, ge=0.0, le=30.0)
    current_hard_limit_a: Optional[float] = Field(default=None, ge=0.0, le=40.0)
    vibration_warning_g: float = Field(default=0.5, ge=0.0, le=16.0)
    vibration_critical_g: float = Field(default=1.0, ge=0.0, le=16.0)
    device_offline_timeout_sec: int = Field(default=30, ge=5, le=3600)
    alert_persistence_sec: int = Field(default=10, ge=1, le=300)
    alert_cooldown_sec: int = Field(default=60, ge=5, le=3600)
    hysteresis_percentage: float = Field(default=5.0, ge=0.0, le=20.0)
    startup_grace_period_sec: float = Field(default=0.5, ge=0.0, le=10.0)
    calibration_status: Literal[
        "manufacturer_verified", "measured_calibrated", "measured_and_calibrated", "provisional", "unconfigured"
    ] = Field(
        default="provisional",
        description="Threshold status: manufacturer_verified, measured_calibrated, provisional, or unconfigured",
    )
    provenance: str = Field(
        default="Provisional RS-775 baseline limits (uncalibrated)",
        description="Source of threshold values (e.g. datasheet, bench test run, provisional)",
    )

    @model_validator(mode="after")
    def validate_threshold_order(self):
        """Enforce warning threshold < critical threshold for safety parameters."""
        if self.temperature_warning_c >= self.temperature_critical_c:
            raise ValueError(
                f"Temperature warning ({self.temperature_warning_c}°C) must be less than critical ({self.temperature_critical_c}°C)"
            )
        if self.current_warning_a >= self.current_critical_a:
            raise ValueError(
                f"Current warning ({self.current_warning_a}A) must be less than critical ({self.current_critical_a}A)"
            )
        if self.vibration_warning_g >= self.vibration_critical_g:
            raise ValueError(
                f"Vibration warning ({self.vibration_warning_g}g) must be less than critical ({self.vibration_critical_g}g)"
            )
        if (
            self.casing_temp_warning_c is not None
            and self.casing_temp_critical_c is not None
            and self.casing_temp_warning_c >= self.casing_temp_critical_c
        ):
            raise ValueError(
                f"Casing temperature warning ({self.casing_temp_warning_c}°C) must be less than critical ({self.casing_temp_critical_c}°C)"
            )
        return self


class EdgeImpulseConfig(BaseModel):
    enabled: bool = True
    model_name: str = "MotoGuard_Motor_Health_inferencing"
    model_version: str = "v1.0.1"
    deployment_type: str = "ESP32 embedded inference"
    expected_input_format: str = "ADXL345 dynamic RMS (100 Hz, 50 samples) + ACS712 + DHT11"
    sample_frequency_hz: int = Field(default=100, ge=10, le=1000)
    window_length_ms: int = Field(default=500, ge=50, le=5000)
    class_mapping: List[str] = Field(default_factory=lambda: ["healthy", "warning", "critical"])
    last_inference_timestamp: Optional[str] = None

    @field_validator("class_mapping")
    @classmethod
    def validate_classes(cls, classes: List[str]) -> List[str]:
        required = {"healthy", "warning", "critical"}
        if not required.issubset(set(c.lower() for c in classes)):
            raise ValueError("Edge Impulse model must output at least 'healthy', 'warning', and 'critical' classes")
        return classes


class MotorCreate(BaseModel):
    motor_id: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]{3,32}$")
    name: str = Field(..., min_length=2, max_length=100)
    motor_type: str = Field(default="RS-775 Brushed DC", min_length=2)
    manufacturer: Optional[str] = Field(default=None, max_length=100)
    model_number: Optional[str] = Field(default=None, max_length=100)
    serial_number: Optional[str] = Field(default=None, max_length=100)
    site_id: str = Field(default="SITE-PLANT-A", min_length=2, max_length=50)
    installation_date: Optional[str] = None
    description: Optional[str] = None
    status: Literal["active", "inactive"] = "active"
    electrical_specs: ElectricalSpecs
    mechanical_specs: Optional[MechanicalSpecs] = Field(default_factory=MechanicalSpecs)
    sensors_config: SensorsConfig = Field(default_factory=SensorsConfig)
    thresholds: HealthThresholds = Field(default_factory=HealthThresholds)
    edge_impulse_config: EdgeImpulseConfig = Field(default_factory=EdgeImpulseConfig)
    assigned_device_id: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{3,32}$")


class MotorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    serial_number: Optional[str] = None
    site_id: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None
    electrical_specs: Optional[ElectricalSpecs] = None
    mechanical_specs: Optional[MechanicalSpecs] = None
    sensors_config: Optional[SensorsConfig] = None
    thresholds: Optional[HealthThresholds] = None
    edge_impulse_config: Optional[EdgeImpulseConfig] = None
    assigned_device_id: Optional[str] = None


class MotorOut(BaseModel):
    motor_id: str
    name: str
    motor_type: str
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    serial_number: Optional[str] = None
    site_id: str
    installation_date: Optional[str] = None
    description: Optional[str] = None
    status: Literal["active", "inactive"] = "active"
    electrical_specs: ElectricalSpecs
    mechanical_specs: Optional[MechanicalSpecs] = None
    sensors_config: SensorsConfig
    thresholds: HealthThresholds
    edge_impulse_config: EdgeImpulseConfig
    assigned_device_id: Optional[str] = None
    configuration_version: int = 1
    health_status: Literal["healthy", "warning", "critical", "unknown"] = "unknown"
    operational_state: Literal["RUNNING", "IDLE", "ALARM", "OFFLINE"] = "OFFLINE"
    effective_thresholds: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
