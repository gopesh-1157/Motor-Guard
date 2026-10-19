import os
from typing import List, Optional
from pydantic import Field, field_validator, model_validator

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application Runtime & Security ---
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    SECRET_KEY: str = Field(
        default="change_this_to_a_secure_random_64_character_hex_string_in_production",
        description="256-bit secret for signing JWT tokens",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480, description="Session validity minutes")

    # --- Gateway Network Binding ---
    HOST: str = Field(default="0.0.0.0", description="Gateway host binding")
    PORT: int = Field(default=8000, description="Gateway port")
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated allowed origins",
    )

    # --- Local MongoDB Storage ---
    MONGO_URI: str = Field(default="mongodb://127.0.0.1:27017", description="MongoDB URI")
    MONGO_DB_NAME: str = Field(default="motorguard_db", description="Database name")
    TELEMETRY_RETENTION_DAYS: int = Field(default=90, description="Retention horizon in days")

    # --- Eclipse Mosquitto / Cloud MQTT Broker ---
    MQTT_BROKER_HOST: str = Field(default="127.0.0.1", description="MQTT broker host")
    MQTT_BROKER_PORT: int = Field(default=1883, description="MQTT broker port (1883 plain, 8883 TLS)")
    MQTT_USERNAME: str = Field(default="motorguard_gateway", description="MQTT broker username")
    MQTT_PASSWORD: str = Field(default="", description="MQTT broker password")
    MQTT_CLIENT_ID: str = Field(default="motorguard-fastapi-backend", description="MQTT client ID")
    MQTT_KEEPALIVE_SEC: int = Field(default=60, description="MQTT keepalive interval in seconds")

    # Global Cloud MQTTS / TLS Controls
    MQTT_USE_TLS: bool = Field(default=False, description="Enable TLS/SSL encryption for MQTT")
    MQTT_TLS_CA_CERT: Optional[str] = Field(default=None, description="Path to custom CA certificate bundle file")
    MQTT_TLS_INSECURE: bool = Field(default=False, description="Skip TLS certificate hostname verification (test only)")
    MQTT_TRANSPORT: str = Field(default="tcp", description="'tcp' or 'websockets'")

    DEVICE_STALE_TIMEOUT_SEC: int = Field(default=15, description="Stale timeout in seconds")
    DEVICE_OFFLINE_TIMEOUT_SEC: int = Field(default=35, description="Offline timeout in seconds")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    DEFAULT_OVERCURRENT_LIMIT_A: float = Field(default=4.0, description="Overcurrent limit in Amperes")
    DEFAULT_MAX_TEMP_C: float = Field(default=50.0, description="Thermal warning limit in Celsius")
    DEFAULT_MAX_VIBRATION_G: float = Field(default=0.100, description="Vibration RMS warning limit in g (ISO 10816 Class I/II)")
    DEFAULT_MAX_PEAK_VIBRATION_G: float = Field(default=0.350, description="Peak dynamic vibration shock limit in g")

    # Security & Hardening Controls
    DEBUG: bool = Field(default=False, description="Enable debug mode (strictly false in production)")
    ENABLE_DOCS: bool = Field(default=True, description="Enable OpenAPI docs UI (/docs and /redoc)")
    ADMIN_INITIAL_PASSWORD: Optional[str] = Field(
        default=None,
        description="Initial seed password for default Admin account",
    )
    RATELIMIT_ENABLED: bool = Field(default=True, description="Enable sliding-window rate limiting")
    RATELIMIT_LOGIN_PER_MIN: int = Field(default=10, description="Max login attempts per minute per IP")
    RATELIMIT_GENERAL_PER_MIN: int = Field(default=180, description="Max general API requests per minute per IP")
    TRUSTED_PROXIES: str = Field(default="127.0.0.1,::1,testclient", description="Comma-separated list of trusted reverse proxy IPs")
    GATEWAY_INGEST_SECRET: str = Field(default="motorguard-dev-ingest-key", description="Shared secret for hardware/bridge telemetry ingestion")

    # App Metadata
    APP_VERSION: str = "1.0.0"
    APP_NAME: str = "MotorGuard Edge Gateway API"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            # In development fallback to standard frontend ports; never return wildcard '*' with credentials
            if self.ENVIRONMENT.lower() != "production":
                return ["http://localhost:5173", "http://127.0.0.1:5173"]
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip() and origin.strip() != "*"]

    @property
    def trusted_proxies_list(self) -> List[str]:
        if not self.TRUSTED_PROXIES:
            return ["127.0.0.1", "::1"]
        return [ip.strip() for ip in self.TRUSTED_PROXIES.split(",") if ip.strip()]

    @model_validator(mode="after")
    def validate_production_requirements(self) -> "Settings":
        # Validate MQTT TLS configuration consistency
        if self.MQTT_BROKER_PORT == 8883 and not self.MQTT_USE_TLS:
            raise ValueError(
                "Contradictory MQTT configuration: Port 8883 is designated for MQTTS and requires MQTT_USE_TLS=True."
            )

        is_cloud_broker = any(
            cloud in self.MQTT_BROKER_HOST.lower()
            for cloud in ("hivemq.cloud", "emqx.cloud", "amazonaws.com", "azure-devices.net")
        )
        if is_cloud_broker and not self.MQTT_USE_TLS:
            raise ValueError(
                f"Cloud MQTT broker '{self.MQTT_BROKER_HOST}' requires secure TLS (MQTT_USE_TLS=True)."
            )

        if self.ENVIRONMENT.strip().lower() == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be set to False in production")
            if (
                not self.SECRET_KEY
                or "change_this" in self.SECRET_KEY
                or len(self.SECRET_KEY) < 32
            ):
                raise ValueError(
                    "SECRET_KEY must be a secure random string of at least 32 characters in production"
                )
            if (
                not self.GATEWAY_INGEST_SECRET
                or self.GATEWAY_INGEST_SECRET == "motorguard-dev-ingest-key"
                or len(self.GATEWAY_INGEST_SECRET) < 16
            ):
                raise ValueError(
                    "GATEWAY_INGEST_SECRET must be configured with a secure random secret of at least 16 characters in production"
                )
            if not self.ADMIN_INITIAL_PASSWORD:
                raise ValueError(
                    "ADMIN_INITIAL_PASSWORD must be explicitly configured in production; fallback default is strictly prohibited"
                )
            if (
                self.ADMIN_INITIAL_PASSWORD.strip() in ("adminpassword123", "password", "admin123456", "admin")
                or len(self.ADMIN_INITIAL_PASSWORD.strip()) < 12
            ):
                raise ValueError(
                    "ADMIN_INITIAL_PASSWORD in production must be at least 12 characters and cannot use default passwords"
                )
            if not self.MQTT_PASSWORD:
                raise ValueError("MQTT_PASSWORD must be configured in production")
            if self.MQTT_TLS_INSECURE:
                raise ValueError("MQTT_TLS_INSECURE=True is strictly forbidden in production")
            is_remote_broker = self.MQTT_BROKER_HOST not in ("127.0.0.1", "localhost", "0.0.0.0")
            if is_remote_broker and not self.MQTT_USE_TLS:
                raise ValueError("Remote MQTT broker connections in production must have MQTT_USE_TLS=True")
            if not self.cors_origins_list:
                raise ValueError("Explicit CORS_ORIGINS must be configured in production (wildcard '*' is forbidden)")
            # Disable interactive docs in production by default
            self.ENABLE_DOCS = False
        return self


settings = Settings()
