from __future__ import annotations

import csv
import io
import logging
import re
import string
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from time import perf_counter
from typing import Iterable, List, Sequence
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..db import crud
from ..db.models import Model, Rank, SubmittedActivity, User
from .schemas import (
    CampaignLeaderboardRow,
    CampaignSummaryResponse,
    CampaignUserInfo,
    SubmissionReloadSummary,
)

logger = logging.getLogger(__name__)

REVIEW_STATUS = "review completed"
MISSION_PREFIX_RE = re.compile(r"^mission:\s*", flags=re.IGNORECASE)
MISSION_DIFFICULTY_RE = re.compile(r"\([^)]*difficulty[^)]*\)\s*$", flags=re.IGNORECASE)
PUNCTUATION_TABLE = str.maketrans({char: " " for char in string.punctuation})
WHITESPACE_RE = re.compile(r"\s+")
CAMPAIGN_RESOURCE = "campaign_submissions"

DEFAULT_RANK_ROWS: Sequence[dict] = (
    {"rank_number": 0, "rank_name": "None", "minimum_points": 0, "swag": "None", "total_raffle_tickets": 0},
    {"rank_number": 1, "rank_name": "Analyst", "minimum_points": 150, "swag": "Sticker", "total_raffle_tickets": 1},
    {"rank_number": 2, "rank_name": "Agent", "minimum_points": 300, "swag": None, "total_raffle_tickets": 3},
    {"rank_number": 3, "rank_name": "Field Agent", "minimum_points": 500, "swag": "Custom Water Bottle", "total_raffle_tickets": 7},
    {"rank_number": 4, "rank_name": "Secret Agent", "minimum_points": 750, "swag": "Custom Hoodie", "total_raffle_tickets": 15},
)

REQUIRED_COLUMNS = {
    "UserID",
    "Email",
    "ActivityID",
    "ActivityType",
    "ActivityStatus",
    "WeekID",
    "Created",
}


@dataclass
class _SubmissionRow:
    user_sharepoint_id: int
    first_name: str | None
    last_name: str | None
    email: str
    activity_id: int
    activity_type: str
    activity_status: str
    points_awarded: Decimal
    week_id: int
    attachments: int | None
    use_case_title: str | None
    use_case_type: str | None
    use_case_story: str | None
    use_case_how: str | None
    use_case_value: str | None
    training_title: str | None
    training_reflection: str | None
    training_duration: Decimal | None
    training_link: str | None
    demo_title: str | None
    demo_description: str | None
    mission_challenge_week: str | None
    mission_challenge: str | None
    mission_challenge_response: Decimal | None
    quiz_topic: str | None
    quiz_score: Decimal | None
    quiz_completion_date: datetime | None
    created: datetime


def _normalize_mission_name(value: str | None) -> str | None:

    if not value:
        return None
    text_value = value.strip()
    if not text_value:
        return None
    text_value = MISSION_PREFIX_RE.sub("", text_value)
    text_value = MISSION_DIFFICULTY_RE.sub("", text_value)
    text_value = text_value.translate(PUNCTUATION_TABLE)
    text_value = WHITESPACE_RE.sub(" ", text_value)
    normalized = text_value.strip().lower()
    return normalized or None


def _parse_decimal(value: str | None, default: Decimal | None = None) -> Decimal | None:
    if value is None:
        return default
    text_value = value.strip()
    if not text_value:
        return default
    try:
        return Decimal(text_value)
    except (InvalidOperation, ValueError):
        return default


def _parse_int(value: str | None, *, required: bool, field: str, line_number: int) -> int | None:
    if value is None or not value.strip():
        if required:
            raise ValueError(f"Line {line_number}: '{field}' is required.")
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Line {line_number}: '{field}' must be an integer.") from exc


def _parse_datetime(value: str | None, *, required: bool, field: str, line_number: int) -> datetime | None:
    if value is None or not value.strip():
        if required:
            raise ValueError(f"Line {line_number}: '{field}' is required.")
        return None
    text_value = value.strip()
    if text_value.endswith("Z"):
        text_value = text_value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text_value)
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M"):
        try:
            dt = datetime.strptime(text_value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    if required:
        raise ValueError(f"Line {line_number}: '{field}' has an unsupported format.")
    return None


def _coerce_row(raw_row: dict[str, str | None], line_number: int) -> _SubmissionRow:
    user_sharepoint_id = _parse_int(raw_row.get("UserID"), required=True, field="UserID", line_number=line_number)
    activity_id = _parse_int(raw_row.get("ActivityID"), required=True, field="ActivityID", line_number=line_number)
    week_id = _parse_int(raw_row.get("WeekID"), required=True, field="WeekID", line_number=line_number)
    if user_sharepoint_id is None or activity_id is None or week_id is None:
        raise ValueError(f"Line {line_number}: Missing required numeric field.")

    email = (raw_row.get("Email") or "").strip()
    if not email:
        raise ValueError(f"Line {line_number}: 'Email' is required.")

    activity_type = (raw_row.get("ActivityType") or "").strip()
    activity_status = (raw_row.get("ActivityStatus") or "").strip()
    if not activity_type:
        raise ValueError(f"Line {line_number}: 'ActivityType' is required.")
    if not activity_status:
        raise ValueError(f"Line {line_number}: 'ActivityStatus' is required.")

    created = _parse_datetime(raw_row.get("Created"), required=True, field="Created", line_number=line_number)
    if created is None:
        raise ValueError(f"Line {line_number}: 'Created' is required.")

    attachments = _parse_int(raw_row.get("Attachments"), required=False, field="Attachments", line_number=line_number)
    training_duration = _parse_decimal(raw_row.get("TrainingDuration"))
    mission_response = _parse_decimal(raw_row.get("MissionChallengeResponse"))
    quiz_score = _parse_decimal(raw_row.get("QuizScore"))
    quiz_completion_date = _parse_datetime(raw_row.get("QuizCompletionDate"), required=False, field="QuizCompletionDate", line_number=line_number)

    points_awarded = _parse_decimal(raw_row.get("PointsAwarded"), default=Decimal("0")) or Decimal("0")

    return _SubmissionRow(
        user_sharepoint_id=user_sharepoint_id,
        first_name=(raw_row.get("FirstName") or "").strip() or None,
        last_name=(raw_row.get("LastName") or "").strip() or None,
        email=email,
        activity_id=activity_id,
        activity_type=activity_type,
        activity_status=activity_status,
        points_awarded=points_awarded,
        week_id=week_id,
        attachments=attachments,
        use_case_title=(raw_row.get("UseCaseTitle") or "").strip() or None,
        use_case_type=(raw_row.get("UseCaseType") or "").strip() or None,
        use_case_story=(raw_row.get("UseCaseStory") or "").strip() or None,
        use_case_how=(raw_row.get("UseCaseHow") or "").strip() or None,
        use_case_value=(raw_row.get("UseCaseValue") or "").strip() or None,
        training_title=(raw_row.get("TrainingTitle") or "").strip() or None,
        training_reflection=(raw_row.get("TrainingReflection") or "").strip() or None,
        training_duration=training_duration,
        training_link=(raw_row.get("TrainingLink") or "").strip() or None,
        demo_title=(raw_row.get("DemoTitle") or "").strip() or None,
        demo_description=(raw_row.get("DemoDescription") or "").strip() or None,
        mission_challenge_week=(raw_row.get("MissionChallengeWeek") or "").strip() or None,
        mission_challenge=(raw_row.get("MissionChallenge") or "").strip() or None,
        mission_challenge_response=mission_response,
        quiz_topic=(raw_row.get("QuizTopic") or "").strip() or None,
        quiz_score=quiz_score,
        quiz_completion_date=quiz_completion_date,
        created=created,
    )


def _decode_csv(content: bytes) -> List[_SubmissionRow]:
    if not content:
        raise ValueError("Uploaded CSV file is empty.")

    decoded = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise ValueError("CSV file is missing a header row.")

    missing = [field for field in REQUIRED_COLUMNS if field not in reader.fieldnames]
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"CSV file is missing required columns: {missing_str}")

    rows: List[_SubmissionRow] = []
    for index, raw_row in enumerate(reader, start=2):
        if not any(value and str(value).strip() for value in raw_row.values()):
            continue
        coerced = _coerce_row(raw_row, index)
        rows.append(coerced)

    if not rows:
        raise ValueError("CSV file does not contain any data rows.")
    return rows


def _truncate_submissions(session: Session) -> None:
    bind = session.get_bind()
    dialect = bind.dialect.name if bind else ""
    if dialect == "sqlite":
        session.execute(text("DELETE FROM submitted_activity_list"))
        try:
            session.execute(text("DELETE FROM sqlite_sequence WHERE name='submitted_activity_list'"))
        except OperationalError:
            pass
    else:
        session.execute(text("TRUNCATE TABLE submitted_activity_list RESTART IDENTITY CASCADE"))


def _build_model_lookup(session: Session) -> dict[str, str]:
    lookup: dict[str, str] = {}
    result = session.execute(select(Model.id, Model.name))
    for model_id, model_name in result:
        normalized = _normalize_mission_name(model_name) or _normalize_mission_name(model_id)
        if normalized and normalized not in lookup:
            lookup[normalized] = model_id
    return lookup


def _get_last_upload_timestamp(session: Session) -> str | None:
    log = crud.get_latest_reload(session, CAMPAIGN_RESOURCE)
    if log and log.finished_at:
        finished = log.finished_at
        if finished.tzinfo is None:
            finished = finished.replace(tzinfo=timezone.utc)
        else:
            finished = finished.astimezone(timezone.utc)
        return finished.isoformat()
    return None


def _validate_unique_user_ids(rows: Iterable[_SubmissionRow]) -> None:
    by_email: dict[str, int] = {}
    conflicts: dict[str, set[int]] = defaultdict(set)

    for row in rows:
        email = row.email.lower()
        if email not in by_email:
            by_email[email] = row.user_sharepoint_id
            continue

        if row.user_sharepoint_id != by_email[email]:
            conflicts[email].update({by_email[email], row.user_sharepoint_id})

    if conflicts:
        messages = [
            f"{email} -> IDs {', '.join(str(uid) for uid in sorted(ids))}"
            for email, ids in conflicts.items()
        ]
        detail = (
            "Each email must map to one SharePoint UserID. "
            "Fix the CSV and re-upload. Conflicts: "
            + "; ".join(messages)
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _generate_user_id(session: Session, sharepoint_id: int | None, email: str) -> str:
    if sharepoint_id is not None:
        candidate = f"sal-{sharepoint_id}"
        if session.get(User, candidate) is None:
            return candidate
    sanitized = email.lower().replace("@", "-at-").replace(".", "-")
    candidate = f"sal-{sanitized}"
    if session.get(User, candidate) is None:
        return candidate
    return f"sal-{uuid4()}"


def _upsert_users_from_submissions(session: Session, rows: Iterable[_SubmissionRow]) -> tuple[int, int]:
    created = 0
    updated = 0
    cache: dict[str, _SubmissionRow] = {}
    for row in rows:
        key = row.email.lower()
        if key not in cache:
            cache[key] = row

    for email_lower, row in cache.items():
        existing = session.execute(
            select(User).where(func.lower(User.email) == email_lower)
        ).scalar_one_or_none()
        display_name = " ".join(filter(None, [row.first_name, row.last_name])) or None
        if existing is None and row.user_sharepoint_id is not None:
            existing = session.execute(
                select(User).where(User.sharepoint_user_id == row.user_sharepoint_id)
            ).scalar_one_or_none()

        if existing is None:
            user_id = _generate_user_id(session, row.user_sharepoint_id, row.email)
            session.add(
                User(
                    id=user_id,
                    name=display_name,
                    email=row.email,
                    data={"source": "submitted_activity_list"},
                    sharepoint_user_id=row.user_sharepoint_id,
                    total_points=Decimal("0"),
                    current_rank=0,
                )
            )
            created += 1
            continue

        changed = False
        if not existing.sharepoint_user_id and row.user_sharepoint_id:
            conflict = session.execute(
                select(User).where(User.sharepoint_user_id == row.user_sharepoint_id)
            ).scalar_one_or_none()
            if conflict and conflict.id != existing.id:
                logger.warning(
                    "SharePoint ID %s already linked to user %s; skipping reassignment to %s",
                    row.user_sharepoint_id,
                    conflict.id,
                    existing.id,
                )
            else:
                existing.sharepoint_user_id = row.user_sharepoint_id
                changed = True
        if display_name and not existing.name:
            existing.name = display_name
            changed = True
        if changed:
            updated += 1

    return created, updated


def _ensure_default_ranks(session: Session) -> None:
    existing_numbers = set(session.execute(select(Rank.rank_number)).scalars())
    missing = [Rank(**row) for row in DEFAULT_RANK_ROWS if row["rank_number"] not in existing_numbers]
    if missing:
        session.add_all(missing)
        session.flush()


def _recompute_user_points(session: Session) -> None:
    _ensure_default_ranks(session)
    session.execute(update(User).values(total_points=Decimal("0"), current_rank=0))

    points_rows = session.execute(
        select(
            SubmittedActivity.user_sharepoint_id,
            func.lower(SubmittedActivity.email).label("email_lc"),
            func.sum(SubmittedActivity.points_awarded).label("points"),
        )
        .where(func.lower(SubmittedActivity.activity_status) == REVIEW_STATUS)
        .group_by(SubmittedActivity.user_sharepoint_id, func.lower(SubmittedActivity.email))
    ).all()

    if not points_rows:
        return

    users = session.execute(select(User)).scalars().all()
    by_sharepoint = {user.sharepoint_user_id: user for user in users if user.sharepoint_user_id is not None}
    by_email = { (user.email or "").lower(): user for user in users if user.email }

    for entry in points_rows:
        user = by_sharepoint.get(entry.user_sharepoint_id) or by_email.get(entry.email_lc)
        if not user:
            continue
        user.total_points = entry.points or Decimal("0")

    ranks = session.execute(select(Rank).order_by(Rank.minimum_points)).scalars().all()
    for user in users:
        total_points = Decimal(user.total_points or 0)
        assigned_rank = 0
        for rank in ranks:
            if total_points >= rank.minimum_points:
                assigned_rank = rank.rank_number
        user.current_rank = assigned_rank


def reload_submissions(content: bytes, session: Session) -> SubmissionReloadSummary:
    start_time = perf_counter()
    try:
        rows = _decode_csv(content)
    except ValueError as exc:
        logger.warning("Unable to parse submitted activity CSV: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    logger.info("Parsed %d submitted activity rows", len(rows))

    _validate_unique_user_ids(rows)

    model_lookup = _build_model_lookup(session)
    _truncate_submissions(session)

    missions_linked = 0
    submission_models: List[SubmittedActivity] = []
    next_id = (session.execute(select(func.max(SubmittedActivity.id))).scalar() or 0) + 1
    for index, row in enumerate(rows, start=next_id):
        mission_model_id = None
        if row.activity_id == 3:
            normalized_mission = _normalize_mission_name(row.mission_challenge)
            if normalized_mission:
                mission_model_id = model_lookup.get(normalized_mission)
                if mission_model_id:
                    missions_linked += 1

        submission_models.append(
            SubmittedActivity(
                id=index,
                user_sharepoint_id=row.user_sharepoint_id,
                first_name=row.first_name,
                last_name=row.last_name,
                email=row.email,
                activity_id=row.activity_id,
                activity_type=row.activity_type,
                activity_status=row.activity_status,
                points_awarded=row.points_awarded,
                week_id=row.week_id,
                attachments=row.attachments,
                use_case_title=row.use_case_title,
                use_case_type=row.use_case_type,
                use_case_story=row.use_case_story,
                use_case_how=row.use_case_how,
                use_case_value=row.use_case_value,
                training_title=row.training_title,
                training_reflection=row.training_reflection,
                training_duration=row.training_duration,
                training_link=row.training_link,
                demo_title=row.demo_title,
                demo_description=row.demo_description,
                mission_challenge_week=row.mission_challenge_week,
                mission_challenge=row.mission_challenge,
                mission_challenge_response=row.mission_challenge_response,
                quiz_topic=row.quiz_topic,
                quiz_score=row.quiz_score,
                quiz_completion_date=row.quiz_completion_date,
                created=row.created,
                mission_model_id=mission_model_id,
            )
        )

    session.add_all(submission_models)
    session.flush()

    users_created, users_updated = _upsert_users_from_submissions(session, rows)
    session.flush()
    _recompute_user_points(session)

    duration = perf_counter() - start_time
    crud.record_reload_log(
        session,
        resource=CAMPAIGN_RESOURCE,
        mode="upload",
        status="success",
        message=None,
        rows=len(submission_models),
        previous_count=None,
        new_records=len(submission_models),
        total_count=len(submission_models),
        duration_seconds=duration,
    )

    return SubmissionReloadSummary(
        rows_inserted=len(submission_models),
        users_created=users_created,
        users_updated=users_updated,
        missions_linked=missions_linked,
    )


def _coerce_week_param(raw_week: str | None) -> int | None:
    if raw_week is None or raw_week.lower() == "all":
        return None
    try:
        week_value = int(raw_week)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Week must be an integer or 'all'.") from exc
    if week_value < 1 or week_value > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Week must be between 1 and 10.")
    return week_value


def _decimal_to_int(value: Decimal | None) -> int:
    if value is None:
        return 0
    quantized = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(quantized)


def get_campaign_summary(session: Session, *, week: str | None, user_filter: str | None) -> CampaignSummaryResponse:
    week_filter = _coerce_week_param(week)
    normalized_user = user_filter.strip().lower() if user_filter and user_filter.strip() else None

    weeks_present_query = session.execute(
        select(SubmittedActivity.week_id).distinct().order_by(SubmittedActivity.week_id)
    )
    weeks_present = [item[0] for item in weeks_present_query if item[0] is not None]
    capped_weeks = weeks_present[:10]

    base_query = (
        select(
            SubmittedActivity.email,
            SubmittedActivity.first_name,
            SubmittedActivity.last_name,
            SubmittedActivity.user_sharepoint_id,
            SubmittedActivity.week_id,
            func.sum(SubmittedActivity.points_awarded).label("points"),
        )
        .where(func.lower(SubmittedActivity.activity_status) == REVIEW_STATUS)
        .group_by(
            SubmittedActivity.email,
            SubmittedActivity.first_name,
            SubmittedActivity.last_name,
            SubmittedActivity.user_sharepoint_id,
            SubmittedActivity.week_id,
        )
    )

    if week_filter is not None:
        base_query = base_query.where(SubmittedActivity.week_id == week_filter)
    if normalized_user:
        base_query = base_query.where(func.lower(SubmittedActivity.email) == normalized_user)

    aggregates = session.execute(base_query).all()

    if not aggregates:
        return CampaignSummaryResponse(weeks_present=capped_weeks, rows=[])

    grouped: dict[str, dict] = {}
    for entry in aggregates:
        key = entry.email.lower()
        record = grouped.setdefault(
            key,
            {
                "user": {
                    "firstName": entry.first_name,
                    "lastName": entry.last_name,
                    "email": entry.email,
                },
                "points": defaultdict(Decimal),
                "sharepoint_id": entry.user_sharepoint_id,
            },
        )
        record["points"][entry.week_id] = Decimal(entry.points or 0)

    sharepoint_ids = {info["sharepoint_id"] for info in grouped.values() if info["sharepoint_id"] is not None}
    email_keys = set(grouped.keys())

    user_query = select(User)
    filters = []
    if sharepoint_ids:
        filters.append(User.sharepoint_user_id.in_(sharepoint_ids))
    if email_keys:
        filters.append(func.lower(User.email).in_(email_keys))
    if filters:
        user_query = user_query.where(or_(*filters))
        users = session.execute(user_query).scalars().all()
    else:
        users = []

    by_sharepoint = {user.sharepoint_user_id: user for user in users if user.sharepoint_user_id is not None}
    by_email = {(user.email or "").lower(): user for user in users if user.email}

    rows: List[CampaignLeaderboardRow] = []
    for key, info in grouped.items():
        user = by_sharepoint.get(info["sharepoint_id"]) or by_email.get(key)
        points_by_week = {
            week: _decimal_to_int(points) for week, points in info["points"].items() if week in capped_weeks
        }
        if week_filter is None:
            total_points_value = sum(points_by_week.values())
        else:
            total_points_value = points_by_week.get(week_filter, 0)
        rows.append(
            CampaignLeaderboardRow(
                user=CampaignUserInfo(**info["user"]),
                pointsByWeek=points_by_week,
                totalPoints=total_points_value,
                currentRank=user.current_rank if user else 0,
            )
        )

    rows.sort(key=lambda item: (-item.totalPoints, item.user.firstName or "", item.user.email))
    last_upload_at = _get_last_upload_timestamp(session)
    return CampaignSummaryResponse(weeks_present=capped_weeks, rows=rows, last_upload_at=last_upload_at)
