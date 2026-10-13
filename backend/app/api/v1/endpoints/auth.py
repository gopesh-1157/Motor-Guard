"""
MotorGuard — Auth & User Management Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.schemas.user import LoginRequest, Token, UserCreate, UserOut
from backend.app.services.user_service import UserService
from backend.app.core.auth import get_user_service, get_current_active_user, require_roles
from backend.app.core.security import create_access_token
from backend.app.config import settings

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    credentials: LoginRequest,
    user_service: UserService = Depends(get_user_service),
):
    """Authenticate with username/password and receive a signed JWT token."""
    user = await user_service.authenticate(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )

    user_out = UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        assigned_sites=user.assigned_sites,
        assigned_motors=user.assigned_motors,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=user_out,
    )


@router.get("/me", response_model=UserOut)
async def get_current_user_profile(
    current_user: UserOut = Depends(get_current_active_user),
):
    """Get profile of currently authenticated user."""
    return current_user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    current_user: UserOut = Depends(require_roles("Admin")),
    user_service: UserService = Depends(get_user_service),
):
    """Register a new user account (Requires 'Admin' role)."""
    existing_username = await user_service.get_by_username(user_in.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_in.username}' is already registered",
        )

    return await user_service.create_user(user_in)


@router.get("/users", response_model=List[UserOut])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: UserOut = Depends(require_roles("Admin")),
    user_service: UserService = Depends(get_user_service),
):
    """List system users (Requires 'Admin' role)."""
    return await user_service.list_users(skip=skip, limit=limit)
