import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is importable when running tests outside the package
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("DB_NAME", "test_models.sqlite")

from backend.app.db.models import Model  # noqa: E402
from backend.app.db.session import (  # noqa: E402
    DATA_DIR,
    Base,
    SessionLocal,
    engine,
    get_engine_info,
)
from backend.app.services.data_store import persist_models  # noqa: E402


def _cleanup_db() -> None:
    db_name = os.environ.get("DB_NAME", "test_models.sqlite")
    path = DATA_DIR / db_name
    if path.exists():
        path.unlink()
    get_engine_info.cache_clear()


@pytest.fixture(autouse=True)
def clean_database():
    _cleanup_db()
    Base.metadata.create_all(bind=engine)
    yield
    _cleanup_db()


def test_persist_models_stores_maip_fields() -> None:
    record = {
        "id": "maip---week-1---challenge-1",
        "name": "Mission Week 1 - Challenge 1",
        "params": {
            "custom_params": {
                "maip_week": "Week 1",
                "maip_points_value": "150",
                "maip_difficulty_level": "Advanced",
            }
        },
    }

    rows = persist_models([record])
    assert rows == 1

    session = SessionLocal()
    try:
        stored = session.get(Model, record["id"])
        assert stored is not None
        assert stored.maip_week == "Week 1"
        assert stored.maip_points == 150
        assert stored.maip_difficulty == "Advanced"
    finally:
        session.close()

    updated_record = {
        "id": record["id"],
        "name": "Mission Week 1 - Challenge 1 (Updated)",
        "info": {
            "params": {
                "custom_params": {
                    "maip_week": 2,
                    "maip_points_value": 175,
                    "maip_difficulty_level": "Expert",
                }
            }
        },
    }

    rows = persist_models([updated_record])
    assert rows == 1

    session = SessionLocal()
    try:
        stored = session.get(Model, record["id"])
        assert stored is not None
        assert stored.name == updated_record["name"]
        assert stored.maip_week == "2"
        assert stored.maip_points == 175
        assert stored.maip_difficulty == "Expert"
        assert stored.data["id"] == record["id"]
    finally:
        session.close()
