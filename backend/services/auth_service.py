"""
AI Music Studio - Secure Authentication & JWT Token Service
Implements standard bcrypt password hashing, JWT token encoding/decoding,
and role-based authorization (USER vs ADMIN).

Security Standards:
- Passwords hashed directly using native bcrypt with 12 salt rounds (never plaintext).
- Passwords safely truncated to 72 bytes per the bcrypt specification.
- JWT signed using HS256 with server-side SECRET_KEY from environment.
- Sub claim carries unique user ID; role claim enforces authorization boundaries.
- No secrets or credentials returned to clients.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple

import bcrypt
from dotenv import load_dotenv

try:
    import jwt
    from jwt.exceptions import PyJWTError as JWTError
except ImportError:
    from jose import JWTError, jwt

from fastapi import HTTPException, status, Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

# Load environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from backend.database.connection import get_db
from backend.database.models import User

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_in_production_ai_music_studio")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours default

# OAuth2 scheme for extracting Bearer tokens from HTTP Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    """Hash a plaintext password securely using native bcrypt (12 salt rounds)."""
    # Truncate to 72 bytes per bcrypt max length
    pw_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plaintext password matches the stored bcrypt hash."""
    try:
        pw_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, int]:
    """Generate a signed JWT access token containing subject and role claims."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    expires_in_sec = int((expire - now).total_seconds())
    return encoded_jwt, expires_in_sec


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Extract the authenticated user if a valid Bearer token is provided.
    Returns None if no token or invalid token is supplied (allows public fallback).
    """
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def get_current_user_from_header_or_query(
    token_header: Optional[str] = Depends(oauth2_scheme),
    token_query: Optional[str] = Query(None, alias="token"),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Extract authenticated user from either HTTP Authorization header
    or ?token= query parameter (for native HTML5 audio streaming & media downloads).
    Returns None if unauthenticated.
    """
    token = token_header or token_query
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Strict dependency: Requires a valid authenticated user.
    Raises 401 Unauthorized if token is missing, invalid, or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise credentials_exception

    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Strict dependency: Requires the authenticated user to have the ADMIN role.
    Raises 403 Forbidden if the user is a standard USER.
    """
    if current_user.role.upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access this resource.",
        )
    return current_user