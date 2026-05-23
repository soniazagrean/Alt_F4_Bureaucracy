from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas import RoleEnum


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)
    full_name: Optional[str] = None
    role: RoleEnum = RoleEnum.VIEWER


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserMeResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str]
    role: RoleEnum
    rbac_role: str
    is_active: bool
    totp_enabled: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ── 2FA schemas ──────────────────────────────────────────────────────────────

class TwoFAVerifyRequest(BaseModel):
    """Step-2 login: exchange partial token + TOTP code for a full token pair."""
    partial_token: str
    code: str = Field(min_length=6, max_length=6)


class TwoFAEnableRequest(BaseModel):
    """Enable 2FA: provide the secret (from /2fa/setup) + first valid code."""
    secret: str
    code: str = Field(min_length=6, max_length=6)


class TwoFADisableRequest(BaseModel):
    """Disable 2FA: verify current code before removing."""
    code: str = Field(min_length=6, max_length=6)


class TwoFASetupResponse(BaseModel):
    secret: str
    qr_uri: str
    qr_image_b64: str
