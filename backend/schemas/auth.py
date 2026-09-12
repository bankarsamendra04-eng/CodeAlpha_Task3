"""
AI Music Studio - Authentication Schemas (Pydantic v2)
Defines registration, login, token, and user profile schemas.
"""

from enum import Enum
import re
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class RoleEnum(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class UserRegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique username or name for studio creator.",
        examples=["mozart_ai"],
    )
    email: str = Field(
        ...,
        description="Valid email address.",
        examples=["creator@aimusicstudio.io"],
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Password (minimum 6 characters).",
        examples=["SecretHarmony#2026"],
    )
    confirm_password: Optional[str] = Field(
        default=None,
        description="Confirmation of password.",
    )
    role: Optional[RoleEnum] = Field(
        default=RoleEnum.USER,
        description="Account role: USER or ADMIN.",
    )
    admin_invite_code: Optional[str] = Field(
        default=None,
        description="Required secret verification code to register with ADMIN privileges.",
    )

    @field_validator("username")
    @classmethod
    def validate_username_format(cls, v: str) -> str:
        clean = v.strip()
        if not re.match(r"^[a-zA-Z0-9_\-\. ]{3,50}$", clean):
            raise ValueError("Username/Name must be between 3 and 50 characters and contain letters, numbers, spaces, underscores, dashes, or dots.")
        return clean

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        # Strict standard email validation pattern
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", clean) or ".." in clean:
            raise ValueError("Invalid email address format. Must be a valid email (e.g. user@example.com).")
        return clean

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        return v


class UserLoginRequest(BaseModel):
    username: str = Field(
        ...,
        description="Registered username or email.",
        examples=["mozart_ai"],
    )
    password: str = Field(
        ...,
        description="Account password.",
        examples=["SecretHarmony#2026"],
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    subscription_tier: Optional[str] = "FREE"
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


TokenResponse.model_rebuild()