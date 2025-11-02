from __future__ import annotations

import logging
from time import perf_counter
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import select

from ..db import crud
from ..db import get_db_session
from ..db.models import Chat as ChatModel
from ..db.models import Model as ModelModel
from ..db.models import ReloadLog
from ..db.models import User as UserModel


logger = logging.getLogger(__name__)


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


def load_chats() -> List[dict]:
    with get_db_session() as session:
        rows = session.execute(select(ChatModel.data)).scalars().all()
    logger.debug("Loaded %d chats from database", len(rows))
    return list(rows)


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
        rows = session.execute(select(ModelModel.data)).scalars().all()
    logger.debug("Loaded %d models from database", len(rows))
    return list(rows)


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
