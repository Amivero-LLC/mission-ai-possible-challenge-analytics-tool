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
from difflib import SequenceMatcher
from time import perf_counter
from typing import Iterable, List, Sequence
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..db import crud
from ..db.models import Model, Rank, SubmittedActivity, User
from ..services.dashboard import MissionAnalysisContext, build_mission_analysis_context
from .schemas import (
    ActivityOverviewEntry,
    ActivityWeekSummary,
    CampaignLeaderboardRow,
    CampaignSummaryResponse,
    CampaignUserInfo,
    SubmissionReloadSummary,
)
from .status_rules import (
    CompletionRecord,
    SubmissionRecord,
    UserStatusPayload,
    evaluate_status_rules,
)

logger = logging.getLogger(__name__)

REVIEW_STATUS = "review completed"
MISSION_PREFIX_RE = re.compile(r"^mission:\s*", flags=re.IGNORECASE)
WEEK_TOKEN_RE = re.compile(r"\bweek\s*\d+\b", flags=re.IGNORECASE)
DIFFICULTY_WORD_RE = re.compile(r"\b(easy|medium|hard)\b", flags=re.IGNORECASE)
CHALLENGE_WORD_RE = re.compile(r"\bchallenge(s)?\b", flags=re.IGNORECASE)
MISSION_DIFFICULTY_RE = re.compile(r"\([^)]*difficulty[^)]*\)\s*$", flags=re.IGNORECASE)
PUNCTUATION_TABLE = str.maketrans({char: " " for char in string.punctuation})
WHITESPACE_RE = re.compile(r"\s+")
CORE_SIMILARITY_THRESHOLD = 0.82
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


@dataclass(frozen=True)
class _ModelRecord:
    model_id: str
    normalized_name: str | None
    week: int | None
    points: int | None


def _normalize_mission_name(value: str | None) -> str | None:

    if not value:
        return None
    text_value = value.strip()
    if not text_value:
        return None
    text_value = MISSION_PREFIX_RE.sub("", text_value)
    text_value = WEEK_TOKEN_RE.sub(" ", text_value)
    text_value = DIFFICULTY_WORD_RE.sub(" ", text_value)
    text_value = re.sub(r"difficulty", " ", text_value, flags=re.IGNORECASE)
    text_value = CHALLENGE_WORD_RE.sub(" ", text_value)
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


def _coerce_model_week(value: str | int | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _build_model_lookup(session: Session) -> tuple[dict[str, _ModelRecord], dict[str, List[_ModelRecord]]]:
    by_id: dict[str, _ModelRecord] = {}
    by_name: dict[str, List[_ModelRecord]] = defaultdict(list)
    result = session.execute(select(Model.id, Model.name, Model.maip_week, Model.maip_points))
    for model_id, model_name, maip_week, maip_points in result:
        normalized = _normalize_mission_name(model_name) or _normalize_mission_name(model_id)
        week_value = _coerce_model_week(maip_week)
        points_value = int(maip_points) if maip_points is not None else None
        record = _ModelRecord(
            model_id=model_id,
            normalized_name=normalized,
            week=week_value,
            points=points_value,
        )
        by_id[model_id] = record
        if normalized:
            by_name[normalized].append(record)
    return by_id, by_name


def _weeks_compatible(model_week: int | None, submission_week: int | None) -> bool:
    if submission_week is None:
        return True
    if model_week is None:
        return False
    return model_week == submission_week


def _find_model_by_name(
    normalized_name: str | None,
    week_id: int | None,
    models_by_name: dict[str, List[_ModelRecord]],
) -> _ModelRecord | None:
    if not normalized_name:
        return None

    def _first_match(candidates: List[_ModelRecord]) -> _ModelRecord | None:
        week_matches = [candidate for candidate in candidates if _weeks_compatible(candidate.week, week_id)]
        return week_matches[0] if week_matches else None

    direct_candidates = models_by_name.get(normalized_name)
    if direct_candidates:
        direct_match = _first_match(direct_candidates)
        if direct_match:
            return direct_match

    best_candidate: _ModelRecord | None = None
    best_ratio = 0.0
    for candidate_name, candidates in models_by_name.items():
        if candidate_name == normalized_name:
            continue
        ratio = SequenceMatcher(None, normalized_name, candidate_name).ratio()
        if ratio < CORE_SIMILARITY_THRESHOLD or ratio <= best_ratio:
            continue
        candidate_match = _first_match(candidates)
        if candidate_match:
            best_candidate = candidate_match
            best_ratio = ratio

    return best_candidate


def _match_model_entry(
    mission_model_id: str | None,
    normalized_name: str | None,
    week_id: int | None,
    models_by_id: dict[str, _ModelRecord],
    models_by_name: dict[str, List[_ModelRecord]],
) -> _ModelRecord | None:
    if mission_model_id:
        record = models_by_id.get(mission_model_id)
        if record and _weeks_compatible(record.week, week_id):
            return record
    return _find_model_by_name(normalized_name, week_id, models_by_name)


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

    models_by_id, models_by_name = _build_model_lookup(session)
    _truncate_submissions(session)

    missions_linked = 0
    submission_models: List[SubmittedActivity] = []
    next_id = (session.execute(select(func.max(SubmittedActivity.id))).scalar() or 0) + 1
    for index, row in enumerate(rows, start=next_id):
        mission_model_id = None
        if row.activity_id == 3:
            normalized_mission = _normalize_mission_name(row.mission_challenge)
            matched_record = _find_model_by_name(normalized_mission, row.week_id, models_by_name)
            if matched_record:
                mission_model_id = matched_record.model_id
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


def _build_activity_overview(
    session: Session,
    *,
    week_filter: int | None,
    normalized_user: str | None,
    capped_weeks: list[int],
) -> list[ActivityOverviewEntry]:
    if not capped_weeks:
        return []

    filters = [func.lower(SubmittedActivity.activity_status) == REVIEW_STATUS]
    if week_filter is not None:
        filters.append(SubmittedActivity.week_id == week_filter)
    elif capped_weeks:
        filters.append(SubmittedActivity.week_id.in_(capped_weeks))
    if normalized_user:
        filters.append(func.lower(SubmittedActivity.email) == normalized_user)

    activity_rows = session.execute(
        select(
            SubmittedActivity.activity_type,
            SubmittedActivity.week_id,
            func.count(func.distinct(SubmittedActivity.user_sharepoint_id)).label("participants"),
            func.sum(SubmittedActivity.points_awarded).label("points"),
        )
        .where(*filters)
        .group_by(SubmittedActivity.activity_type, SubmittedActivity.week_id)
    ).all()

    participant_rows = session.execute(
        select(
            SubmittedActivity.activity_type,
            SubmittedActivity.user_sharepoint_id,
        )
        .where(*filters)
        .distinct()
    ).all()

    participants_by_activity: dict[str, set[int]] = defaultdict(set)
    for activity_type, sharepoint_id in participant_rows:
        if activity_type is None or sharepoint_id is None:
            continue
        participants_by_activity[str(activity_type)].add(int(sharepoint_id))

    overview_map: dict[str, dict] = {}
    for activity_type, week_id, participants, points in activity_rows:
        if activity_type is None or week_id is None or week_id not in capped_weeks:
            continue
        key = str(activity_type)
        entry = overview_map.setdefault(
            key,
            {
                "weeks": {},
                "total_points": 0,
            },
        )
        entry["weeks"][int(week_id)] = {
            "participants": int(participants or 0),
            "points": _decimal_to_int(points),
        }
        entry["total_points"] += entry["weeks"][int(week_id)]["points"]

    activity_overview: list[ActivityOverviewEntry] = []
    for activity_type, data in overview_map.items():
        total_participants = len(participants_by_activity.get(activity_type, set()))
        weeks_payload = {
            week: ActivityWeekSummary(
                participants=week_info["participants"],
                points=week_info["points"],
            )
            for week, week_info in sorted(data["weeks"].items())
        }
        activity_overview.append(
            ActivityOverviewEntry(
                activityType=activity_type,
                totalParticipants=total_participants,
                totalPoints=data.get("total_points", 0),
                weeks=weeks_payload,
            )
        )

    activity_overview.sort(key=lambda entry: (-entry.totalPoints, entry.activityType.lower()))
    return activity_overview


def _collect_completed_challenges(
    context: MissionAnalysisContext | None,
) -> dict[str, dict[str, CompletionRecord]]:
    completions: dict[str, dict[str, CompletionRecord]] = defaultdict(dict)
    if context is None:
        return completions

    analyzer = context.analyzer
    user_info_map = context.user_info_map

    for user_id, stats in analyzer.user_stats.items():
        user_details = user_info_map.get(user_id, {})
        email = (user_details.get("email") or "").strip().lower()
        if not email:
            continue
        per_user = completions[email]
        for detail in stats.get("missions_completed_details", []):
            mission_name = detail.get("mission_id")
            normalized = _normalize_mission_name(mission_name)
            if not normalized:
                continue
            record = per_user.get(normalized)
            if record:
                record.count += 1
            else:
                per_user[normalized] = CompletionRecord(
                    display_name=str(mission_name),
                    normalized_name=normalized,
                    count=1,
                )

    return completions


def _collect_submission_records(
    session: Session,
    models_by_id: dict[str, _ModelRecord],
    models_by_name: dict[str, List[_ModelRecord]],
) -> dict[str, list[SubmissionRecord]]:
    submissions: dict[str, list[SubmissionRecord]] = defaultdict(list)
    rows = session.execute(
        select(
            SubmittedActivity.email,
            SubmittedActivity.mission_challenge,
            SubmittedActivity.points_awarded,
            SubmittedActivity.mission_model_id,
            SubmittedActivity.week_id,
        ).where(func.lower(SubmittedActivity.activity_status) == REVIEW_STATUS)
    ).all()

    for email, mission_challenge, points_awarded, mission_model_id, submission_week in rows:
        normalized_email = (email or "").strip().lower()
        if not normalized_email:
            continue
        normalized_challenge = _normalize_mission_name(mission_challenge)
        model_record = _match_model_entry(
            mission_model_id,
            normalized_challenge,
            submission_week,
            models_by_id,
            models_by_name,
        )
        expected = model_record.points if model_record else None

        submissions[normalized_email].append(
            SubmissionRecord(
                challenge_name=mission_challenge or "Unknown Challenge",
                normalized_name=normalized_challenge,
                points_awarded=_decimal_to_int(points_awarded),
                expected_points=expected,
            )
        )

    return submissions


def _prepare_status_sources(session: Session) -> tuple[
    dict[str, dict[str, CompletionRecord]],
    dict[str, list[SubmissionRecord]],
]:
    models_by_id, models_by_name = _build_model_lookup(session)
    analysis_context = build_mission_analysis_context(strict=False)
    completions = _collect_completed_challenges(analysis_context)
    submissions = _collect_submission_records(session, models_by_id, models_by_name)
    return completions, submissions


def get_campaign_summary(session: Session, *, week: str | None, user_filter: str | None) -> CampaignSummaryResponse:
    week_filter = _coerce_week_param(week)
    normalized_user = user_filter.strip().lower() if user_filter and user_filter.strip() else None
    completions_index, submissions_index = _prepare_status_sources(session)

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
    activity_overview = _build_activity_overview(
        session,
        week_filter=week_filter,
        normalized_user=normalized_user,
        capped_weeks=capped_weeks,
    )

    if not aggregates:
        last_upload_at = _get_last_upload_timestamp(session)
        return CampaignSummaryResponse(
            weeks_present=capped_weeks,
            rows=[],
            last_upload_at=last_upload_at,
            activity_overview=activity_overview,
        )

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
        payload = UserStatusPayload(
            email=info["user"]["email"],
            normalized_email=key,
            completions=completions_index.get(key, {}),
            submissions=submissions_index.get(key, []),
        )
        indicators = evaluate_status_rules(payload)
        rows.append(
            CampaignLeaderboardRow(
                user=CampaignUserInfo(**info["user"]),
                pointsByWeek=points_by_week,
                totalPoints=total_points_value,
                currentRank=user.current_rank if user else 0,
                statusIndicators=indicators,
            )
        )

    rows.sort(key=lambda item: (-item.totalPoints, item.user.firstName or "", item.user.email))
    last_upload_at = _get_last_upload_timestamp(session)
    return CampaignSummaryResponse(
        weeks_present=capped_weeks,
        rows=rows,
        last_upload_at=last_upload_at,
        activity_overview=activity_overview,
    )
