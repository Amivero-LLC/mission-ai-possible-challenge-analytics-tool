from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..db.models import User as AnalyticsUser
from ..db.session import get_db_session
from .config import get_auth_config
from .models import AuthAuditLog, AuthMode, AuthProvider, AuthRefreshToken, AuthRole, AuthUser, EmailVerificationToken, OAuthState, PasswordResetToken
from .oauth import build_authorization_url, exchange_code_for_token, verify_id_token
from .schemas import (
    AdminUserUpdateRequest,
    AuditEntry,
    AuthUserOut,
    BootstrapRequest,
    ForgotPasswordRequest,
    LoginRequest,
    OAuthCallbackRequest,
    OAuthStartResponse,
    RegisterCompleteRequest,
    RegisterStartRequest,
    RegisterStartResponse,
    ResetPasswordRequest,
    UserSyncRequest,
)
from .security import (
    create_access_token,
    create_pkce_challenge,
    create_refresh_token,
    generate_code_verifier,
    generate_state,
    generate_token_id,
    hash_password,
    hash_token,
    verify_password,
)

logger = logging.getLogger(__name__)


def get_auth_mode() -> AuthMode:
    return get_auth_config().auth_mode


def _ensure_email_allowed(db: Session, email: str) -> None:
    count = db.scalar(
        select(func.count()).select_from(AnalyticsUser).where(func.lower(AnalyticsUser.email) == email.lower())
    )
    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email is not pre-approved. Contact an administrator.",
        )


def bootstrap_required(db: Session) -> bool:
    return db.scalar(select(func.count()).select_from(AuthUser)) == 0


def create_bootstrap_admin(db: Session, payload: BootstrapRequest) -> AuthUser:
    user = AuthUser(
        email=payload.email.lower(),
        username=payload.username,
        auth_provider=AuthProvider.LOCAL,
        password_hash=hash_password(payload.password),
        role=AuthRole.ADMIN,
        is_approved=True,
        is_active=True,
        email_verified=True,
        source="bootstrap",
    )
    db.add(user)
    db.flush()
    _record_audit(db, action="bootstrap", actor=user, subject=user, details={"email": user.email})
    return user


def start_registration(db: Session, payload: RegisterStartRequest) -> RegisterStartResponse:
    if bootstrap_required(db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System requires initial setup.")
    if get_auth_mode() == AuthMode.OAUTH:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local registration is disabled.")

    _ensure_email_allowed(db, payload.email)

    email = payload.email.lower()
    user = db.scalar(select(AuthUser).where(func.lower(AuthUser.email) == email))

    if user:
        if user.auth_provider != AuthProvider.LOCAL:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account uses single sign-on.")

        if payload.username and not user.username:
            user.username = payload.username
            db.flush()

        if user.password_hash:
            return RegisterStartResponse(
                status="password_reset_required",
                message="An account already exists. Use the password reset workflow to regain access.",
            )

        if user.is_approved:
            return RegisterStartResponse(
                status="password_setup_required",
                message="Your account is approved. Set your password to finish signing up.",
            )

        return RegisterStartResponse(
            status="pending_approval",
            message="Registration already received. Awaiting administrator approval.",
        )

    user = AuthUser(
        email=email,
        username=payload.username,
        auth_provider=AuthProvider.LOCAL,
        password_hash=None,
        role=AuthRole.ADMIN if get_auth_config().feature_role_user_enabled is False else AuthRole.USER,
        is_approved=False,
        is_active=True,
        email_verified=False,
        source="local",
    )
    db.add(user)
    db.flush()
    _record_audit(db, action="register_start", actor=user, subject=user, details={"provider": "local"})

    return RegisterStartResponse(
        status="pending_approval",
        message="Registration submitted. Awaiting administrator approval.",
    )


def complete_registration_password(db: Session, payload: RegisterCompleteRequest) -> AuthUser:
    if bootstrap_required(db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System requires initial setup.")
    if get_auth_mode() == AuthMode.OAUTH:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local registration is disabled.")

    email = payload.email.lower()
    user = db.scalar(select(AuthUser).where(func.lower(AuthUser.email) == email))
    if not user or user.auth_provider != AuthProvider.LOCAL:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    if user.password_hash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Password already set. Use password reset instead.")
    if not user.is_approved:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account pending approval.")

    user.password_hash = hash_password(payload.password)
    user.email_verified = True
    user.is_active = True
    db.flush()
    _record_audit(db, action="register_complete", actor=user, subject=user)
    return user


def authenticate_local_user(db: Session, payload: LoginRequest) -> AuthUser:
    if bootstrap_required(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System requires initial setup.",
        )
    user = db.scalar(
        select(AuthUser).where(func.lower(AuthUser.email) == payload.email.lower())
    )
    if not user or user.auth_provider != AuthProvider.LOCAL:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    if not verify_password(payload.password, user.password_hash):
        _record_audit(
            db,
            action="login_failed",
            actor=user,
            subject=user,
            details={"reason": "bad_password"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    if not user.is_active or not user.is_approved:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is pending approval.")

    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    _record_audit(db, action="login_success", actor=user, subject=user, details={"provider": "local"})
    return user


def issue_tokens(db: Session, user: AuthUser, remember_me: bool = False) -> tuple[str, datetime, str, datetime]:
    access_token, access_exp = create_access_token(
        subject=user.id,
        role=user.role.value,
        approved=user.is_approved,
        active=user.is_active,
        email_verified=user.email_verified,
    )
    token_id = generate_token_id()
    refresh_token, refresh_exp = create_refresh_token(subject=user.id, jti=token_id)

    token_record = AuthRefreshToken(
        user_id=user.id,
        jti=token_id,
        token_hash=hash_token(refresh_token),
        expires_at=refresh_exp,
    )
    if remember_me:
        token_record.expires_at = datetime.now(timezone.utc) + timedelta(days=max(30, get_auth_config().refresh_token_ttl_days))
    db.add(token_record)
    db.flush()
    return access_token, access_exp, refresh_token, token_record.expires_at


def refresh_session(db: Session, refresh_token: str) -> tuple[AuthUser, str, datetime, str, datetime]:
    try:
        payload = verify_token(refresh_token, expected_type="refresh")
    except HTTPException:
        raise

    token = db.scalar(
        select(AuthRefreshToken).where(AuthRefreshToken.jti == payload["jti"])
    )
    if not token or token.revoked_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired.")

    if hash_token(refresh_token) != token.token_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalid.")

    if token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired.")

    user = db.get(AuthUser, token.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.")

    access_token, access_exp, new_refresh, new_refresh_exp = issue_tokens(db, user)
    token.revoked_at = datetime.now(timezone.utc)
    db.flush()
    return user, access_token, access_exp, new_refresh, new_refresh_exp


def verify_token(token: str, expected_type: str) -> dict:
    from .security import decode_token

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid.")

    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid.")

    return payload


def revoke_refresh_token(db: Session, token: str) -> None:
    try:
        payload = verify_token(token, expected_type="refresh")
    except HTTPException:
        return
    record = db.scalar(select(AuthRefreshToken).where(AuthRefreshToken.jti == payload["jti"]))
    if record:
        record.revoked_at = datetime.now(timezone.utc)
        db.flush()


def _record_audit(
    db: Session,
    action: str,
    actor: Optional[AuthUser],
    subject: Optional[AuthUser],
    details: Optional[dict] = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        AuthAuditLog(
            user_id=subject.id if subject else None,
            actor_id=actor.id if actor else None,
            action=action,
            details=details,
            ip_address=ip,
            user_agent=user_agent,
        )
    )
    db.flush()


def start_oauth_flow(db: Session, redirect_to: str | None = None, redirect_uri: str | None = None) -> OAuthStartResponse:
    if get_auth_mode() == AuthMode.DEFAULT and not bootstrap_required(db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="OAuth login disabled.")

    state = generate_state()
    verifier = generate_code_verifier()
    challenge = create_pkce_challenge(verifier)

    db.add(
        OAuthState(
            state=state,
            code_challenge=challenge,
            code_verifier=verifier,
            redirect_to=redirect_to,
        )
    )
    db.flush()

    url = build_authorization_url(state=state, code_challenge=challenge, redirect_uri=redirect_uri)
    return OAuthStartResponse(authorization_url=url, state=state)


def complete_oauth_flow(db: Session, payload: OAuthCallbackRequest) -> AuthUser:
    record = db.get(OAuthState, payload.state)
    if not record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired.")

    try:
        token_payload = exchange_code_for_token(payload.code, record.code_verifier, payload.redirect_uri)
    finally:
        db.delete(record)
        db.flush()

    id_token = token_payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing ID token in OAuth response.")

    claims = verify_id_token(id_token)
    email = claims.get("email") or claims.get("preferred_username")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Microsoft did not return an email address.")

    email = email.lower()
    user = db.scalar(select(AuthUser).where(func.lower(AuthUser.email) == email))

    if not user:
        if bootstrap_required(db):
            user = AuthUser(
                email=email,
                username=claims.get("name"),
                auth_provider=AuthProvider.O365,
                password_hash=None,
                role=AuthRole.ADMIN,
                is_approved=True,
                is_active=True,
                email_verified=True,
                source="oauth",
                azure_tenant_id=claims.get("tid"),
                azure_oid=claims.get("oid"),
                identity_metadata=claims,
            )
            db.add(user)
            db.flush()
            _record_audit(db, action="bootstrap_oauth", actor=user, subject=user)
        else:
            _ensure_email_allowed(db, email)
            user = AuthUser(
                email=email,
                username=claims.get("name"),
                auth_provider=AuthProvider.O365,
                password_hash=None,
                role=AuthRole.USER if get_auth_config().feature_role_user_enabled else AuthRole.ADMIN,
                is_approved=False,
                is_active=True,
                email_verified=True,
                source="oauth",
                azure_tenant_id=claims.get("tid"),
                azure_oid=claims.get("oid"),
                identity_metadata=claims,
            )
            db.add(user)
            db.flush()
            _record_audit(db, action="oauth_pending_approval", actor=user, subject=user)
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Account pending approval.",
            )
    else:
        if not user.is_active or not user.is_approved:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account pending approval.",
            )
        user.azure_oid = claims.get("oid")
        user.azure_tenant_id = claims.get("tid")
        user.identity_metadata = claims
        user.auth_provider = AuthProvider.O365

    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    _record_audit(db, action="login_success", actor=user, subject=user, details={"provider": "o365"})
    return user


def forgot_password(db: Session, payload: ForgotPasswordRequest) -> str:
    user = db.scalar(select(AuthUser).where(func.lower(AuthUser.email) == payload.email.lower()))
    if not user or user.auth_provider != AuthProvider.LOCAL:
        return ""

    token = secrets.token_urlsafe(48)
    record = PasswordResetToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(record)
    db.flush()
    _record_audit(db, action="password_reset_requested", actor=user, subject=user)
    return token


def reset_password(db: Session, payload: ResetPasswordRequest) -> None:
    record = db.get(PasswordResetToken, payload.token)
    if not record or record.consumed_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token invalid.")
    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token expired.")

    user = db.get(AuthUser, record.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account no longer exists.")
    user.password_hash = hash_password(payload.password)
    user.email_verified = True
    record.consumed_at = datetime.now(timezone.utc)
    db.flush()
    _record_audit(db, action="password_reset", actor=user, subject=user)


def verify_email(db: Session, token: str) -> None:
    record = db.get(EmailVerificationToken, token)
    if not record or record.consumed_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token invalid.")
    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token expired.")

    user = db.get(AuthUser, record.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account no longer exists.")

    user.email_verified = True
    user.is_active = True
    record.consumed_at = datetime.now(timezone.utc)
    db.flush()
    _record_audit(db, action="email_verified", actor=None, subject=user)


def list_admin_users(db: Session) -> list[AuthUserOut]:
    records = db.scalars(select(AuthUser).order_by(AuthUser.created_at.desc())).all()
    return [AuthUserOut.model_validate(record) for record in records]


def update_admin_user(db: Session, user_id: str, payload: AdminUserUpdateRequest, actor: AuthUser) -> AuthUser:
    user = db.get(AuthUser, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if payload.is_approved is not None:
        user.is_approved = payload.is_approved
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role is not None:
        user.role = payload.role

    db.flush()
    _record_audit(
        db,
        action="admin_user_update",
        actor=actor,
        subject=user,
        details=payload.model_dump(exclude_none=True),
    )
    return user


def sync_users_from_emails(db: Session, payload: UserSyncRequest, actor: AuthUser) -> int:
    emails = {email.lower() for email in payload.emails}
    # include existing analytics users if manual list empty
    if not emails:
        analytics_emails = db.scalars(
            select(AnalyticsUser.email).where(AnalyticsUser.email.isnot(None))
        ).all()
        emails.update(email.lower() for email in analytics_emails if email)

    created = 0
    for email in emails:
        if not email:
            continue
        user = db.scalar(select(AuthUser).where(func.lower(AuthUser.email) == email))
        if user:
            continue
        db.add(
            AuthUser(
                email=email,
                auth_provider=AuthProvider.LOCAL,
                is_approved=False,
                is_active=True,
                email_verified=False,
                role=AuthRole.USER if get_auth_config().feature_role_user_enabled else AuthRole.ADMIN,
                source=payload.source,
            )
        )
        created += 1
    db.flush()
    _record_audit(
        db,
        action="sync_users",
        actor=actor,
        subject=None,
        details={"created": created, "source": payload.source},
    )
    return created


def list_audit_logs(db: Session, limit: int = 200) -> list[AuditEntry]:
    records = db.scalars(
        select(AuthAuditLog).order_by(AuthAuditLog.created_at.desc()).limit(limit)
    ).all()
    return [
        AuditEntry(
            id=record.id,
            action=record.action,
            actor_id=record.actor_id,
            user_id=record.user_id,
            details=record.details,
            created_at=record.created_at,
        )
        for record in records
    ]
