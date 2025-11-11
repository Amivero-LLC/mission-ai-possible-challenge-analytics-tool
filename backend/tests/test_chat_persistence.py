import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is importable when running tests outside the package
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("DB_NAME", "test_chats.sqlite")

from backend.app.db.models import Chat, User  # noqa: E402
from backend.app.db.session import (  # noqa: E402
    DATA_DIR,
    Base,
    SessionLocal,
    engine,
    get_engine_info,
)
from backend.app.services.data_store import persist_chats, persist_users  # noqa: E402


def _cleanup_db() -> None:
    db_name = os.environ.get("DB_NAME", "test_chats.sqlite")
    path = DATA_DIR / db_name
    engine.dispose()
    if path.exists():
        path.unlink()
    get_engine_info.cache_clear()


@pytest.fixture(autouse=True)
def clean_database():
    _cleanup_db()
    Base.metadata.create_all(bind=engine)
    yield
    _cleanup_db()


def test_persist_chats_creates_placeholder_user() -> None:
    payload = {
        "id": "chat-placeholder",
        "user_id": "user-missing",
        "title": "Placeholder creation test",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "chat": {
            "models": ["demo-model"],
            "messages": [],
        },
    }

    rows = persist_chats([payload])
    assert rows == 1

    session = SessionLocal()
    try:
        stored_chat = session.get(Chat, payload["id"])
        assert stored_chat is not None
        assert stored_chat.user_id == payload["user_id"]

        stored_user = session.get(User, payload["user_id"])
        assert stored_user is not None
        assert stored_user.data["id"] == payload["user_id"]
        assert stored_user.data["_source"] == "chat_placeholder"
    finally:
        session.close()


def test_persist_users_overrides_placeholder_data() -> None:
    chat_payload = {
        "id": "chat-with-real-user",
        "user_id": "user-real",
        "title": "Needs user info",
        "created_at": "2025-01-02T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
        "chat": {
            "models": ["demo-model"],
            "messages": [],
        },
    }

    persist_chats([chat_payload])

    user_payload = [
        {
            "id": "user-real",
            "name": "Mission Specialist",
            "email": "specialist@example.com",
        }
    ]

    persist_users(user_payload)

    session = SessionLocal()
    try:
        stored_user = session.get(User, "user-real")
        assert stored_user is not None
        assert stored_user.name == "Mission Specialist"
        assert stored_user.email == "specialist@example.com"
        assert stored_user.data["name"] == "Mission Specialist"
    finally:
        session.close()
