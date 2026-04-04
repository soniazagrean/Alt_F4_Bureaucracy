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
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
