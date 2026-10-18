"""
MotorGuard — Security & JWT Authentication Core

Handles password hashing (bcrypt) and JWT signing/validation.
Uses direct bcrypt to ensure Python 3.12 compatibility without passlib wrapping bugs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import bcrypt
from jose import JWTError, jwt
from backend.app.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generate bcrypt hash for a password."""
    # Truncate to 72 bytes if necessary per bcrypt algorithm limit
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password entropy:
    - Production: >=10 chars, uppercase, lowercase, digit, special character.
    - Development/Test: >=8 chars, letters, and at least one digit or symbol.
    """
    import re
    is_prod = settings.ENVIRONMENT.lower() == "production"

    if is_prod:
        if len(password) < 10:
            return False, "Production password must be at least 10 characters in length."
        if not re.search(r"[A-Z]", password):
            return False, "Production password must contain at least one uppercase letter."
        if not re.search(r"[a-z]", password):
            return False, "Production password must contain at least one lowercase letter."
        if not re.search(r"[0-9]", password):
            return False, "Production password must contain at least one digit."
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "Production password must contain at least one special symbol."
        return True, None

    # Development & test baseline
    if len(password) < 8:
        return False, "Password must be at least 8 characters in length."
    if not re.search(r"[a-zA-Z]", password):
        return False, "Password must contain alphabetic characters."
    if not re.search(r"[0-9!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one digit or special symbol."
    return True, None



def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None

