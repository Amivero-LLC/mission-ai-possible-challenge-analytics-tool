from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import Chat, Model, ReloadLog, User


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
            for field, value in normalized.items():
                setattr(existing, field, value)
        else:
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

        if existing:
            existing.name = display_name
            existing.data = record
            existing.maip_week = maip_week
            existing.maip_points = maip_points
            existing.maip_difficulty = maip_difficulty
        else:
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


def upsert_chats(session: Session, records: Iterable[dict]) -> int:
    """Insert chat transcripts while preserving mission-specific metadata."""
    affected = 0
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
