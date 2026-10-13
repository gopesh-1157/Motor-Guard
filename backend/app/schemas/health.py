from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class LiveHealthResponse(BaseModel):
    status: str = Field(default="ok", json_schema_extra={"example": "ok"})
    version: str = Field(default="1.0.0", json_schema_extra={"example": "1.0.0"})


class DependencyHealth(BaseModel):
    status: str = Field(..., description="Service connection status: healthy, degraded, unavailable, or disabled")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Diagnostic details or latency metrics")


class ReadyHealthResponse(BaseModel):
    status: str = Field(..., description="System overall readiness: ok, degraded, or unavailable")
    version: str = Field(default="1.0.0", description="API version")
    dependencies: Dict[str, DependencyHealth] = Field(default_factory=dict, description="State of backing dependencies")
