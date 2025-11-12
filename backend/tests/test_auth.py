import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("AUTH_MODE", "HYBRID")
os.environ.setdefault("OAUTH_TENANT_ID", "test-tenant")
os.environ.setdefault("OAUTH_CLIENT_ID", "test-client")
os.environ.setdefault("OAUTH_CLIENT_SECRET", "test-secret")
os.environ.setdefault("OAUTH_REDIRECT_URL", "http://testserver/auth/oauth/callback")

TEST_DB_NAME = "test_auth.sqlite"
os.environ["DB_NAME"] = TEST_DB_NAME

from backend.app.db.session import DATA_DIR, SessionLocal, engine, get_engine_info  # noqa: E402
from backend.app.db.models import User  # noqa: E402
from backend.app.main import app  # noqa: E402


def _cleanup_db() -> None:
    try:
        engine.dispose()
    except Exception:
        pass
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
                id=f"seed-user-{uuid.uuid4().hex}",
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

    # Seed approved email for registration
    seed_allowed_email("agent@example.com")

    # Attempt to register second user (should require approval)
    response = client.post(
        "/api/auth/register/start",
        json={"email": "agent@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"

    # Admin lists users and approves
    response = client.get("/api/admin/users")
    assert response.status_code == 200
    users = response.json()["users"]
    pending = next(user for user in users if user["email"] == "agent@example.com")

    response = client.patch(f"/api/admin/users/{pending['id']}", json={"is_approved": True})
    assert response.status_code == 200
    assert response.json()["is_approved"] is True

    completion = client.post(
        "/api/auth/register/complete",
        json={"email": "agent@example.com", "password": "AnotherSecurePass123"},
    )
    assert completion.status_code == 200

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


def test_register_prompts_password_setup_when_missing_password(client: TestClient) -> None:
    client.post(
        "/api/setup",
        json={"email": "owner@example.com", "password": "SuperSecurePass123", "username": "Owner"},
    )

    seed_allowed_email("preapproved@example.com")

    sync_response = client.post(
        "/api/admin/users/sync",
        json={"emails": ["preapproved@example.com"]},
    )
    assert sync_response.status_code == 200

    users = client.get("/api/admin/users").json()["users"]
    pending = next(user for user in users if user["email"] == "preapproved@example.com")

    approve_response = client.patch(
        f"/api/admin/users/{pending['id']}",
        json={"is_approved": True},
    )
    assert approve_response.status_code == 200

    response = client.post(
        "/api/auth/register/start",
        json={"email": "preapproved@example.com"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "password_setup_required"

    completion = client.post(
        "/api/auth/register/complete",
        json={"email": "preapproved@example.com", "password": "AnotherSecurePass123"},
    )
    assert completion.status_code == 200

    follow_up = client.post(
        "/api/auth/register/start",
        json={"email": "preapproved@example.com"},
    )
    assert follow_up.status_code == 200
    assert follow_up.json()["status"] == "password_reset_required"
