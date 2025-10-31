from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, constr

from .models import AuthMode, AuthProvider, AuthRole


class BootstrapStatus(BaseModel):
    needs_setup: bool
    auth_mode: AuthMode


class BootstrapRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=12)
    username: Optional[str] = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=12)
    username: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=8)
    remember_me: bool = False


class ApprovalStatus(BaseModel):
    is_approved: bool
    is_active: bool
    email_verified: bool


class AuthUserOut(BaseModel):
    id: str
    email: EmailStr
    username: Optional[str] = None
    role: AuthRole
    auth_provider: AuthProvider
    is_approved: bool
    is_active: bool
    email_verified: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(..., description="Access token TTL in seconds")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: constr(min_length=12)


class EmailVerificationRequest(BaseModel):
    token: str


class OAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class OAuthSettings(BaseModel):
    tenant_id: str
    client_id: str
    redirect_uri: str
    scopes: list[str]


class ModeResponse(BaseModel):
    auth_mode: AuthMode


class AdminUserUpdateRequest(BaseModel):
    is_approved: Optional[bool] = None
    is_active: Optional[bool] = None
    role: Optional[AuthRole] = None


class AdminUserListResponse(BaseModel):
    users: list[AuthUserOut]


class UserSyncRequest(BaseModel):
    emails: list[EmailStr] = Field(default_factory=list)
    source: str = Field(default="manual")


class AuditEntry(BaseModel):
    id: int
    action: str
    actor_id: Optional[str] = None
    user_id: Optional[str] = None
    details: Optional[dict] = None
    created_at: datetime


class AuditLogResponse(BaseModel):
    entries: list[AuditEntry]
