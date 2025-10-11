from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from .schemas import DashboardResponse, SortOption
from .services.dashboard import build_dashboard_response

app = FastAPI(title="Mission Dashboard API", version="1.0.0")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    sort_by: SortOption = Query(default=SortOption.completions),
    week: Optional[int] = Query(default=None, ge=1),
    challenge: Optional[int] = Query(default=None, ge=1),
    user_id: Optional[str] = Query(default=None, min_length=1),
    data_file: Optional[str] = Query(default=None),
    user_names_file: Optional[str] = Query(default=None),
) -> DashboardResponse:
    try:
        return build_dashboard_response(
            data_file=data_file,
            user_names_file=user_names_file,
            sort_by=sort_by,
            filter_week=week,
            filter_challenge=challenge,
            filter_user=user_id,
        )
    except HTTPException as exc:
        raise exc
    except Exception as exc:  # pragma: no cover - safety net for unexpected issues
        raise HTTPException(status_code=500, detail=str(exc)) from exc
