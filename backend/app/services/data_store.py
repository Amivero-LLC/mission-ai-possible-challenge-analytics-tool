from __future__ import annotations

import logging
from time import perf_counter
from threading import Lock
from copy import deepcopy
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import select

from ..db import crud
from ..db import get_db_session
from ..db.models import ChallengeAttempt as ChallengeAttemptModel
from ..db.models import Chat as ChatModel
from ..db.models import Model as ModelModel
from ..db.models import ReloadLog
from ..db.models import User as UserModel
from .model_admin import collect_model_identifiers


logger = logging.getLogger(__name__)
_CHALLENGE_ATTEMPT_LOCK = Lock()


def persist_chats(records: Iterable[dict], mode: str = "upsert") -> int:
    start_time = perf_counter()
    previous_count = None
    record_count = len(records) if hasattr(records, "__len__") else None
    if record_count is not None:
        logger.debug("Persisting %d chat records (mode=%s)", record_count, mode)
    else:
        logger.debug("Persisting chat records from iterable (mode=%s)", mode)
    try:
        with get_db_session() as session:
            previous_count = crud.get_row_count(session, ChatModel)
            if mode == "truncate":
                crud.truncate_table(session, ChatModel)
            rows = crud.upsert_chats(session, records)
            total_count = crud.get_row_count(session, ChatModel)
            previous = previous_count or 0
            if mode == "truncate":
                new_records = total_count
            else:
                new_records = max(total_count - previous, 0)
            duration = perf_counter() - start_time
            crud.record_reload_log(
                session,
                resource="chats",
                mode=mode,
                status="success",
                message=None,
                rows=rows,
                previous_count=previous_count,
                new_records=new_records,
                total_count=total_count,
                duration_seconds=duration,
            )
            logger.info(
                "Persisted %s chat records in %.2fs (mode=%s, previous=%s, new=%s, total=%s)",
                rows,
                duration,
                mode,
                previous_count,
                new_records,
                total_count,
            )
            return rows
    except Exception as exc:
        duration = perf_counter() - start_time
        logger.exception("Failed to persist chats (mode=%s)", mode)
        with get_db_session() as session:
            crud.record_reload_log(
                session,
                resource="chats",
                mode=mode,
                status="error",
                message=str(exc),
                rows=None,
                previous_count=previous_count,
                new_records=None,
                total_count=None,
                duration_seconds=duration,
            )
        raise


def persist_users(records: Iterable[dict], mode: str = "upsert") -> int:
    start_time = perf_counter()
    previous_count = None
    record_count = len(records) if hasattr(records, "__len__") else None
    if record_count is not None:
        logger.debug("Persisting %d user records (mode=%s)", record_count, mode)
    else:
        logger.debug("Persisting user records from iterable (mode=%s)", mode)
    try:
        with get_db_session() as session:
            previous_count = crud.get_row_count(session, UserModel)
            if mode == "truncate":
                crud.truncate_table(session, UserModel)
            rows = crud.upsert_users(session, records)
            total_count = crud.get_row_count(session, UserModel)
            previous = previous_count or 0
            if mode == "truncate":
                new_records = total_count
            else:
                new_records = max(total_count - previous, 0)
            duration = perf_counter() - start_time
            crud.record_reload_log(
                session,
                resource="users",
                mode=mode,
                status="success",
                message=None,
                rows=rows,
                previous_count=previous_count,
                new_records=new_records,
                total_count=total_count,
                duration_seconds=duration,
            )
            logger.info(
                "Persisted %s user records in %.2fs (mode=%s, previous=%s, new=%s, total=%s)",
                rows,
                duration,
                mode,
                previous_count,
                new_records,
                total_count,
            )
            return rows
    except Exception as exc:
        duration = perf_counter() - start_time
        logger.exception("Failed to persist users (mode=%s)", mode)
        with get_db_session() as session:
            crud.record_reload_log(
                session,
                resource="users",
                mode=mode,
                status="error",
                message=str(exc),
                rows=None,
                previous_count=previous_count,
                new_records=None,
                total_count=None,
                duration_seconds=duration,
            )
        raise


def persist_models(records: Iterable[dict], mode: str = "upsert") -> int:
    start_time = perf_counter()
    previous_count = None
    record_count = len(records) if hasattr(records, "__len__") else None
    if record_count is not None:
        logger.debug("Persisting %d model records (mode=%s)", record_count, mode)
    else:
        logger.debug("Persisting model records from iterable (mode=%s)", mode)
    try:
        with get_db_session() as session:
            previous_count = crud.get_row_count(session, ModelModel)
            if mode == "truncate":
                crud.truncate_table(session, ModelModel)
            rows = crud.upsert_models(session, records)
            total_count = crud.get_row_count(session, ModelModel)
            previous = previous_count or 0
            if mode == "truncate":
                new_records = total_count
            else:
                new_records = max(total_count - previous, 0)
            duration = perf_counter() - start_time
            crud.record_reload_log(
                session,
                resource="models",
                mode=mode,
                status="success",
                message=None,
                rows=rows,
                previous_count=previous_count,
                new_records=new_records,
                total_count=total_count,
                duration_seconds=duration,
            )
            logger.info(
                "Persisted %s model records in %.2fs (mode=%s, previous=%s, new=%s, total=%s)",
                rows,
                duration,
                mode,
                previous_count,
                new_records,
                total_count,
            )
            return rows
    except Exception as exc:
        duration = perf_counter() - start_time
        logger.exception("Failed to persist models (mode=%s)", mode)
        with get_db_session() as session:
            crud.record_reload_log(
                session,
                resource="models",
                mode=mode,
                status="error",
                message=str(exc),
                rows=None,
                previous_count=previous_count,
                new_records=None,
                total_count=None,
                duration_seconds=duration,
            )
        raise


def persist_challenge_attempts(records: Iterable[dict], mode: str = "upsert") -> int:
    start_time = perf_counter()
    previous_count = None
    mode_normalized = mode.lower()
    if mode_normalized not in {"upsert", "truncate"}:
        raise ValueError("mode must be 'upsert' or 'truncate'")

    with _CHALLENGE_ATTEMPT_LOCK:
        try:
            with get_db_session() as session:
                previous_count = crud.get_row_count(session, ChallengeAttemptModel)
                if mode_normalized == "truncate":
                    crud.truncate_table(session, ChallengeAttemptModel)
                rows = crud.upsert_challenge_attempts(session, records)
                total_count = crud.get_row_count(session, ChallengeAttemptModel)
                previous = previous_count or 0
                if mode_normalized == "truncate":
                    new_records = total_count
                else:
                    new_records = max(total_count - previous, 0)
                duration = perf_counter() - start_time
                crud.record_reload_log(
                    session,
                    resource="challenge_attempts",
                    mode=mode_normalized,
                    status="success",
                    message=None,
                    rows=rows,
                    previous_count=previous_count,
                    new_records=new_records,
                    total_count=total_count,
                    duration_seconds=duration,
                )
                logger.info(
                    "Persisted %s challenge attempts in %.2fs (mode=%s, previous=%s, new=%s, total=%s)",
                    rows,
                    duration,
                    mode_normalized,
                    previous_count,
                    new_records,
                    total_count,
                )
                return rows
        except Exception as exc:
            duration = perf_counter() - start_time
            logger.exception("Failed to persist challenge attempts (mode=%s)", mode_normalized)
            with get_db_session() as session:
                crud.record_reload_log(
                    session,
                    resource="challenge_attempts",
                    mode=mode_normalized,
                    status="error",
                    message=str(exc),
                    rows=None,
                    previous_count=previous_count,
                    new_records=None,
                    total_count=None,
                    duration_seconds=duration,
                )
            raise


def load_chats() -> List[dict]:
    with get_db_session() as session:
        rows = session.execute(select(ChatModel.data)).scalars().all()
    logger.debug("Loaded %d chats from database", len(rows))
    return list(rows)


def load_challenge_attempts() -> List[dict]:
    with get_db_session() as session:
        rows = (
            session.execute(
                select(ChallengeAttemptModel).order_by(
                    ChallengeAttemptModel.chat_index, ChallengeAttemptModel.id
                )
            )
            .scalars()
            .all()
        )

    model_week_by_alias: Dict[str, str] = {}
    with get_db_session() as session:
        models = session.execute(select(ModelModel)).scalars().all()
        for model in models:
            if model.maip_week is None:
                continue
            for identifier in collect_model_identifiers(model):
                model_week_by_alias[str(identifier).lower()] = str(model.maip_week)

    attempts: List[dict] = []
    for row in rows:
        payload = {}
        if isinstance(row.payload, dict):
            payload = dict(row.payload)
        else:
            payload = {}

        payload.setdefault("attempt_id", row.id)
        payload.setdefault("chat_num", row.chat_index)
        payload.setdefault("chat_id", row.chat_id or row.id)
        payload.setdefault("user_id", row.user_id)
        payload.setdefault("model", payload.get("model") or row.mission_model)
        payload.setdefault("completed", bool(row.completed))
        payload.setdefault("message_count", payload.get("message_count") or row.message_count or 0)
        payload.setdefault("user_message_count", payload.get("user_message_count") or row.user_message_count or 0)
        payload.setdefault("created_at", payload.get("created_at") or row.started_at)
        payload.setdefault("updated_at", payload.get("updated_at") or row.updated_at_raw)

        mission_info = payload.get("mission_info")
        if not isinstance(mission_info, dict):
            mission_info = {}
            payload["mission_info"] = mission_info
        mission_info.setdefault("mission_id", row.mission_id)
        if row.mission_week is not None:
            mission_info.setdefault("week", row.mission_week)
        else:
            model_key = (row.mission_model or "").lower()
            if model_key:
                week = model_week_by_alias.get(model_key)
                if week:
                    mission_info.setdefault("week", week)

        attempts.append(payload)

    logger.debug("Loaded %d challenge attempt payloads from database", len(attempts))
    return attempts


def load_users() -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """
    Returns:
        tuple(dict, dict): (user_map, raw_data_map)
    """
    with get_db_session() as session:
        users = session.execute(select(UserModel)).scalars().all()

    user_map: Dict[str, dict] = {}
    raw_map: Dict[str, dict] = {}
    for user in users:
        user_map[user.id] = {"name": user.name or "", "email": user.email or ""}
        if isinstance(user.data, dict):
            raw_map[user.id] = user.data
        else:
            raw_map[user.id] = {}
    logger.debug("Loaded %d user records from database", len(user_map))
    return user_map, raw_map


def load_models() -> List[dict]:
    with get_db_session() as session:
        rows = session.execute(select(ModelModel)).scalars().all()

    records: List[dict] = []
    for row in rows:
        payload = deepcopy(row.data) if isinstance(row.data, dict) else {}
        payload.setdefault("id", row.id)
        if row.maip_week is not None:
            payload["maip_week"] = row.maip_week
        if row.maip_points is not None:
            payload["maip_points"] = row.maip_points
        if row.maip_difficulty is not None:
            payload["maip_difficulty"] = row.maip_difficulty
        records.append(payload)

    logger.debug("Loaded %d models from database", len(records))
    return records


def get_latest_status(resource: str | None = None) -> ReloadLog | None:
    with get_db_session() as session:
        if resource:
            log = crud.get_latest_reload(session, resource)
        else:
            log = crud.get_latest_reload_any(session)
    if log:
        logger.debug(
            "Latest reload for resource=%s -> status=%s finished_at=%s",
            resource or "any",
            log.status,
            log.finished_at,
        )
    return log


def get_row_counts() -> Dict[str, int]:
    with get_db_session() as session:
        counts = {
            "users": crud.get_row_count(session, UserModel),
            "chats": crud.get_row_count(session, ChatModel),
            "models": crud.get_row_count(session, ModelModel),
            "challenge_attempts": crud.get_row_count(session, ChallengeAttemptModel),
        }
    logger.debug("Row counts: %s", counts)
    return counts


def get_recent_logs(limit: int = 10) -> List[ReloadLog]:
    with get_db_session() as session:
        logs = crud.get_recent_logs(session, limit=limit)
    logger.debug("Fetched %d recent reload logs", len(logs))
    return logs


def record_custom_reload(
    resource: str,
    mode: str,
    status: str,
    message: str | None,
    rows: int | None,
    *,
    previous_count: int | None = None,
    new_records: int | None = None,
    total_count: int | None = None,
    duration_seconds: float | None = None,
) -> ReloadLog:
    with get_db_session() as session:
        log = crud.record_reload_log(
            session,
            resource=resource,
            mode=mode,
            status=status,
            message=message,
            rows=rows,
            previous_count=previous_count,
            new_records=new_records,
            total_count=total_count,
            duration_seconds=duration_seconds,
        )
    logger.info(
        "Recorded custom reload summary resource=%s mode=%s status=%s rows=%s total=%s duration=%.2fs",
        resource,
        mode,
        status,
        rows,
        total_count,
        duration_seconds or 0.0,
    )
    return log
