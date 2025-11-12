from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .config import get_auth_config
from .dependencies import get_current_user, get_db, require_admin
from .models import AuthUser
from .schemas import (
    AdminUserListResponse,
    AdminUserUpdateRequest,
    AuditLogResponse,
    AuthUserOut,
    BootstrapRequest,
    BootstrapStatus,
    EmailVerificationRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ModeResponse,
    OAuthCallbackRequest,
    OAuthStartResponse,
    RegisterCompleteRequest,
    RegisterStartRequest,
    RegisterStartResponse,
    ResetPasswordRequest,
    TokenPair,
    UserSyncRequest,
)
from .security import REFRESH_COOKIE_NAME, SESSION_COOKIE_NAME
from .service import (
    authenticate_local_user,
    bootstrap_required,
    complete_oauth_flow,
    complete_registration_password,
    create_bootstrap_admin,
    forgot_password,
    issue_tokens,
    list_admin_users,
    list_audit_logs,
    refresh_session,
    revoke_refresh_token,
    start_oauth_flow,
    start_registration,
    sync_users_from_emails,
    update_admin_user,
    verify_email,
)

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])
setup_router = APIRouter(prefix="/api", tags=["setup"])


def _set_session_cookies(response: Response, access: str, access_exp: datetime, refresh: str, refresh_exp: datetime) -> None:
    cfg = get_auth_config()
    cookie_kwargs = {
        "httponly": True,
        "secure": cfg.session_cookie_secure,
        "samesite": cfg.session_cookie_same_site,
        "path": "/",
    }
    if cfg.session_cookie_domain:
        cookie_kwargs["domain"] = cfg.session_cookie_domain

    now = datetime.now(timezone.utc)
    access_ttl = max(0, int((access_exp - now).total_seconds()))
    refresh_ttl = max(0, int((refresh_exp - now).total_seconds()))

    response.set_cookie(
        SESSION_COOKIE_NAME,
        access,
        max_age=access_ttl,
        **cookie_kwargs,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh,
        max_age=refresh_ttl,
        **cookie_kwargs,
    )


def _clear_session_cookies(response: Response) -> None:
    cfg = get_auth_config()
    cookie_kwargs = {
        "httponly": True,
        "secure": cfg.session_cookie_secure,
        "samesite": cfg.session_cookie_same_site,
        "path": "/",
        "max_age": 0,
    }
    if cfg.session_cookie_domain:
        cookie_kwargs["domain"] = cfg.session_cookie_domain
    response.set_cookie(SESSION_COOKIE_NAME, "", **cookie_kwargs)
    response.set_cookie(REFRESH_COOKIE_NAME, "", **cookie_kwargs)


@setup_router.get("/setup/status", response_model=BootstrapStatus)
def get_setup_status(db: Session = Depends(get_db)) -> BootstrapStatus:
    return BootstrapStatus(needs_setup=bootstrap_required(db), auth_mode=get_auth_config().auth_mode)


@setup_router.post("/setup", response_model=TokenPair)
def perform_bootstrap(payload: BootstrapRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    if not bootstrap_required(db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Setup already completed.")
    user = create_bootstrap_admin(db, payload)
    access, access_exp, refresh, refresh_exp = issue_tokens(db, user, remember_me=True)
    _set_session_cookies(response, access, access_exp, refresh, refresh_exp)
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=int((access_exp - datetime.now(timezone.utc)).total_seconds()))


@auth_router.get("/mode", response_model=ModeResponse)
def get_mode() -> ModeResponse:
    return ModeResponse(auth_mode=get_auth_config().auth_mode)


@auth_router.post("/register/start", response_model=RegisterStartResponse)
def register_start(payload: RegisterStartRequest, response: Response, db: Session = Depends(get_db)) -> RegisterStartResponse:
    return start_registration(db, payload)


@auth_router.post("/register/complete", response_model=TokenPair)
def register_complete(payload: RegisterCompleteRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    user = complete_registration_password(db, payload)
    access, access_exp, refresh, refresh_exp = issue_tokens(db, user)
    _set_session_cookies(response, access, access_exp, refresh, refresh_exp)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=int((access_exp - datetime.now(timezone.utc)).total_seconds()),
    )


@auth_router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    if bootstrap_required(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System requires initial setup.",
        )
    user = authenticate_local_user(db, payload)
    access, access_exp, refresh, refresh_exp = issue_tokens(db, user, remember_me=payload.remember_me)
    _set_session_cookies(response, access, access_exp, refresh, refresh_exp)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=int((access_exp - datetime.now(timezone.utc)).total_seconds()),
    )


@auth_router.post("/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)) -> dict:
    refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh:
        revoke_refresh_token(db, refresh)
    _clear_session_cookies(response)
    return {"status": "ok"}


@auth_router.post("/token/refresh", response_model=TokenPair)
def refresh_token(response: Response, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing.")
    user, access, access_exp, refresh, refresh_exp = refresh_session(db, token)
    _set_session_cookies(response, access, access_exp, refresh, refresh_exp)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=int((access_exp - datetime.now(timezone.utc)).total_seconds()),
    )


@auth_router.post("/password/forgot")
def forgot_password_route(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    token = forgot_password(db, payload)
    # Intentionally avoid leaking whether the email exists. Token is returned only for
    # environments wired to send email; otherwise callers must monitor server logs.
    return {"status": "ok"}


@auth_router.post("/password/reset")
def reset_password_route(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    reset_password(db, payload)
    return {"status": "ok"}


@auth_router.post("/email/verify")
def verify_email_route(payload: EmailVerificationRequest, db: Session = Depends(get_db)) -> dict:
    verify_email(db, payload.token)
    return {"status": "ok"}


@auth_router.get("/oauth/start", response_model=OAuthStartResponse)
def oauth_start(
    redirect_to: Optional[str] = Query(default=None),
    redirect_uri: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> OAuthStartResponse:
    return start_oauth_flow(db, redirect_to=redirect_to, redirect_uri=redirect_uri)


@auth_router.post("/oauth/callback", response_model=TokenPair)
def oauth_callback(payload: OAuthCallbackRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = complete_oauth_flow(db, payload)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_202_ACCEPTED:
            _clear_session_cookies(response)
        raise
    access, access_exp, refresh, refresh_exp = issue_tokens(db, user)
    _set_session_cookies(response, access, access_exp, refresh, refresh_exp)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=int((access_exp - datetime.now(timezone.utc)).total_seconds()),
    )


@auth_router.get("/me", response_model=AuthUserOut)
def me(user: AuthUser = Depends(get_current_user)) -> AuthUserOut:
    return AuthUserOut.model_validate(user)


@admin_router.get("/users", response_model=AdminUserListResponse)
def list_users(_: AuthUser = Depends(require_admin), db: Session = Depends(get_db)) -> AdminUserListResponse:
    return AdminUserListResponse(users=list_admin_users(db))


@admin_router.patch("/users/{user_id}", response_model=AuthUserOut)
def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    current: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AuthUserOut:
    user = update_admin_user(db, user_id, payload, actor=current)
    return AuthUserOut.model_validate(user)


@admin_router.post("/users/sync")
def sync_users(
    payload: UserSyncRequest,
    current: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    created = sync_users_from_emails(db, payload, actor=current)
    return {"created": created}


@admin_router.get("/audit", response_model=AuditLogResponse)
def audit_logs(_: AuthUser = Depends(require_admin), db: Session = Depends(get_db)) -> AuditLogResponse:
    return AuditLogResponse(entries=list_audit_logs(db))
