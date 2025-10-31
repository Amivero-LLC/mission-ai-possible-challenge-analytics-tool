from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .auth import models as auth_models  # noqa: F401
from .auth.dependencies import get_current_user, require_admin
from .auth.models import AuthUser
from .auth.routes import admin_router as auth_admin_router
from .auth.routes import auth_router, setup_router
from .db import Base, engine, get_engine_info
from .schemas import (
    ChallengesResponse,
    DashboardResponse,
    DatabaseStatus,
    ReloadRequest,
    ReloadRun,
    SortOption,
    UsersResponse,
)
from .services.dashboard import (
    build_challenges_response,
    build_dashboard_response,
    build_users_response,
    reload_all,
    reload_chats,
    reload_models,
    reload_users,
)
from .services.data_store import get_latest_status, get_recent_logs, get_row_counts


logger = logging.getLogger(__name__)

# FastAPI instance serves data to the analytics frontend.
app = FastAPI(title="Mission Dashboard API", version="1.0.0")

# Configure CORS to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(setup_router)
app.include_router(auth_router)
app.include_router(auth_admin_router)


def _ensure_reload_log_columns() -> None:
    info = get_engine_info()
    column_definitions = {
        "previous_count": "previous_count INTEGER",
        "new_records": "new_records INTEGER",
        "total_count": "total_count INTEGER",
        "duration_seconds": "duration_seconds FLOAT",
    }

    with engine.begin() as connection:
        for column, definition in column_definitions.items():
            if info.engine == "sqlite":
                try:
                    connection.execute(text(f"ALTER TABLE reload_logs ADD COLUMN {definition}"))
                except Exception as exc:  # pragma: no cover - best effort upgrade
                    if "duplicate column name" in str(exc).lower():
                        continue
                    logger.debug("Skipping column %s migration: %s", column, exc)
            else:
                connection.execute(text(f"ALTER TABLE reload_logs ADD COLUMN IF NOT EXISTS {definition}"))


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_reload_log_columns()

    try:
        row_counts = get_row_counts()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to determine initial row counts: %s", exc)
        row_counts = {}

    if row_counts.get("chats"):
        return

    hostname = os.getenv("OPEN_WEBUI_HOSTNAME") or os.getenv("OPEN_WEB_UI_HOSTNAME")
    api_key = os.getenv("OPEN_WEBUI_API_KEY")
    if not hostname or not api_key:
        return

    try:
        # Trigger a refresh to seed the database on first launch.
        build_dashboard_response(force_refresh=True)
    except HTTPException as exc:
        logger.warning("Startup data refresh failed: %s", exc.detail)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Startup data refresh failed: %s", exc)


def _to_reload_run(payload: Dict[str, object]) -> ReloadRun:
    return ReloadRun(
        resource=str(payload.get("resource", "unknown")),
        mode=str(payload.get("mode", "upsert")),
        status=str(payload.get("status", "success")),
        rows=payload.get("rows"),
        message=payload.get("message"),
        finished_at=payload.get("finished_at"),
        previous_count=payload.get("previous_count"),
        new_records=payload.get("new_records"),
        total_records=payload.get("total_records"),
        duration_seconds=payload.get("duration_seconds"),
    )


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/status/health")
def status_health() -> dict:
    return health_check()


@app.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    sort_by: SortOption = Query(default=SortOption.completions),
    week: Optional[str] = Query(default=None, min_length=1),
    challenge: Optional[str] = Query(default=None, min_length=1),
    user_id: Optional[str] = Query(default=None, min_length=1),
    status: Optional[str] = Query(default=None, min_length=1),
    data_file: Optional[str] = Query(default=None),
    user_names_file: Optional[str] = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
) -> DashboardResponse:
    # Delegate heavy lifting to the dashboard service while keeping HTTP layer thin.
    try:
        return build_dashboard_response(
            data_file=data_file,
            user_names_file=user_names_file,
            sort_by=sort_by,
            filter_week=week,
            filter_challenge=challenge,
            filter_user=user_id,
            filter_status=status,
        )
    except HTTPException as exc:
        raise exc
    except Exception as exc:  # pragma: no cover - safety net for unexpected issues
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/refresh")
def refresh_data(current_user: AuthUser = Depends(require_admin)) -> dict:
    """
    Force a refresh of data from Open WebUI API.

    This endpoint requires OPEN_WEBUI_HOSTNAME and OPEN_WEBUI_API_KEY to be configured.
    Returns the timestamp when data was last fetched.
    """
    hostname = os.getenv("OPEN_WEBUI_HOSTNAME") or os.getenv("OPEN_WEB_UI_HOSTNAME")
    api_key = os.getenv("OPEN_WEBUI_API_KEY")

    if not hostname or not api_key:
        raise HTTPException(
            status_code=400,
            detail="Open WebUI credentials not configured. Please set OPEN_WEBUI_HOSTNAME and OPEN_WEBUI_API_KEY environment variables."
        )

    try:
        # Call build_dashboard_response with force_refresh=True to fetch fresh data
        response = build_dashboard_response(
            sort_by=SortOption.completions,
            force_refresh=True
        )
        return {
            "status": "success",
            "message": "Data refreshed successfully",
            "last_fetched": response.last_fetched,
            "data_source": response.data_source
        }
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to refresh data: {str(exc)}") from exc


@app.get("/users", response_model=UsersResponse)
def get_users(current_user: AuthUser = Depends(get_current_user)) -> UsersResponse:
    """
    Get a list of all users with their attempted/completed challenges.

    Returns:
        UsersResponse: A list of users with detailed challenge participation information including:
            - User identification (id, name, email)
            - Overall statistics (total attempts, completions, points, efficiency)
            - Per-challenge details (status, attempts, messages, timestamps)

    Example response structure:
        {
            "generated_at": "2025-10-27T22:00:00Z",
            "users": [
                {
                    "user_id": "abc123",
                    "user_name": "John Doe",
                    "email": "john@example.com",
                    "total_attempts": 5,
                    "total_completions": 3,
                    "total_points": 150,
                    "efficiency": 60.0,
                    "challenges": [
                        {
                            "challenge_name": "Intel Guardian",
                            "challenge_id": "intel-guardian",
                            "week": "1",
                            "difficulty": "Medium",
                            "points": 50,
                            "status": "Completed",
                            "num_attempts": 2,
                            "num_messages": 15,
                            "first_attempt_time": 1234567890,
                            "completed_time": 1234567900
                        }
                    ]
                }
            ]
        }
    """
    try:
        return build_users_response()
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/challenges", response_model=ChallengesResponse)
def get_challenges(current_user: AuthUser = Depends(get_current_user)) -> ChallengesResponse:
    """
    Get a list of all challenges with users who attempted/completed them.

    Returns:
        ChallengesResponse: A list of challenges with detailed participant information including:
            - Challenge metadata (name, id, week, difficulty, points)
            - Aggregate statistics (attempts, completions, success rate)
            - User participation breakdown (attempted, completed, not started)
            - Performance metrics (avg messages/attempts to complete)
            - Per-user participation details

    Example response structure:
        {
            "generated_at": "2025-10-27T22:00:00Z",
            "challenges": [
                {
                    "challenge_name": "Intel Guardian",
                    "challenge_id": "intel-guardian",
                    "week": "1",
                    "difficulty": "Medium",
                    "points": 50,
                    "total_attempts": 15,
                    "total_completions": 8,
                    "success_rate": 53.3,
                    "users_attempted": 10,
                    "users_completed": 8,
                    "users_not_started": 5,
                    "avg_messages_to_complete": 12.5,
                    "avg_attempts_to_complete": 1.8,
                    "participants": [
                        {
                            "user_id": "abc123",
                            "user_name": "John Doe",
                            "email": "john@example.com",
                            "status": "Completed",
                            "num_attempts": 2,
                            "num_messages": 15,
                            "first_attempt_time": 1234567890,
                            "completed_time": 1234567900
                        }
                    ]
                }
            ]
        }
    """
    try:
        return build_challenges_response()
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/admin/db/status", response_model=DatabaseStatus)
def get_database_status(current_user: AuthUser = Depends(require_admin)) -> DatabaseStatus:
    """Return metadata about the configured database and recent reload activity."""
    info = get_engine_info()
    row_counts = get_row_counts()
    latest = get_latest_status()
    last_update = latest.finished_at if latest and latest.finished_at else None
    last_duration = latest.duration_seconds if latest else None

    logs = get_recent_logs(limit=20)

    deduped: Dict[tuple[str, str], ReloadRun] = {}
    for log in logs:
        key = (log.resource, log.mode)
        if key in deduped:
            continue
        deduped[key] = ReloadRun(
            resource=log.resource,
            mode=log.mode,
            status=log.status,
            rows=log.rows_affected,
            message=log.message,
            finished_at=log.finished_at,
            previous_count=log.previous_count,
            new_records=log.new_records,
            total_records=log.total_count,
            duration_seconds=log.duration_seconds,
        )

    runs = list(deduped.values())

    return DatabaseStatus(
        engine=info.engine,
        row_counts=row_counts,
        last_update=last_update,
        last_duration_seconds=last_duration,
        recent_runs=runs,
    )


@app.post("/admin/db/reload", response_model=List[ReloadRun])
def reload_all_resources(
    options: ReloadRequest = Body(default=ReloadRequest()),
    current_user: AuthUser = Depends(require_admin),
) -> List[ReloadRun]:
    results = reload_all(mode=options.mode)
    return [_to_reload_run(item) for item in results]


@app.post("/admin/db/reload/users", response_model=ReloadRun)
def reload_users_resource(
    options: ReloadRequest = Body(default=ReloadRequest()),
    current_user: AuthUser = Depends(require_admin),
) -> ReloadRun:
    result = reload_users(mode=options.mode)
    return _to_reload_run(result)


@app.post("/admin/db/reload/chats", response_model=ReloadRun)
def reload_chats_resource(
    options: ReloadRequest = Body(default=ReloadRequest()),
    current_user: AuthUser = Depends(require_admin),
) -> ReloadRun:
    result = reload_chats(mode=options.mode)
    return _to_reload_run(result)


@app.post("/admin/db/reload/models", response_model=ReloadRun)
def reload_models_resource(
    options: ReloadRequest = Body(default=ReloadRequest()),
    current_user: AuthUser = Depends(require_admin),
) -> ReloadRun:
    result = reload_models(mode=options.mode)
    return _to_reload_run(result)
