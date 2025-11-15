import os
import sys
from pathlib import Path

import pytest

# Ensure project root importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("DB_NAME", "test_challenge_attempts.sqlite")

from backend.app.db.session import DATA_DIR, Base, engine, get_engine_info  # noqa: E402
from backend.app.services.data_store import (  # noqa: E402
    load_challenge_attempts,
    persist_challenge_attempts,
)
from backend.app.services.mission_analyzer import MissionAnalyzer  # noqa: E402


def _cleanup_db() -> None:
    db_name = os.environ.get("DB_NAME", "test_challenge_attempts.sqlite")
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


def _build_sample_record():
    payload = {
        "attempt_id": "chat-sample::maip-challenge::mission::1",
        "chat_id": "chat-sample",
        "chat_num": 1,
        "user_id": "user-123",
        "title": "Week 1 Run",
        "model": "maip---week-1---challenge-1",
        "mission_info": {"mission_id": "Week 1 - Challenge 1", "week": 1},
        "messages": [
            {"role": "user", "content": "start", "timestamp": 1},
            {"role": "assistant", "content": "congratulations", "timestamp": 2},
        ],
        "message_count": 2,
        "user_message_count": 1,
        "created_at": 1,
        "updated_at": 2,
        "completed": True,
    }
    record = {
        "id": payload["attempt_id"],
        "chat_id": payload["chat_id"],
        "chat_index": payload["chat_num"],
        "user_id": payload["user_id"],
        "mission_id": payload["mission_info"]["mission_id"],
        "mission_model": payload["model"],
        "mission_week": str(payload["mission_info"]["week"]),
        "completed": payload["completed"],
        "message_count": payload["message_count"],
        "user_message_count": payload["user_message_count"],
        "started_at": payload["created_at"],
        "updated_at_raw": payload["updated_at"],
        "payload": payload,
    }
    return record, payload


def test_persist_challenge_attempts_round_trip():
    record, payload = _build_sample_record()
    persist_challenge_attempts([record], mode="truncate")

    attempts = load_challenge_attempts()
    assert len(attempts) == 1
    entry = attempts[0]
    assert entry["attempt_id"] == payload["attempt_id"]
    assert entry["mission_info"]["mission_id"] == payload["mission_info"]["mission_id"]
    assert entry["messages"][0]["content"] == "start"


def test_mission_analyzer_loads_cached_attempts():
    record, payload = _build_sample_record()
    persist_challenge_attempts([record], mode="truncate")
    attempts = load_challenge_attempts()

    analyzer = MissionAnalyzer(
        json_file=None,
        data=[],
        user_names={"user-123": "Agent Smith"},
        model_lookup={"maip---week-1---challenge-1": "Week 1 Challenge"},
        mission_model_aliases={"maip---week-1---challenge-1"},
        model_alias_to_primary={"maip---week-1---challenge-1": "maip---week-1---challenge-1"},
        week_mapping={"maip---week-1---challenge-1": "1"},
        points_mapping={"maip---week-1---challenge-1": 15},
        difficulty_mapping={"maip---week-1---challenge-1": "Easy"},
        verbose=False,
    )

    analyzer.load_challenge_attempts(attempts)
    assert len(analyzer.mission_chats) == 1
    leaderboard = analyzer.get_leaderboard()
    assert leaderboard[0]["user_id"] == payload["user_id"]
    assert leaderboard[0]["completions"] == 1
