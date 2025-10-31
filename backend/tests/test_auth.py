import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("AUTH_MODE", "HYBRID")
os.environ.setdefault("OAUTH_TENANT_ID", "test-tenant")
os.environ.setdefault("OAUTH_CLIENT_ID", "test-client")
os.environ.setdefault("OAUTH_CLIENT_SECRET", "test-secret")
os.environ.setdefault("OAUTH_REDIRECT_URL", "http://testserver/auth/oauth/callback")

TEST_DB_NAME = "test_auth.sqlite"
os.environ["DB_NAME"] = TEST_DB_NAME

from backend.app.db.session import DATA_DIR, SessionLocal, get_engine_info  # noqa: E402
from backend.app.db.models import User  # noqa: E402
from backend.app.main import app  # noqa: E402


def _cleanup_db() -> None:
    path = DATA_DIR / TEST_DB_NAME
    if path.exists():
        path.unlink()
    get_engine_info.cache_clear()


@pytest.fixture(autouse=True)
def clean_database():
    _cleanup_db()
    yield
    _cleanup_db()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def seed_allowed_email(email: str) -> None:
    session = SessionLocal()
    try:
        session.add(
            User(
                id="seed-user",
                name="Seed User",
                email=email,
                data={},
            )
        )
        session.commit()
    finally:
        session.close()


def test_bootstrap_and_local_login_flow(client: TestClient) -> None:
    response = client.get("/api/setup/status")
    assert response.status_code == 200
    data = response.json()
    assert data["needs_setup"] is True

    response = client.post(
        "/api/setup",
        json={"email": "owner@example.com", "password": "SuperSecurePass123", "username": "Owner"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "Bearer"

    response = client.get("/dashboard")
    assert response.status_code == 200

    # Seed approved email for registration
    seed_allowed_email("agent@example.com")

    # Attempt to register second user (should require approval)
    response = client.post(
        "/api/auth/register",
        json={"email": "agent@example.com", "password": "AnotherSecurePass123"},
    )
    assert response.status_code == 202

    # Admin lists users and approves
    response = client.get("/api/admin/users")
    assert response.status_code == 200
    users = response.json()["users"]
    pending = next(user for user in users if user["email"] == "agent@example.com")

    response = client.patch(f"/api/admin/users/{pending['id']}", json={"is_approved": True})
    assert response.status_code == 200
    assert response.json()["is_approved"] is True

    # Login as approved user fails until password set via reset? We have password stored, so login should succeed
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/login",
        json={"email": "agent@example.com", "password": "AnotherSecurePass123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "agent@example.com"
