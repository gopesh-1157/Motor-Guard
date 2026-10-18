"""
MotorGuard — Audit Trail Schemas
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AuditLogOut(BaseModel):
    id: Optional[str] = None
    audit_id: str
    actor_username: str
    action: str
    entity_type: str
    entity_id: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
