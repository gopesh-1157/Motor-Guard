"""
MotorGuard — Auth & User Management Endpoints
"""

from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.schemas.user import LoginRequest, Token, UserCreate, UserUpdate, UserOut, UserProfileUpdate
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


@router.patch("/me", response_model=UserOut)
async def update_current_user_profile(
    profile_in: UserProfileUpdate,
    current_user: UserOut = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
):
    """Update profile of currently authenticated user (email, password)."""
    return await user_service.update_profile(
        user_id=current_user.id,
        email=profile_in.email,
        password=profile_in.password,
        current_password=profile_in.current_password,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    user_service: UserService = Depends(get_user_service),
):
    """Register a new user account (Requires 'Admin' or 'Manager' role)."""
    # Manager can only provision Technicians
    if current_user.role == "Manager":
        if user_in.role != "Technician":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Managers cannot provision accounts with role '{user_in.role}'. Only 'Technician' is permitted.",
            )
    else:
        # Security Constraint: Admin cannot create another Admin through ordinary APIs
        if user_in.role == "Admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Creating Admin accounts through standard user management is prohibited. Admin accounts require system bootstrap.",
            )
        if user_in.role not in ("Manager", "Technician"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{user_in.role}' is invalid. Standard user creation permits only 'Manager' or 'Technician'.",
            )

    existing_username = await user_service.get_by_username(user_in.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_in.username}' is already registered",
        )

    existing_email = await user_service.get_by_email(user_in.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{user_in.email}' is already registered",
        )

    return await user_service.create_user(user_in, actor=current_user.username)


@router.get("/users", response_model=List[UserOut])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    user_service: UserService = Depends(get_user_service),
):
    """List system users (Admin views all, Manager views users in their assigned sites)."""
    site_filter = None
    if current_user.role == "Manager":
        site_filter = current_user.assigned_sites if (current_user.assigned_sites and len(current_user.assigned_sites) > 0) else None
    return await user_service.list_users(skip=skip, limit=limit, site_filter=site_filter)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user_by_id(
    user_id: str,
    current_user: UserOut = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
):
    """
    Get user details by id.
    Allowed for:
    - Admin: can view any user
    - The user themselves (current_user.id == user_id)
    - Manager: can view users whose assigned sites intersect with manager's assigned sites
    """
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found",
        )

    if current_user.role == "Admin" or current_user.id == user_id:
        return user

    if current_user.role == "Manager":
        manager_sites = set(current_user.assigned_sites or [])
        user_sites = set(user.assigned_sites or [])
        if manager_sites.intersection(user_sites):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: User is outside your assigned site scope",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Operation requires elevated privileges to inspect other users",
    )



@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    user_service: UserService = Depends(get_user_service),
):
    """Update user profile, permissions, or activation status (Requires 'Admin' or 'Manager' role)."""
    return await user_service.update_user(user_id, user_update, actor=current_user.username, actor_user=current_user)


class UserStatusUpdate(BaseModel):
    is_active: bool


@router.post("/users/{user_id}/status", response_model=UserOut)
async def toggle_user_status(
    user_id: str,
    is_active: Optional[bool] = None,
    status_body: Optional[UserStatusUpdate] = None,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    user_service: UserService = Depends(get_user_service),
):
    """Activate or deactivate user account with final Admin protection (Requires 'Admin' or 'Manager' role)."""
    target_active = is_active if is_active is not None else (status_body.is_active if status_body else None)
    if target_active is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required 'is_active' status parameter")
    return await user_service.update_user(user_id, UserUpdate(is_active=target_active), actor=current_user.username, actor_user=current_user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: UserOut = Depends(require_roles("Admin")),
    user_service: UserService = Depends(get_user_service),
):
    """Delete a user account with final Admin protection (Requires 'Admin' role)."""
    await user_service.delete_user(user_id, actor=current_user.username, actor_user=current_user)
    return None


@router.get("/technicians", response_model=List[UserOut])
async def list_technicians(
    site_id: str = None,
    current_user: UserOut = Depends(require_roles("Admin", "Manager")),
    user_service: UserService = Depends(get_user_service),
):
    """List eligible technicians for work order assignment (Requires 'Admin' or 'Manager' role)."""
    effective_site_id = site_id
    if current_user.role == "Manager" and current_user.assigned_sites:
        if site_id and site_id not in current_user.assigned_sites:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Site '{site_id}' is outside your authorized scope {current_user.assigned_sites}",
            )
        effective_site_id = site_id or (current_user.assigned_sites[0] if len(current_user.assigned_sites) == 1 else None)
    return await user_service.list_technicians(site_id=effective_site_id)
