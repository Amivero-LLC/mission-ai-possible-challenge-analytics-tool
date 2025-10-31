from __future__ import annotations

from time import perf_counter
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import select

from ..db import get_db_session
from ..db import crud
from ..db.models import Chat as ChatModel
from ..db.models import Model as ModelModel
from ..db.models import ReloadLog
from ..db.models import User as UserModel


def persist_chats(records: Iterable[dict], mode: str = "upsert") -> int:
    start_time = perf_counter()
    previous_count = None
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
            return rows
    except Exception as exc:
        duration = perf_counter() - start_time
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
            return rows
    except Exception as exc:
        duration = perf_counter() - start_time
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
            return rows
    except Exception as exc:
        duration = perf_counter() - start_time
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
    return user_map, raw_map


def load_models() -> List[dict]:
    with get_db_session() as session:
        rows = session.execute(select(ModelModel.data)).scalars().all()
    return list(rows)


def get_latest_status(resource: str | None = None) -> ReloadLog | None:
    with get_db_session() as session:
        if resource:
            return crud.get_latest_reload(session, resource)
        return crud.get_latest_reload_any(session)


def get_row_counts() -> Dict[str, int]:
    with get_db_session() as session:
        return {
            "users": crud.get_row_count(session, UserModel),
            "chats": crud.get_row_count(session, ChatModel),
            "models": crud.get_row_count(session, ModelModel),
        }


def get_recent_logs(limit: int = 10) -> List[ReloadLog]:
    with get_db_session() as session:
        return crud.get_recent_logs(session, limit=limit)


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
        return crud.record_reload_log(
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
