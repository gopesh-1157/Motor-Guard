"""
MotorGuard — Work Order Schemas & Lifecycle Models

Defines the data contract for the end-to-end maintenance workflow:
Assigned -> Accepted -> In Progress -> Resolved (or Rejected)
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

WorkOrderStatus = Literal["Assigned", "Accepted", "In Progress", "Resolved", "Rejected"]
WorkOrderPriority = Literal["LOW", "MEDIUM", "HIGH", "URGENT", "CRITICAL"]


class WorkOrderCreate(BaseModel):
    motor_id: str = Field(..., min_length=2)
    alert_id: Optional[str] = None
    assigned_to_user_id: str = Field(..., min_length=2, description="Technician username")
    priority: WorkOrderPriority = "HIGH"
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., min_length=5)


class WorkOrderAcceptRequest(BaseModel):
    notes: Optional[str] = None


class WorkOrderStartRequest(BaseModel):
    notes: Optional[str] = None


class WorkOrderResolveRequest(BaseModel):
    diagnosis: str = Field(..., min_length=3, description="Root cause diagnosis")
    actions_taken: str = Field(..., min_length=3, description="Corrective actions performed")
    parts_replaced: List[str] = Field(default_factory=list)
    downtime_minutes: int = Field(default=0, ge=0)
    resolution_notes: str = Field(..., min_length=3, description="Final sign-off summary")


class WorkOrderRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, description="Reason for rejection or reassignment")


class WorkOrderOut(BaseModel):
    id: Optional[str] = None
    work_order_id: str
    motor_id: str
    alert_id: Optional[str] = None
    assigned_to_user_id: str
    assigned_by_user_id: str
    priority: WorkOrderPriority
    title: str
    description: str
    status: WorkOrderStatus
    created_at: datetime
    assigned_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    diagnosis: Optional[str] = None
    actions_taken: Optional[str] = None
    parts_replaced: List[str] = Field(default_factory=list)
    downtime_minutes: int = 0
    resolution_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    updated_at: datetime
