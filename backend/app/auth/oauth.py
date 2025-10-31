from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
import jwt

from .config import get_auth_config

logger = logging.getLogger(__name__)


@dataclass
class _OidcCache:
    config: Dict[str, Any] | None = None
    config_fetched_at: float = 0.0
    jwks: Dict[str, Any] | None = None
    jwks_fetched_at: float = 0.0


_CACHE = _OidcCache()
_CACHE_TTL = 60 * 60  # 1 hour


def _ensure_oauth_config() -> None:
    cfg = get_auth_config()
    if not cfg.oauth_tenant_id or not cfg.oauth_client_id or not cfg.oauth_client_secret:
        raise RuntimeError("Office 365 OAuth is not configured. Set OAUTH_TENANT_ID, OAUTH_CLIENT_ID, and OAUTH_CLIENT_SECRET.")


def _openid_configuration_url() -> str:
    cfg = get_auth_config()
    tenant = cfg.oauth_tenant_id or "common"
    return f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"


def _fetch_openid_configuration() -> Dict[str, Any]:
    now = time.time()
    if _CACHE.config and now - _CACHE.config_fetched_at < _CACHE_TTL:
        return _CACHE.config

    url = _openid_configuration_url()
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()

    _CACHE.config = data
    _CACHE.config_fetched_at = now
    return data


def _fetch_jwks() -> Dict[str, Any]:
    now = time.time()
    if _CACHE.jwks and now - _CACHE.jwks_fetched_at < _CACHE_TTL:
        return _CACHE.jwks

    config = _fetch_openid_configuration()
    jwks_uri = config.get("jwks_uri")
    if not jwks_uri:
        raise RuntimeError("Azure OpenID configuration is missing jwks_uri.")

    with httpx.Client(timeout=10.0) as client:
        response = client.get(jwks_uri)
        response.raise_for_status()
        data = response.json()

    _CACHE.jwks = data
    _CACHE.jwks_fetched_at = now
    return data


def build_authorization_url(state: str, code_challenge: str, redirect_uri: str | None = None) -> str:
    _ensure_oauth_config()
    config = _fetch_openid_configuration()
    authorize_url = config.get("authorization_endpoint")
    if not authorize_url:
        raise RuntimeError("Azure OpenID configuration missing authorization_endpoint.")

    cfg = get_auth_config()
    scopes = cfg.oauth_scopes or "openid profile email offline_access"
    redirect = redirect_uri or cfg.oauth_redirect_url
    if not redirect:
        raise RuntimeError("Missing OAUTH_REDIRECT_URL.")

    params = {
        "client_id": cfg.oauth_client_id,
        "response_type": "code",
        "redirect_uri": redirect,
        "response_mode": "query",
        "scope": scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }

    query = httpx.QueryParams(params)
    return f"{authorize_url}?{query}"


def exchange_code_for_token(code: str, code_verifier: str, redirect_uri: str) -> Dict[str, Any]:
    _ensure_oauth_config()
    config = _fetch_openid_configuration()
    token_endpoint = config.get("token_endpoint")
    if not token_endpoint:
        raise RuntimeError("Azure OpenID configuration missing token_endpoint.")

    cfg = get_auth_config()
    data = {
        "client_id": cfg.oauth_client_id,
        "client_secret": cfg.oauth_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(token_endpoint, data=data)

    if response.status_code >= 400:
        logger.warning("OAuth token exchange failed: %s - %s", response.status_code, response.text)
        response.raise_for_status()

    return response.json()


def verify_id_token(id_token: str) -> Dict[str, Any]:
    _ensure_oauth_config()
    cfg = get_auth_config()
    unverified_header = jwt.get_unverified_header(id_token)
    key_id = unverified_header.get("kid")

    jwks = _fetch_jwks()
    keys = jwks.get("keys", [])

    key = next((k for k in keys if k.get("kid") == key_id), None)
    if not key:
        raise RuntimeError("Unable to verify ID token: signing key not found.")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    issuer = _fetch_openid_configuration().get("issuer")

    return jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=cfg.oauth_client_id,
        issuer=issuer,
    )
