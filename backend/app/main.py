from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .schemas import ChallengesResponse, DashboardResponse, SortOption, UsersResponse
from .services.dashboard import (
    build_challenges_response,
    build_dashboard_response,
    build_users_response,
)

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


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    sort_by: SortOption = Query(default=SortOption.completions),
    week: Optional[str] = Query(default=None, min_length=1),
    challenge: Optional[str] = Query(default=None, min_length=1),
    user_id: Optional[str] = Query(default=None, min_length=1),
    status: Optional[str] = Query(default=None, min_length=1),
    data_file: Optional[str] = Query(default=None),
    user_names_file: Optional[str] = Query(default=None),
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
def refresh_data() -> dict:
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
def get_users() -> UsersResponse:
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
def get_challenges() -> ChallengesResponse:
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
