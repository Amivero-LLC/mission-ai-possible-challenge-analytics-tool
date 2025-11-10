from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import AuthMode


class AuthConfig(BaseSettings):
    auth_mode: AuthMode = AuthMode.DEFAULT
    session_secret: str = "change-me"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_days: int = 14
    session_cookie_secure: bool = False
    session_cookie_domain: Optional[str] = None
    session_cookie_same_site: str = "strict"
    oauth_tenant_id: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_redirect_url: Optional[str] = None
    oauth_scopes: Optional[str] = None
    feature_role_user_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_use_tls: bool = True

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @field_validator("oauth_scopes")
    def _normalize_scopes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return " ".join(scope.strip() for scope in value.replace(",", " ").split())


@lru_cache()
def get_auth_config() -> AuthConfig:
    # Provide a deterministic secret in local/dev environments when the variable is unset.
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        os.environ.setdefault("SESSION_SECRET", "development-secret")
    return AuthConfig()
