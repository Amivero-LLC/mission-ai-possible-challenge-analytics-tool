from __future__ import annotations

import enum
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base


class AuthProvider(str, enum.Enum):
    LOCAL = "local"
    O365 = "o365"


class AuthRole(str, enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"


def _uuid() -> str:
    return str(uuid.uuid4())


class AuthUser(Base):
    __tablename__ = "auth_users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_provider: Mapped[AuthProvider] = mapped_column(Enum(AuthProvider), nullable=False, default=AuthProvider.LOCAL)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[AuthRole] = mapped_column(Enum(AuthRole), nullable=False, default=AuthRole.ADMIN)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    azure_tenant_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    azure_oid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    identity_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    refresh_tokens: Mapped[list["AuthRefreshToken"]] = relationship(
        "AuthRefreshToken",
        cascade="all, delete-orphan",
        back_populates="user",
    )
    email_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        "EmailVerificationToken",
        cascade="all, delete-orphan",
        back_populates="user",
    )
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        cascade="all, delete-orphan",
        back_populates="user",
    )


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)
    jti: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    user: Mapped[AuthUser] = relationship("AuthUser", back_populates="refresh_tokens")

    @staticmethod
    def expiry(days: int = 14) -> datetime:
        return datetime.now(timezone.utc) + timedelta(days=days)


class OAuthState(Base):
    __tablename__ = "auth_oauth_states"

    state: Mapped[str] = mapped_column(String, primary_key=True)
    code_challenge: Mapped[str] = mapped_column(String, nullable=False)
    code_verifier: Mapped[str] = mapped_column(String, nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String, nullable=False, default="S256")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    redirect_to: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class PasswordResetToken(Base):
    __tablename__ = "auth_password_reset_tokens"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[AuthUser] = relationship("AuthUser", back_populates="reset_tokens")


class EmailVerificationToken(Base):
    __tablename__ = "auth_email_verification_tokens"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[AuthUser] = relationship("AuthUser", back_populates="email_tokens")


class AuthAuditLog(Base):
    __tablename__ = "auth_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("auth_users.id"), nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("auth_users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    actor: Mapped[Optional[AuthUser]] = relationship("AuthUser", foreign_keys=[actor_id])
    subject: Mapped[Optional[AuthUser]] = relationship("AuthUser", foreign_keys=[user_id])


class AuthMode(str, enum.Enum):
    DEFAULT = "DEFAULT"
    HYBRID = "HYBRID"
    OAUTH = "OAUTH"


__all__ = [
    "AuthProvider",
    "AuthRole",
    "AuthUser",
    "AuthRefreshToken",
    "OAuthState",
    "PasswordResetToken",
    "EmailVerificationToken",
    "AuthAuditLog",
    "AuthMode",
]
