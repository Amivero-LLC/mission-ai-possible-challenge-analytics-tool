from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests
from fastapi import HTTPException

# Ensure project root is importable when backend runs as a module
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from .mission_analyzer import DATA_DIR, MissionAnalyzer, find_latest_export  # noqa: E402

from ..schemas import (
    ChatMessage,
    ChatPreview,
    DashboardResponse,
    LeaderboardEntry,
    MissionBreakdownEntry,
    ModelStatsEntry,
    SortOption,
    Summary,
)


def _fetch_remote_chats() -> Optional[List[dict]]:
    """Pull latest chats from OpenWebUI when hostname/key env vars are configured."""
    hostname = os.getenv("OPEN_WEBUI_HOSTNAME") or os.getenv("OPEN_WEB_UI_HOSTNAME")
    api_key = os.getenv("OPEN_WEBUI_API_KEY")

    if not hostname or not api_key:
        return None

    url = f"{hostname.rstrip('/')}/api/v1/chats/all/db"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:  # pragma: no cover - network failure
        raise HTTPException(status_code=502, detail=f"Failed to fetch chats from OpenWebUI: {exc}") from exc

    data = response.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Unexpected response format from OpenWebUI")

    return data


def _fetch_remote_users() -> Optional[Dict[str, str]]:
    # Mirrors chat fetch logic but normalizes user metadata for display names.
    hostname = os.getenv("OPEN_WEBUI_HOSTNAME") or os.getenv("OPEN_WEB_UI_HOSTNAME")
    api_key = os.getenv("OPEN_WEBUI_API_KEY")

    if not hostname or not api_key:
        return None

    url = f"{hostname.rstrip('/')}/api/v1/users/all"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Failed to fetch users from OpenWebUI: {exc}") from exc

    payload = response.json()
    if isinstance(payload, dict):
        if "users" in payload and isinstance(payload["users"], list):
            payload = payload["users"]
        elif "data" in payload and isinstance(payload["data"], list):
            payload = payload["data"]
        else:
            raise HTTPException(status_code=502, detail="Unexpected users response format from OpenWebUI")
    elif not isinstance(payload, list):
        raise HTTPException(status_code=502, detail="Unexpected users response format from OpenWebUI")

    user_map: Dict[str, str] = {}
    for item in payload:
        user_id = item.get("id")
        if not user_id:
            continue
        name = item.get("name") or ""
        email = item.get("email") or ""
        display = name.strip() or (email.split("@")[0] if email else user_id[:8])
        user_map[user_id] = display

    return user_map


def _pick_data_file(explicit_file: Optional[str]) -> str:
    # Fallback to auto-discovered export when caller does not supply a path.
    if explicit_file:
        return explicit_file
    latest = find_latest_export()
    if not latest:
        raise HTTPException(status_code=404, detail="No chat export files found")
    return latest


def _build_chat_previews(analyzer: MissionAnalyzer) -> List[ChatPreview]:
    """Transform analyzer results into lightweight cards for the frontend."""
    mission_lookup: Dict[int, Dict] = {chat["chat_num"]: chat for chat in analyzer.mission_chats}
    previews: List[ChatPreview] = []

    for index, item in enumerate(analyzer.data, start=1):
        chat = item.get("chat", {})
        models: Iterable[str] = chat.get("models", [])
        messages: List[dict] = chat.get("messages", [])

        mission_chat = mission_lookup.get(index)
        is_mission = mission_chat is not None
        completed = mission_chat["completed"] if mission_chat else False

        user_id = item.get("user_id", "Unknown")
        previews.append(
            ChatPreview(
                num=index,
                title=item.get("title", "Untitled"),
                user_id=user_id,
                user_name=analyzer.get_user_name(user_id),
                created_at=item.get("created_at"),
                model=next(iter(models), "Unknown"),
                message_count=len(messages),
                is_mission=is_mission,
                completed=completed,
                messages=[
                    ChatMessage(role=msg.get("role"), content=msg.get("content"))
                    for msg in messages[:3]
                ],
            )
        )

    return previews


def _build_model_stats(chats: List[ChatPreview]) -> List[ModelStatsEntry]:
    """Aggregate mission/model counts used to render the model stats tab."""
    stats: Dict[str, Dict[str, int]] = {}
    for chat in chats:
        model_stat = stats.setdefault(chat.model, {"total": 0, "mission": 0, "completed": 0})
        model_stat["total"] += 1
        if chat.is_mission:
            model_stat["mission"] += 1
        if chat.completed:
            model_stat["completed"] += 1

    result: List[ModelStatsEntry] = []
    for model, values in stats.items():
        total = values["total"]
        mission = values["mission"]
        completed = values["completed"]
        mission_percentage = (mission / total * 100) if total else 0.0
        result.append(
            ModelStatsEntry(
                model=model,
                total=total,
                mission=mission,
                completed=completed,
                mission_percentage=mission_percentage,
            )
        )
    return sorted(result, key=lambda entry: entry.total, reverse=True)


def _decorate_leaderboard(
    analyzer: MissionAnalyzer, raw_leaderboard: List[dict]
) -> List[LeaderboardEntry]:
    # Enrich raw metrics with display-friendly user names.
    entries: List[LeaderboardEntry] = []
    for item in raw_leaderboard:
        user_id = item["user_id"]
        entries.append(
            LeaderboardEntry(
                user_id=user_id,
                user_name=analyzer.get_user_name(user_id),
                attempts=item["attempts"],
                completions=item["completions"],
                efficiency=item["efficiency"],
                total_messages=item["total_messages"],
                unique_missions_attempted=item["unique_missions_attempted"],
                unique_missions_completed=item["unique_missions_completed"],
            )
        )
    return entries


def _decorate_summary(analyzer: MissionAnalyzer, raw_summary: dict) -> Summary:
    participation_rate = (
        raw_summary["unique_users"] / raw_summary["total_chats"] * 100
        if raw_summary["total_chats"]
        else 0.0
    )
    return Summary(
        total_chats=raw_summary["total_chats"],
        mission_attempts=raw_summary["mission_attempts"],
        mission_completions=raw_summary["mission_completions"],
        success_rate=raw_summary["success_rate"],
        unique_users=raw_summary["unique_users"],
        unique_missions=raw_summary["unique_missions"],
        missions_list=raw_summary["missions_list"],
        participation_rate=participation_rate,
    )


def _decorate_mission_breakdown(mission_breakdown: List[dict]) -> List[MissionBreakdownEntry]:
    return [
        MissionBreakdownEntry(
            mission=item["mission"],
            attempts=item["attempts"],
            completions=item["completions"],
            success_rate=item["success_rate"],
            unique_users=item["unique_users"],
        )
        for item in mission_breakdown
    ]


def build_dashboard_response(
    *,
    data_file: Optional[str] = None,
    user_names_file: Optional[str] = None,
    sort_by: SortOption = SortOption.completions,
    filter_week: Optional[int] = None,
    filter_challenge: Optional[int] = None,
    filter_user: Optional[str] = None,
) -> DashboardResponse:
    # Resolve user names file relative to DATA_DIR by default
    resolved_user_names = user_names_file or str(Path(DATA_DIR) / "user_names.json")

    remote_chats = _fetch_remote_chats()
    if remote_chats is not None:
        # Prefer live data when OpenWebUI is reachable; fall back to static exports otherwise.
        remote_users = _fetch_remote_users() or {}
        analyzer = MissionAnalyzer(
            json_file=None,
            data=remote_chats,
            user_names_file=resolved_user_names,
            user_names=remote_users,
            verbose=False,
        )
    else:
        resolved_data_file = _pick_data_file(data_file)
        analyzer = MissionAnalyzer(
            resolved_data_file,
            user_names_file=resolved_user_names,
            verbose=False,
        )

    analyzer.analyze_missions(
        filter_week=filter_week,
        filter_challenge=filter_challenge,
        filter_user=filter_user,
    )

    # Compose the response sections in the order expected by the frontend.
    summary = _decorate_summary(analyzer, analyzer.get_summary())
    leaderboard = _decorate_leaderboard(analyzer, analyzer.get_leaderboard(sort_by=sort_by.value))
    missions = _decorate_mission_breakdown(analyzer.get_mission_breakdown())
    chats = _build_chat_previews(analyzer)
    model_stats = _build_model_stats(chats)

    return DashboardResponse(
        generated_at=datetime.now(timezone.utc),
        summary=summary,
        leaderboard=leaderboard,
        mission_breakdown=missions,
        all_chats=chats,
        model_stats=model_stats,
    )
