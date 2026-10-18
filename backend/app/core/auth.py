"""
MotorGuard — FastAPI Authentication & RBAC Dependencies

Enforces JWT extraction, user validation, and server-side role hierarchy.
"""

from typing import Callable, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from backend.app.core.security import decode_access_token
from backend.app.schemas.user import UserOut
from backend.app.db.mongodb import db_manager
from backend.app.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def get_user_service() -> UserService:
    """Dependency provider for UserService."""
    if db_manager.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    return UserService(db_manager.db)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> UserOut:
    """Extract and validate JWT token to resolve the authenticated User."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    from backend.app.main import app
    if get_user_service in app.dependency_overrides:
        override = app.dependency_overrides[get_user_service]
        user_service = override() if callable(override) else override
    else:
        user_service = get_user_service()

    user = await user_service.get_by_username(username)
    if user is None:
        raise credentials_exception


    return UserOut(
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


async def get_current_active_user(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    """Ensure the authenticated user account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


def require_roles(*allowed_roles: str) -> Callable:
    """
    Dependency factory to enforce server-side Role-Based Access Control (RBAC).
    
    Example:
        @router.post("/motors/{id}/maintenance", dependencies=[Depends(require_roles("Admin", "Technician"))])
    """
    async def role_checker(
        current_user: UserOut = Depends(get_current_active_user),
    ) -> UserOut:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires role in {allowed_roles}. Current role: '{current_user.role}'",
            )
        return current_user

    return role_checker
