import csv
import io
import os
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SESSION_SECRET", "test-secret")
TEST_DB_NAME = "test_campaign.sqlite"
os.environ["DB_NAME"] = TEST_DB_NAME

if "jwt" not in sys.modules:
    jwt_stub = types.SimpleNamespace(
        encode=lambda payload, key, algorithm=None: "token",
        decode=lambda token, key, algorithms=None: {},
    )
    sys.modules["jwt"] = jwt_stub

from backend.app.campaign.service import get_campaign_summary, reload_submissions  # noqa: E402
from backend.app.campaign.status_rules import CompletionRecord, SubmissionRecord  # noqa: E402
from backend.app.db.models import Model, SubmittedActivity, User  # noqa: E402
from backend.app.db.session import DATA_DIR, Base, SessionLocal, engine, get_engine_info  # noqa: E402

campaign_service = sys.modules["backend.app.campaign.service"]

CSV_COLUMNS = [
    "UserID",
    "FirstName",
    "LastName",
    "Email",
    "ActivityID",
    "ActivityType",
    "ActivityStatus",
    "PointsAwarded",
    "WeekID",
    "Attachments",
    "UseCaseTitle",
    "UseCaseType",
    "UseCaseStory",
    "UseCaseHow",
    "UseCaseValue",
    "TrainingTitle",
    "TrainingReflection",
    "TrainingDuration",
    "TrainingLink",
    "DemoTitle",
    "DemoDescription",
    "MissionChallengeWeek",
    "MissionChallenge",
    "MissionChallengeResponse",
    "QuizTopic",
    "QuizScore",
    "QuizCompletionDate",
    "Created",
]


def _cleanup_db() -> None:
    path = DATA_DIR / TEST_DB_NAME
    if path.exists():
        path.unlink()
    get_engine_info.cache_clear()


def _build_csv(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for row in rows:
        full_row = {column: "" for column in CSV_COLUMNS}
        full_row.update(row)
        writer.writerow(full_row)
    return buffer.getvalue().encode("utf-8")


def _base_row(**overrides: str) -> dict[str, str]:
    row = {
        "UserID": "1",
        "FirstName": "Test",
        "LastName": "User",
        "Email": "test@example.com",
        "ActivityID": "3",
        "ActivityType": "Missions & Challenges",
        "ActivityStatus": "Review Completed",
        "PointsAwarded": "10",
        "WeekID": "1",
        "Created": "10/13/2025 11:38 AM",
    }
    row.update(overrides)
    return row


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _count_submissions(session) -> int:
    return session.scalar(select(func.count()).select_from(SubmittedActivity)) or 0


def test_ingestion_truncates_and_counts(session):
    first_csv = _build_csv([
        _base_row(UserID="10", Email="first@example.com", PointsAwarded="20"),
    ])
    reload_submissions(first_csv, session)
    session.commit()

    second_csv = _build_csv([
        _base_row(UserID="11", Email="second@example.com", PointsAwarded="30"),
        _base_row(UserID="12", Email="third@example.com", PointsAwarded="40", WeekID="2"),
    ])
    summary = reload_submissions(second_csv, session)
    session.commit()

    assert summary.rows_inserted == 2
    assert _count_submissions(session) == 2
    campaign_summary = get_campaign_summary(session, week=None, user_filter=None)
    assert campaign_summary.last_upload_at is not None


def test_user_upsert_sets_sharepoint(session):
    existing = User(
        id="legacy-user",
        name=None,
        email="agent@example.com",
        data={},
        sharepoint_user_id=None,
        total_points=0,
        current_rank=0,
    )
    session.add(existing)
    session.commit()

    csv_data = _build_csv([
        _base_row(UserID="21", Email="agent@example.com", PointsAwarded="15"),
        _base_row(UserID="22", Email="newuser@example.com", PointsAwarded="25"),
    ])
    summary = reload_submissions(csv_data, session)
    session.commit()

    updated = session.get(User, "legacy-user")
    assert updated.sharepoint_user_id == 21
    assert summary.users_updated == 1
    assert summary.users_created == 1


def test_points_only_include_review_completed(session):
    csv_data = _build_csv([
        _base_row(UserID="31", Email="points@example.com", PointsAwarded="100", ActivityStatus="Review Completed"),
        _base_row(UserID="31", Email="points@example.com", PointsAwarded="500", ActivityStatus="Pending Review"),
    ])
    reload_submissions(csv_data, session)
    session.commit()

    user = session.execute(
        select(User).where(func.lower(User.email) == "points@example.com")
    ).scalar_one()
    assert float(user.total_points) == 100.0


def test_rank_thresholds(session):
    rows = [
        _base_row(UserID="41", Email="rank0@example.com", PointsAwarded="149"),
        _base_row(UserID="42", Email="rank1a@example.com", PointsAwarded="150"),
        _base_row(UserID="43", Email="rank1b@example.com", PointsAwarded="299"),
        _base_row(UserID="44", Email="rank2@example.com", PointsAwarded="300"),
    ]
    reload_submissions(_build_csv(rows), session)
    session.commit()

    ranks = {
        user.email: user.current_rank
        for user in session.execute(select(User).where(User.email.in_([row["Email"] for row in rows]))).scalars()
    }
    assert ranks["rank0@example.com"] == 0
    assert ranks["rank1a@example.com"] == 1
    assert ranks["rank1b@example.com"] == 1
    assert ranks["rank2@example.com"] == 2


def test_mission_mapping_links_models(session):
    session.add(
        Model(
            id="intel-guardian",
            name="Intel Guardian",
            data={},
            maip_week="1",
            maip_points=20,
        )
    )
    session.commit()

    csv_data = _build_csv([
        _base_row(
            UserID="55",
            Email="mission@example.com",
            PointsAwarded="20",
            MissionChallengeWeek="Week 1",
            MissionChallenge="Mission: Intel Guardian (Medium Difficulty)",
        )
    ])
    summary = reload_submissions(csv_data, session)
    session.commit()

    linked = session.execute(select(SubmittedActivity)).scalar_one()
    assert linked.mission_model_id == "intel-guardian"
    assert summary.missions_linked == 1


def test_mission_mapping_prefers_matching_week(session):
    session.add_all([
        Model(id="prompt-week-1", name="Prompt Qualification", data={}, maip_week="1", maip_points=15),
        Model(id="prompt-week-2", name="Prompt Qualification", data={}, maip_week="2", maip_points=25),
    ])
    session.commit()

    csv_data = _build_csv([
        _base_row(
            UserID="61",
            Email="weekmatch@example.com",
            PointsAwarded="30",
            WeekID="2",
            MissionChallenge="Week 2 - Prompt Qualification (Easy Difficulty)",
        )
    ])
    reload_submissions(csv_data, session)
    session.commit()

    linked = session.execute(select(SubmittedActivity)).scalar_one()
    assert linked.mission_model_id == "prompt-week-2"


def test_mission_mapping_requires_week_alignment(session):
    session.add(
        Model(id="prompt-week-1", name="Prompt Qualification", data={}, maip_week="1", maip_points=15)
    )
    session.commit()

    csv_data = _build_csv([
        _base_row(
            UserID="62",
            Email="weekmismatch@example.com",
            PointsAwarded="30",
            WeekID="2",
            MissionChallenge="Week 2 - Prompt Qualification (Easy)",
        )
    ])
    reload_submissions(csv_data, session)
    session.commit()

    linked = session.execute(select(SubmittedActivity)).scalar_one()
    assert linked.mission_model_id is None


def test_mission_mapping_handles_challenge_suffix(session):
    session.add(
        Model(id="seeds-week-2", name="Week 2 - Seeds of Bias (Hard)", data={}, maip_week="2", maip_points=30)
    )
    session.commit()

    csv_data = _build_csv([
        _base_row(
            UserID="63",
            Email="seedbias@example.com",
            PointsAwarded="30",
            WeekID="2",
            MissionChallenge="Mission: Seeds of Bias Challenge (Hard Difficulty)",
        )
    ])
    reload_submissions(csv_data, session)
    session.commit()

    linked = session.execute(select(SubmittedActivity)).scalar_one()
    assert linked.mission_model_id == "seeds-week-2"


def test_duplicate_user_ids_raise_error(session):
    csv_data = _build_csv([
        _base_row(UserID="1", Email="dup@example.com"),
        _base_row(UserID="2", Email="dup@example.com"),
    ])
    with pytest.raises(HTTPException) as exc:
        reload_submissions(csv_data, session)

    assert exc.value.status_code == 400
    assert "dup@example.com" in exc.value.detail


def test_campaign_status_missing_credit(session, monkeypatch):
    csv_data = _build_csv([
        _base_row(UserID="60", Email="status@example.com", PointsAwarded="25"),
    ])
    reload_submissions(csv_data, session)
    session.commit()

    def fake_status_sources(_session):
        return (
            {
                "status@example.com": {
                    "intel guardian": CompletionRecord(
                        display_name="Intel Guardian",
                        normalized_name="intel guardian",
                        count=1,
                    )
                }
            },
            {"status@example.com": []},
        )

    monkeypatch.setattr(campaign_service, "_prepare_status_sources", fake_status_sources)

    summary = get_campaign_summary(session, week=None, user_filter=None)
    assert summary.rows
    assert summary.rows[0].statusIndicators
    assert summary.rows[0].statusIndicators[0].code == "missing-credit"


def test_campaign_status_points_mismatch(session, monkeypatch):
    csv_data = _build_csv([
        _base_row(UserID="70", Email="mismatch@example.com", PointsAwarded="30"),
    ])
    reload_submissions(csv_data, session)
    session.commit()

    def fake_status_sources(_session):
        return (
            {},
            {
                "mismatch@example.com": [
                    SubmissionRecord(
                        challenge_name="Intel Guardian",
                        normalized_name="intel guardian",
                        points_awarded=30,
                        expected_points=100,
                    )
                ]
            },
        )

    monkeypatch.setattr(campaign_service, "_prepare_status_sources", fake_status_sources)

    summary = get_campaign_summary(session, week=None, user_filter=None)
    assert summary.rows
    assert summary.rows[0].statusIndicators
    assert summary.rows[0].statusIndicators[0].code == "points-mismatch"
