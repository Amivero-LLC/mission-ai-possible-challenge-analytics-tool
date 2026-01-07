from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import ChallengeAttempt, Chat, Model, ReloadLog, User


def _parse_datetime(value: Optional[str | int | float]) -> Optional[datetime]:
    if value in (None, ""):
        return None

    if isinstance(value, (int, float)):
        # Values returned by Open WebUI are seconds; convert when plausible.
        if value > 0 and value < 1e12:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)

    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        # Attempt ISO8601 parsing; fallback returns None
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _normalize_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    text = str(value).strip()
    return text or None


def _normalize_int(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _extract_maip_metadata(record: dict) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    maip_week: Optional[str] = None
    maip_points: Optional[int] = None
    maip_difficulty: Optional[str] = None

    def walk(node: object) -> None:
        nonlocal maip_week, maip_points, maip_difficulty
        if not isinstance(node, dict):
            return

        if maip_week is None and "maip_week" in node:
            maip_week = _normalize_str(node.get("maip_week"))

        if maip_points is None:
            for key in ("maip_points_value", "maip_points"):
                if key in node:
                    maip_points = _normalize_int(node.get(key))
                    if maip_points is not None:
                        break

        if maip_difficulty is None:
            for key in ("maip_difficulty_level", "maip_difficulty"):
                if key in node:
                    maip_difficulty = _normalize_str(node.get(key))
                    if maip_difficulty is not None:
                        break

        for value in node.values():
            if isinstance(value, dict):
                walk(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        walk(item)

    walk(record)
    return maip_week, maip_points, maip_difficulty


def _infer_maip_from_name(name: Optional[str]) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    if not name:
        return None, None, None

    text = str(name).strip()
    if not text:
        return None, None, None

    week_value: Optional[str] = None
    difficulty_value: Optional[str] = None
    points_value: Optional[int] = None

    week_match = re.search(r"week\s*(\d+)", text, flags=re.IGNORECASE)
    if week_match:
        week_value = f"Week {week_match.group(1)}"

    difficulty_map = {
        "very easy": ("Very Easy", 10),
        "easy": ("Easy", 15),
        "medium": ("Medium", 20),
        "hard": ("Hard", 25),
        "impossible": ("Impossible", 30),
    }
    lower_text = text.lower()
    for key, (label, points) in difficulty_map.items():
        if key in lower_text:
            difficulty_value = label
            points_value = points
            break

    return week_value, points_value, difficulty_value


def _normalize_identifier(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _record_has_missions_tag(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    for candidate in (
        record.get("tags"),
        record.get("meta", {}).get("tags") if isinstance(record.get("meta"), dict) else None,
        record.get("info", {}).get("meta", {}).get("tags") if isinstance(record.get("info"), dict) else None,
    ):
        if isinstance(candidate, list):
            for entry in candidate:
                name = None
                if isinstance(entry, dict):
                    name = entry.get("name")
                elif isinstance(entry, str):
                    name = entry
                if name and isinstance(name, str) and name.strip().lower() == "missions":
                    return True
    return False


def _collect_model_identifiers(record: dict, model_id: Optional[str] = None) -> set[str]:
    identifiers: set[str] = set()
    if model_id:
        identifiers.add(str(model_id))

    def add(value: object) -> None:
        normalized = _normalize_identifier(value)
        if normalized:
            identifiers.add(normalized)

    for key in ("id", "slug", "model", "preset", "name", "display_name", "displayName", "model_id"):
        add(record.get(key))

    meta = record.get("meta")
    if isinstance(meta, dict):
        for key in ("id", "slug", "model", "preset", "name"):
            add(meta.get(key))

    info = record.get("info")
    if isinstance(info, dict):
        for key in ("id", "slug", "model", "preset", "name"):
            add(info.get(key))
        info_meta = info.get("meta")
        if isinstance(info_meta, dict):
            for key in ("id", "slug", "model", "preset", "name"):
                add(info_meta.get(key))

    return identifiers


def upsert_users(session: Session, records: Iterable[dict]) -> int:
    """Insert or update user records, preserving the raw payload for fidelity."""
    affected = 0
    for record in records:
        user_id = record.get("id") or record.get("user_id")
        if not user_id:
            continue

        existing = session.get(User, user_id)
        name = record.get("name") or record.get("display_name")
        email = record.get("email")
        normalized = {
            "name": name,
            "email": email,
            "data": record,
        }

        if existing:
            continue
        session.add(
            User(
                id=user_id,
                **normalized,
            )
        )
        affected += 1

    return affected


def upsert_models(session: Session, records: Iterable[dict]) -> int:
    """Store Open WebUI models metadata."""
    affected = 0
    for record in records:
        model_id = (
            record.get("id")
            or record.get("model_id")
            or record.get("slug")
            or record.get("model")
        )
        if not model_id:
            continue

        existing = session.get(Model, model_id)
        display_name = (
            record.get("name")
            or record.get("display_name")
            or record.get("preset")
            or record.get("model")
        )
        maip_week, maip_points, maip_difficulty = _extract_maip_metadata(record)
        if not maip_week or maip_points is None or not maip_difficulty:
            inferred_week, inferred_points, inferred_difficulty = _infer_maip_from_name(display_name)
            if not maip_week and inferred_week:
                maip_week = inferred_week
            if maip_points is None and inferred_points is not None:
                maip_points = inferred_points
            if not maip_difficulty and inferred_difficulty:
                maip_difficulty = inferred_difficulty

        if existing:
            continue
        session.add(
            Model(
                id=model_id,
                name=display_name,
                data=record,
                maip_week=maip_week,
                maip_points=maip_points,
                maip_difficulty=maip_difficulty,
            )
        )
        affected += 1
    return affected


def _build_placeholder_user(record: dict, user_id: str) -> Dict[str, object]:
    """
    Construct a minimal user payload using any hints from the chat record so
    chats referencing unknown users can be persisted without violating the FK.
    """
    user_sources = [
        record.get("user"),
        record.get("owner"),
        record.get("profile"),
        record.get("meta", {}).get("user") if isinstance(record.get("meta"), dict) else None,
        record.get("chat", {}).get("user") if isinstance(record.get("chat"), dict) else None,
    ]
    user_data: Dict[str, object] = {}
    for candidate in user_sources:
        if isinstance(candidate, dict):
            user_data = dict(candidate)
            break

    user_data.setdefault("id", user_id)
    user_data.setdefault("_source", "chat_placeholder")

    def _normalize(value: object) -> Optional[str]:
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text or None

    name = _normalize(
        user_data.get("name")
        or user_data.get("display_name")
        or user_data.get("username")
        or user_data.get("email")
    )
    email = _normalize(user_data.get("email"))

    return {
        "name": name,
        "email": email,
        "data": user_data or {"id": user_id},
    }


def upsert_chats(session: Session, records: Iterable[dict]) -> int:
    """Insert chat transcripts while preserving mission-specific metadata."""
    affected = 0
    ensured_users: set[str] = set()
    challenge_aliases: set[str] = set()
    challenge_aliases_lower: set[str] = set()

    model_rows = session.execute(select(Model.id, Model.data)).all()
    for model_id, model_data in model_rows:
        if not isinstance(model_data, dict):
            continue
        if not _record_has_missions_tag(model_data):
            continue
        identifiers = _collect_model_identifiers(model_data, model_id)
        for identifier in identifiers:
            challenge_aliases.add(identifier)
            challenge_aliases_lower.add(identifier.lower())

    for record in records:
        chat_id = record.get("id")
        if not chat_id:
            continue

        chat_data = record.get("chat") or {}
        user_id = record.get("user_id") or chat_data.get("user_id")
        title = record.get("title") or chat_data.get("title")
        models = chat_data.get("models", [])
        primary_model = None
        if isinstance(models, list) and models:
            candidate = models[0]
            if isinstance(candidate, str):
                primary_model = candidate
            elif isinstance(candidate, dict):
                primary_model = (
                    candidate.get("id")
                    or candidate.get("model")
                    or candidate.get("slug")
                )
        if primary_model is None:
            primary_model = chat_data.get("model") or record.get("model")

        if not primary_model or not challenge_aliases_lower:
            continue

        if str(primary_model).lower() not in challenge_aliases_lower:
            continue

        if user_id:
            if user_id not in ensured_users:
                if not session.get(User, user_id):
                    placeholder = _build_placeholder_user(record, user_id)
                    session.add(User(id=user_id, **placeholder))
                ensured_users.add(user_id)

        messages = chat_data.get("messages") or []
        message_count = len(messages) if isinstance(messages, list) else None
        archived = bool(record.get("archived", False))

        existing = session.get(Chat, chat_id)
        payload = {
            "user_id": user_id,
            "title": title,
            "model": primary_model,
            "created_at_remote": _parse_datetime(record.get("created_at")),
            "updated_at_remote": _parse_datetime(record.get("updated_at")),
            "message_count": message_count,
            "archived": archived,
            "data": record,
        }

        if existing:
            for field, value in payload.items():
                setattr(existing, field, value)
        else:
            session.add(
                Chat(
                    id=chat_id,
                    **payload,
                )
            )
        affected += 1

    return affected


def upsert_challenge_attempts(session: Session, records: Iterable[dict]) -> int:
    """Store per-challenge attempt data for faster analytics queries."""
    affected = 0
    for record in records:
        attempt_id = record.get("id")
        if not attempt_id:
            continue

        existing = session.get(ChallengeAttempt, attempt_id)

        sanitized = {
            "chat_id": record.get("chat_id"),
            "chat_index": record.get("chat_index") or 0,
            "user_id": record.get("user_id"),
            "mission_id": record.get("mission_id"),
            "mission_model": record.get("mission_model"),
            "mission_week": record.get("mission_week"),
            "completed": bool(record.get("completed", False)),
            "message_count": record.get("message_count") or 0,
            "user_message_count": record.get("user_message_count") or 0,
            "started_at": record.get("started_at"),
            "updated_at_raw": record.get("updated_at_raw"),
            "payload": record.get("payload") or {},
        }

        if existing:
            for field, value in sanitized.items():
                setattr(existing, field, value)
        else:
            session.add(ChallengeAttempt(id=attempt_id, **sanitized))
        affected += 1

    return affected


def truncate_table(session: Session, model) -> int:
    """Delete all rows from the provided table and return the count."""
    result = session.execute(delete(model))
    return result.rowcount or 0


def record_reload_log(
    session: Session,
    *,
    resource: str,
    mode: str,
    status: str,
    message: str | None,
    rows: int | None,
    previous_count: int | None = None,
    new_records: int | None = None,
    total_count: int | None = None,
    duration_seconds: float | None = None,
) -> ReloadLog:
    log = ReloadLog(
        resource=resource,
        mode=mode,
        status=status,
        message=message,
        rows_affected=rows,
        previous_count=previous_count,
        new_records=new_records,
        total_count=total_count,
        duration_seconds=duration_seconds,
        finished_at=datetime.now(timezone.utc),
    )
    session.add(log)
    return log


def get_row_count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def get_latest_reload(session: Session, resource: str) -> ReloadLog | None:
    stmt = (
        select(ReloadLog)
        .where(ReloadLog.resource == resource)
        .order_by(ReloadLog.finished_at.desc().nullslast(), ReloadLog.id.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def get_latest_reload_any(session: Session) -> ReloadLog | None:
    stmt = select(ReloadLog).order_by(ReloadLog.finished_at.desc().nullslast(), ReloadLog.id.desc()).limit(1)
    return session.execute(stmt).scalars().first()


def get_recent_logs(session: Session, limit: int = 10) -> List[ReloadLog]:
    stmt = (
        select(ReloadLog)
        .order_by(ReloadLog.finished_at.desc().nullslast(), ReloadLog.id.desc())
        .limit(limit)
    )
    return session.execute(stmt).scalars().all()
