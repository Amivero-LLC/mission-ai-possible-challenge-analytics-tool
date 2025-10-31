from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from .config import get_auth_config

password_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)


SESSION_COOKIE_NAME = "maip_session"
REFRESH_COOKIE_NAME = "maip_refresh"


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    return password_context.verify(password, password_hash)


def _create_token(payload: Dict[str, Any], expires_delta: timedelta) -> tuple[str, datetime]:
    config = get_auth_config()
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    token = jwt.encode(
        {
            **payload,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
        },
        config.session_secret,
        algorithm="HS256",
    )
    return token, expire


def create_access_token(subject: str, role: str, approved: bool, active: bool, email_verified: bool) -> tuple[str, datetime]:
    payload = {
        "sub": subject,
        "type": "access",
        "role": role,
        "approved": approved,
        "active": active,
        "email_verified": email_verified,
    }
    ttl = timedelta(minutes=get_auth_config().access_token_ttl_minutes)
    return _create_token(payload, ttl)


def create_refresh_token(subject: str, jti: str) -> tuple[str, datetime]:
    payload = {
        "sub": subject,
        "type": "refresh",
        "jti": jti,
    }
    ttl = timedelta(days=get_auth_config().refresh_token_ttl_days)
    return _create_token(payload, ttl)


def decode_token(token: str) -> dict[str, Any]:
    config = get_auth_config()
    return jwt.decode(token, config.session_secret, algorithms=["HS256"])


def generate_token_id() -> str:
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def generate_code_verifier() -> str:
    verifier = secrets.token_urlsafe(64)
    return verifier[:128]


def create_pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*" * (len(local) - 1)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"
