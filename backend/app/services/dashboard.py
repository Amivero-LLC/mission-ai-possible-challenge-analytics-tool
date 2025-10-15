from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

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


# Cache file paths
USERS_CACHE_FILE = Path(DATA_DIR) / "users.json"
MODELS_CACHE_FILE = Path(DATA_DIR) / "models.json"


def _load_json_cache(file_path: Path) -> Optional[List[dict]]:
    """Load data from a JSON cache file if it exists."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, list) else None
    except (json.JSONDecodeError, IOError):
        return None


def _save_json_cache(file_path: Path, data: List[dict]) -> None:
    """Save data to a JSON cache file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def _merge_and_update_cache(
    file_path: Path,
    new_records: List[dict],
    id_key: str = "id"
) -> List[dict]:
    """
    Merge new records with existing cache, updating existing records by ID.

    Args:
        file_path: Path to the cache file
        new_records: List of new records to merge
        id_key: The key to use for identifying unique records

    Returns:
        The merged list of records
    """
    existing = _load_json_cache(file_path) or []
    existing_map = {record.get(id_key): record for record in existing if record.get(id_key)}

    # Update existing records and add new ones
    for record in new_records:
        record_id = record.get(id_key)
        if record_id:
            existing_map[record_id] = record

    merged = list(existing_map.values())
    _save_json_cache(file_path, merged)
    return merged


def _extract_model_metadata(records: Iterable[dict]) -> Tuple[Dict[str, str], Set[str], Dict[str, str]]:
    """
    Normalize a sequence of model records into lookup maps and mission classifications.

    Args:
        records (Iterable[dict]): Raw model objects returned by OpenWebUI or loaded
            from the bundled sample export.

    Returns:
        tuple:
            - dict[str, str]: Mapping of ``model_alias -> friendly_name``.
            - set[str]: Aliases flagged with the ``Missions`` tag (case-insensitive).
            - dict[str, str]: Mapping of ``model_alias -> canonical_id`` used for mission matching.
    """
    lookup: Dict[str, str] = {}
    mission_aliases: Set[str] = set()
    alias_to_primary: Dict[str, str] = {}

    for item in records:
        if not isinstance(item, dict):
            continue

        # Handle production data format with model_id and raw fields
        if "model_id" in item and "raw" in item:
            raw = item.get("raw", {})
            if isinstance(raw, dict):
                # Use raw data as the source
                item = raw

        identifiers: Set[str] = set()

        def add_identifier(value: Optional[str]) -> None:
            if value is None:
                return
            # Skip non-string values (e.g., boolean True from preset field)
            if not isinstance(value, str):
                return
            text = value.strip()
            if not text:
                return
            identifiers.add(text)

        # Gather identifiers from top level fields.
        for key in ("id", "slug", "model", "preset", "name", "display_name", "displayName", "model_id"):
            add_identifier(item.get(key))

        # Include identifiers defined within nested metadata blocks.
        meta = item.get("meta")
        if isinstance(meta, dict):
            for key in ("id", "slug", "model", "preset", "name"):
                add_identifier(meta.get(key))

        info = item.get("info")
        if isinstance(info, dict):
            for key in ("id", "slug", "model", "preset", "name"):
                add_identifier(info.get(key))
            info_meta = info.get("meta")
            if isinstance(info_meta, dict):
                for key in ("id", "slug", "model", "preset", "name"):
                    add_identifier(info_meta.get(key))

        if not identifiers:
            continue

        # Pick a canonical identifier that retains mission context when available (prefer slugs/presets).
        # Filter out non-string values like boolean True
        preferred_order = (
            item.get("slug"),
            item.get("model"),
            item.get("preset"),
            info.get("slug") if isinstance(info, dict) else None,
            info.get("model") if isinstance(info, dict) else None,
            info.get("preset") if isinstance(info, dict) else None,
            item.get("id"),
            info.get("id") if isinstance(info, dict) else None,
        )
        primary_id = next((str(value) for value in preferred_order if value and isinstance(value, str)), None)
        if not primary_id:
            primary_id = next(iter(identifiers))

        identifiers.add(primary_id)

        name = item.get("name")
        if not name and isinstance(info, dict):
            name = info.get("name")
        if not name and isinstance(meta, dict):
            name = meta.get("name")
        display_name = str(name or primary_id)

        tags: List[str] = []
        for candidate in (
            item.get("tags"),
            meta.get("tags") if isinstance(meta, dict) else None,
            (
                info.get("meta", {}).get("tags")
                if isinstance(info, dict)
                and isinstance(info.get("meta"), dict)
                else None
            ),
        ):
            if isinstance(candidate, list):
                for tag in candidate:
                    if tag:
                        # Handle both string tags and dict tags with "name" property
                        if isinstance(tag, dict):
                            tag_name = tag.get("name")
                            if tag_name:
                                tags.append(str(tag_name))
                        elif isinstance(tag, str):
                            # Only add string tags, skip boolean or other types
                            tags.append(tag)

        for identifier in identifiers:
            lookup[identifier] = display_name
            alias_to_primary[identifier] = primary_id

        if any(tag.lower() == "missions" for tag in tags):
            mission_aliases.update(identifiers)

    return lookup, mission_aliases, alias_to_primary


def _read_cached_users() -> Optional[Dict[str, str]]:
    """Read users from the cache file and return as a user_id -> name mapping."""
    cached_users = _load_json_cache(USERS_CACHE_FILE)
    if not cached_users:
        return None

    user_map: Dict[str, str] = {}
    for user in cached_users:
        user_id = user.get("user_id")
        name = user.get("name")
        if user_id and name:
            user_map[user_id] = name

    return user_map if user_map else None


def _read_cached_models() -> Optional[Tuple[Dict[str, str], Set[str], Dict[str, str]]]:
    """Read models from the cache file and extract metadata."""
    cached_models = _load_json_cache(MODELS_CACHE_FILE)
    if not cached_models:
        return None

    return _extract_model_metadata(cached_models)


def _load_model_metadata(model_file: Optional[str] = None) -> Tuple[Dict[str, str], Set[str], Dict[str, str]]:
    """
    Build lookup tables for model names and mission classification.

    Fetches live data from the OpenWebUI API, falling back to cache if unavailable.
    """
    remote_metadata = _fetch_remote_models()
    if remote_metadata is not None:
        return remote_metadata

    # Fall back to cached models if API is unavailable
    cached_metadata = _read_cached_models()
    if cached_metadata is not None:
        return cached_metadata

    # Return empty lookups if both API and cache are unavailable
    return {}, set(), {}


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

    # Normalize user records for caching
    user_records = []
    user_map: Dict[str, str] = {}
    for item in payload:
        user_id = item.get("id")
        if not user_id:
            continue
        name = item.get("name") or ""
        email = item.get("email") or ""
        display = name.strip() or (email.split("@")[0] if email else user_id[:8])
        user_map[user_id] = display

        # Store normalized user record for cache
        user_records.append({
            "user_id": user_id,
            "name": display,
            "email": email
        })

    # Save/update cache
    _merge_and_update_cache(USERS_CACHE_FILE, user_records, id_key="user_id")

    return user_map


def _fetch_remote_models() -> Optional[Tuple[Dict[str, str], Set[str], Dict[str, str]]]:
    """Retrieve model metadata from OpenWebUI to translate model IDs into names."""
    hostname = os.getenv("OPEN_WEBUI_HOSTNAME") or os.getenv("OPEN_WEB_UI_HOSTNAME")
    api_key = os.getenv("OPEN_WEBUI_API_KEY")

    if not hostname or not api_key:
        return None

    url = f"{hostname.rstrip('/')}/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    payload = response.json()
    if isinstance(payload, dict):
        records = payload.get("data") or payload.get("models") or []
    elif isinstance(payload, list):
        records = payload
    else:
        return None

    # Save/update cache - store the raw records
    if records:
        _merge_and_update_cache(MODELS_CACHE_FILE, list(records), id_key="id")

    return _extract_model_metadata(records)


def _pick_data_file(explicit_file: Optional[str]) -> str:
    # Fallback to auto-discovered export when caller does not supply a path.
    if explicit_file:
        return explicit_file
    latest = find_latest_export()
    if not latest:
        raise HTTPException(status_code=404, detail="No chat export files found")
    return latest


def _build_chat_previews(
    analyzer: MissionAnalyzer,
    filter_challenge: Optional[str] = None,
    filter_user: Optional[str] = None,
    filter_status: Optional[str] = None,
    filter_date_from: Optional[str] = None,
    filter_date_to: Optional[str] = None,
    model_lookup: Optional[Dict[str, str]] = None,
) -> List[ChatPreview]:
    """Transform analyzer results into lightweight cards for the frontend, applying filters."""
    mission_lookup: Dict[int, Dict] = {chat["chat_num"]: chat for chat in analyzer.mission_chats}
    previews: List[ChatPreview] = []
    model_lookup = model_lookup or {}

    # Parse date filters if provided
    date_from_ts = None
    date_to_ts = None
    if filter_date_from:
        try:
            from datetime import datetime as dt
            date_from_ts = int(dt.fromisoformat(filter_date_from).timestamp())
        except (ValueError, AttributeError):
            pass
    if filter_date_to:
        try:
            from datetime import datetime as dt
            # Add 23:59:59 to include the entire day
            date_to_ts = int(dt.fromisoformat(filter_date_to + "T23:59:59").timestamp())
        except (ValueError, AttributeError):
            pass

    for index, item in enumerate(analyzer.data, start=1):
        chat = item.get("chat", {})
        models: Iterable[str] = chat.get("models", [])
        messages: List[dict] = chat.get("messages", [])
        user_id = item.get("user_id", "Unknown")
        created_at = item.get("created_at")

        # Check if this chat is a mission
        mission_chat = mission_lookup.get(index)
        is_mission = mission_chat is not None
        completed = mission_chat["completed"] if mission_chat else False

        # Apply user filter
        if filter_user and user_id != filter_user:
            continue

        # Apply date filter
        if date_from_ts or date_to_ts:
            chat_timestamp = created_at if isinstance(created_at, (int, float)) else None
            if chat_timestamp:
                if date_from_ts and chat_timestamp < date_from_ts:
                    continue
                if date_to_ts and chat_timestamp > date_to_ts:
                    continue

        # For mission-specific filters, check if it's a mission chat
        if is_mission and mission_chat:
            mission_info = mission_chat["mission_info"]
            mission_model = mission_chat["model"]

            if filter_challenge and not analyzer._mission_matches_filter(mission_model, filter_challenge):
                continue
            if filter_status:
                if filter_status.lower() == "completed" and not completed:
                    continue
                elif filter_status.lower() == "attempted" and completed:
                    continue
        else:
            # If filters are applied but this is not a mission chat, skip it
            if filter_challenge or filter_status:
                continue

        # Resolve a user-friendly model name using the lookup map. Falls back to the raw
        # identifier when no metadata is available.
        display_model = "Unknown"
        raw_model = "Unknown"
        for entry in models:
            candidate_id = None
            candidate_name = None
            if isinstance(entry, str):
                candidate_id = entry
            elif isinstance(entry, dict):
                candidate_id = entry.get("id") or entry.get("model") or entry.get("slug")
                candidate_name = entry.get("name") or entry.get("display_name")
            if candidate_id:
                raw_model = candidate_id
                display_model = model_lookup.get(candidate_id) or candidate_name or candidate_id
                break

        if display_model == "Unknown" and messages:
            for msg in messages:
                candidate = msg.get("model")
                candidate_name = msg.get("modelName") or msg.get("model_name")
                if candidate:
                    raw_model = candidate
                    display_model = model_lookup.get(candidate) or candidate_name or candidate
                    break

        previews.append(
            ChatPreview(
                num=index,
                title=item.get("title", "Untitled"),
                user_id=user_id,
                user_name=analyzer.get_user_name(user_id),
                created_at=item.get("created_at"),
                model=display_model if display_model != "Unknown" else model_lookup.get(raw_model, raw_model),
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
        weeks_list=raw_summary.get("weeks_list", []),
        users_list=raw_summary.get("users_list", []),
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
    filter_date_from: Optional[str] = None,
    filter_date_to: Optional[str] = None,
    filter_challenge: Optional[str] = None,
    filter_user: Optional[str] = None,
    filter_status: Optional[str] = None,
) -> DashboardResponse:
    # Resolve user names file relative to DATA_DIR by default
    resolved_user_names = user_names_file or str(Path(DATA_DIR) / "user_names.json")

    model_lookup, mission_model_aliases, alias_to_primary = _load_model_metadata()

    remote_chats = _fetch_remote_chats()
    if remote_chats is not None:
        # Prefer live data when OpenWebUI is reachable; fall back to cached data otherwise.
        remote_users = _fetch_remote_users()
        if remote_users is None:
            # Fall back to cached users if API is unavailable
            remote_users = _read_cached_users() or {}

        analyzer = MissionAnalyzer(
            json_file=None,
            data=remote_chats,
            user_names_file=resolved_user_names,
            user_names=remote_users,
            model_lookup=model_lookup,
            mission_model_aliases=mission_model_aliases,
            model_alias_to_primary=alias_to_primary,
            verbose=False,
        )
    else:
        resolved_data_file = _pick_data_file(data_file)
        analyzer = MissionAnalyzer(
            resolved_data_file,
            user_names_file=resolved_user_names,
            model_lookup=model_lookup,
            mission_model_aliases=mission_model_aliases,
            model_alias_to_primary=alias_to_primary,
            verbose=False,
        )

    analyzer.analyze_missions(
        filter_challenge=filter_challenge,
        filter_user=filter_user,
        filter_status=filter_status,
        filter_date_from=filter_date_from,
        filter_date_to=filter_date_to,
    )

    # Compose the response sections in the order expected by the frontend.
    summary = _decorate_summary(analyzer, analyzer.get_summary())
    leaderboard = _decorate_leaderboard(analyzer, analyzer.get_leaderboard(sort_by=sort_by.value))
    missions = _decorate_mission_breakdown(analyzer.get_mission_breakdown())
    chats = _build_chat_previews(
        analyzer,
        filter_challenge=filter_challenge,
        filter_user=filter_user,
        filter_status=filter_status,
        filter_date_from=filter_date_from,
        filter_date_to=filter_date_to,
        model_lookup=model_lookup,
    )
    model_stats = _build_model_stats(chats)

    return DashboardResponse(
        generated_at=datetime.now(timezone.utc),
        summary=summary,
        leaderboard=leaderboard,
        mission_breakdown=missions,
        all_chats=chats,
        model_stats=model_stats,
    )
