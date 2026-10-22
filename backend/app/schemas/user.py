"""
MotorGuard — User & Auth Pydantic Schemas
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from backend.app.core.security import validate_password_strength

UserRole = Literal["Admin", "Manager", "Technician"]


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="User email address")
    role: UserRole = "Technician"
    assigned_sites: List[str] = Field(default_factory=list)
    assigned_motors: List[str] = Field(default_factory=list)
    is_active: bool = True
    session_revoked_at: Optional[datetime] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        valid, err = validate_password_strength(v)
        if not valid:
            raise ValueError(err)
        return v


class UserUpdate(BaseModel):
    email: Optional[str] = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: Optional[UserRole] = None
    assigned_sites: Optional[List[str]] = None
    assigned_motors: Optional[List[str]] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8)

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid, err = validate_password_strength(v)
            if not valid:
                raise ValueError(err)
        return v



class UserOut(UserBase):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class UserInDB(UserBase):
    id: Optional[str] = None
    password_hash: str
    created_at: datetime
    last_login_at: Optional[datetime] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
