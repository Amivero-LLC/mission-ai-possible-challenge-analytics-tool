from __future__ import annotations

import json
import logging
import os
import sys
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import requests
from fastapi import HTTPException

from .data_store import (
    get_latest_status,
    record_custom_reload,
    load_challenge_attempts,
    load_chats,
    load_models,
    load_users,
    persist_challenge_attempts,
    persist_chats,
    persist_models,
    persist_users,
)

# Ensure project root is importable when backend runs as a module
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from .mission_analyzer import DATA_DIR, MissionAnalyzer, find_latest_export  # noqa: E402

from ..schemas import (
    ChallengeAttempt,
    ChallengeAttemptRecord,
    ChallengeResultEntry,
    ChallengesResponse,
    ChallengeWithUsers,
    ChatMessage,
    ChatPreview,
    DashboardResponse,
    LeaderboardEntry,
    MissionBreakdownEntry,
    MissionDetail,
    SortOption,
    Summary,
    UserChallengeExportRow,
    UserParticipation,
    UsersResponse,
    UserWithChallenges,
)


logger = logging.getLogger(__name__)


@dataclass
class MissionAnalysisContext:
    analyzer: MissionAnalyzer
    data_source: str
    user_info_map: Dict[str, dict]
    model_lookup: Dict[str, str]
    mission_model_aliases: Set[str]
    alias_to_primary: Dict[str, str]
    week_mapping: Dict[str, str]
    points_mapping: Dict[str, int]
    difficulty_mapping: Dict[str, str]


def _normalize_to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure timestamps are timezone-aware UTC datetimes for consistent serialization."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_model_metadata(records: Iterable[dict]) -> Tuple[Dict[str, str], Set[str], Dict[str, str], Dict[str, str], Dict[str, int], Dict[str, str]]:
    """
    Normalize a sequence of model records into lookup maps and mission classifications.
    Only processes models with the "Missions" tag.

    Args:
        records (Iterable[dict]): Raw model objects returned by OpenWebUI or loaded
            from the bundled sample export.

    Returns:
        tuple:
            - dict[str, str]: Mapping of ``model_alias -> friendly_name`` (mission models only).
            - set[str]: Aliases flagged with the ``Missions`` tag (case-insensitive).
            - dict[str, str]: Mapping of ``model_alias -> canonical_id`` used for mission matching.
            - dict[str, str]: Mapping of ``model_alias -> maip_week`` value.
            - dict[str, int]: Mapping of ``model_alias -> maip_points_value`` (int).
            - dict[str, str]: Mapping of ``model_alias -> maip_difficulty_level`` value.
    """
    lookup: Dict[str, str] = {}
    mission_aliases: Set[str] = set()
    alias_to_primary: Dict[str, str] = {}
    week_mapping: Dict[str, str] = {}
    points_mapping: Dict[str, int] = {}
    difficulty_mapping: Dict[str, str] = {}

    for item in records:
        if not isinstance(item, dict):
            continue

        # Capture top-level model_id before processing raw data
        top_level_model_id = item.get("id") or item.get("model_id")

        # Handle production data format with model_id and raw fields
        if "model_id" in item and "raw" in item:
            raw = item.get("raw", {})
            if isinstance(raw, dict):
                # Use raw data as the source
                item = raw

        identifiers: Set[str] = set()

        # Add top-level model_id to identifiers if present
        if top_level_model_id and isinstance(top_level_model_id, str):
            identifiers.add(top_level_model_id.strip())

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

        # Extract maip_week, maip_points_value, and maip_difficulty_level from custom_params if present
        maip_week = None
        maip_points = None
        maip_difficulty = None

        # Check params.custom_params
        params = item.get("params")
        if isinstance(params, dict):
            custom_params = params.get("custom_params")
            if isinstance(custom_params, dict):
                maip_week = custom_params.get("maip_week")
                maip_points = custom_params.get("maip_points_value")
                maip_difficulty = custom_params.get("maip_difficulty_level")

        # Also check info.params.custom_params
        if not maip_week or not maip_points or not maip_difficulty:
            info = item.get("info")
            if isinstance(info, dict):
                info_params = info.get("params")
                if isinstance(info_params, dict):
                    custom_params = info_params.get("custom_params")
                    if isinstance(custom_params, dict):
                        if not maip_week:
                            maip_week = custom_params.get("maip_week")
                        if not maip_points:
                            maip_points = custom_params.get("maip_points_value")
                        if not maip_difficulty:
                            maip_difficulty = custom_params.get("maip_difficulty_level")

        # Only process models with the "Missions" tag
        has_missions_tag = any(tag.lower() == "missions" for tag in tags)
        if not has_missions_tag:
            continue

        # This model has the Missions tag, so add it to our lookups
        mission_aliases.update(identifiers)

        for identifier in identifiers:
            lookup[identifier] = display_name
            alias_to_primary[identifier] = primary_id
            if maip_week:
                week_mapping[identifier] = str(maip_week)
            if maip_points:
                try:
                    points_mapping[identifier] = int(maip_points)
                except (ValueError, TypeError):
                    pass  # Skip invalid point values
            if maip_difficulty:
                difficulty_mapping[identifier] = str(maip_difficulty)

    return lookup, mission_aliases, alias_to_primary, week_mapping, points_mapping, difficulty_mapping

def _load_model_metadata(
    *,
    force_refresh: bool = False,
    mode: str = "upsert",
) -> Tuple[Dict[str, str], Set[str], Dict[str, str], Dict[str, str], Dict[str, int], Dict[str, str]]:
    """
    Build lookup tables for model names and mission classification.

    Order of precedence:
        1. Fresh API payload when ``force_refresh`` is True and credentials are configured.
        2. Persisted database rows.
    """
    records: List[dict] = []
    logger.debug("Loading model metadata (force_refresh=%s, mode=%s)", force_refresh, mode)

    if force_refresh:
        remote_records = _fetch_remote_models()
        if remote_records:
            persist_models(remote_records, mode=mode)
            records = remote_records
            logger.info("Loaded %d models from OpenWebUI API (force refresh)", len(remote_records))

    if not records:
        records = load_models()
        if records:
            logger.debug("Loaded %d models from database cache", len(records))

    if not records:
        logger.warning(
            "No model metadata available in cache; skip automatic OpenWebUI fetch and wait for manual reload."
        )
        return {}, set(), {}, {}, {}, {}

    metadata = _extract_model_metadata(records)
    logger.debug(
        "Extracted model metadata with %d aliases and %d mission-tagged models",
        len(metadata[0]),
        len(metadata[1]),
    )
    return metadata


def _fetch_remote_chats() -> Optional[List[dict]]:
    """Pull latest chats from OpenWebUI when hostname/key env vars are configured."""
    hostname = os.getenv("OPEN_WEBUI_HOSTNAME") or os.getenv("OPEN_WEB_UI_HOSTNAME")
    api_key = os.getenv("OPEN_WEBUI_API_KEY")

    if not hostname or not api_key:
        logger.debug("Skipping remote chat fetch; credentials not configured")
        return None

    url = f"{hostname.rstrip('/')}/api/v1/chats/all/db"
    headers = {"Authorization": f"Bearer {api_key}"}
    logger.debug("Requesting chats from OpenWebUI at %s", url)
    start_time = perf_counter()

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch chats from OpenWebUI: {exc}") from exc
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        logger.warning("OpenWebUI chats fetch failed (%s); falling back to local exports", exc)
        return None
    except requests.exceptions.RequestException as exc:  # pragma: no cover - network failure
        logger.warning("OpenWebUI chats fetch failed (%s); falling back to local exports", exc)
        return None

    data = response.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Unexpected response format from OpenWebUI")

    duration = perf_counter() - start_time
    logger.info("Fetched %d chats from OpenWebUI in %.2fs", len(data), duration)

    return data


def _filter_chats_by_mission_models(chats: List[dict], mission_model_aliases: Set[str]) -> List[dict]:
    """
    Filter chats to only include those using models with the "Missions" tag.

    Args:
        chats: List of chat records
        mission_model_aliases: Set of model identifiers that have the "Missions" tag

    Returns:
        Filtered list of chats that use mission models
    """
    if not mission_model_aliases:
        return []

    filtered_chats = []
    mission_aliases_lower = {alias.lower() for alias in mission_model_aliases}

    for chat in chats:
        if not isinstance(chat, dict):
            continue

        # Check the chat's models field
        chat_data = chat.get("chat", {})
        models = chat_data.get("models", [])

        # Check if any model in this chat is a mission model
        is_mission_chat = False
        for model in models:
            model_id = None
            if isinstance(model, str):
                model_id = model
            elif isinstance(model, dict):
                model_id = model.get("id") or model.get("model") or model.get("slug")

            if model_id and model_id.lower() in mission_aliases_lower:
                is_mission_chat = True
                break

        # Also check messages for model references
        if not is_mission_chat:
            messages = chat_data.get("messages", [])
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                msg_model = msg.get("model")
                if msg_model and msg_model.lower() in mission_aliases_lower:
                    is_mission_chat = True
                    break

        if is_mission_chat:
            filtered_chats.append(chat)

    return filtered_chats


def _build_challenge_attempt_records(attempt_payloads: List[dict]) -> List[dict]:
    """
    Normalize MissionAnalyzer payloads so they can be persisted in SQLite.
    """
    records: List[dict] = []
    for payload in attempt_payloads:
        attempt_id = payload.get("attempt_id")
        if not attempt_id:
            continue
        mission_info = payload.get("mission_info") or {}
        week_val = mission_info.get("week")
        sanitized_payload = json.loads(json.dumps(payload))
        records.append(
            {
                "id": attempt_id,
                "chat_id": payload.get("chat_id"),
                "chat_index": payload.get("chat_num") or 0,
                "user_id": payload.get("user_id"),
                "mission_id": mission_info.get("mission_id"),
                "mission_model": payload.get("model"),
                "mission_week": str(week_val) if week_val is not None else None,
                "completed": bool(payload.get("completed")),
                "message_count": payload.get("message_count") or 0,
                "user_message_count": payload.get("user_message_count") or 0,
                "started_at": payload.get("created_at"),
                "updated_at_raw": payload.get("updated_at"),
                "payload": sanitized_payload,
            }
        )
    return records


def _rebuild_challenge_attempts_from_chats(
    chats_payload: List[dict],
    *,
    model_lookup: Dict[str, str],
    mission_model_aliases: Set[str],
    alias_to_primary: Dict[str, str],
    week_mapping: Dict[str, str],
    points_mapping: Dict[str, int],
    difficulty_mapping: Dict[str, str],
    persist_mode: str = "truncate",
) -> List[dict]:
    """
    Recompute challenge attempts from raw chat exports and persist them.
    """
    if not chats_payload or not mission_model_aliases:
        persist_challenge_attempts([], mode=persist_mode)
        return []

    filtered_chats = _filter_chats_by_mission_models(chats_payload, mission_model_aliases)
    analyzer = MissionAnalyzer(
        json_file=None,
        data=filtered_chats,
        user_names_file=None,
        user_names={},
        model_lookup=model_lookup,
        mission_model_aliases=mission_model_aliases,
        model_alias_to_primary=alias_to_primary,
        week_mapping=week_mapping,
        points_mapping=points_mapping,
        difficulty_mapping=difficulty_mapping,
        verbose=False,
    )
    analyzer.analyze_missions()
    attempt_payloads = analyzer.export_challenge_attempts()

    records = _build_challenge_attempt_records(attempt_payloads)
    persist_challenge_attempts(records, mode=persist_mode)
    logger.info("Persisted %d challenge attempts (mode=%s)", len(records), persist_mode)
    return attempt_payloads


def _persist_chats_and_rebuild_attempts(chats_payload: List[dict], mode: str = "upsert") -> int:
    """
    Persist chat payloads and refresh the cached challenge attempts table.
    """
    rows = persist_chats(chats_payload, mode=mode)
    metadata = _load_model_metadata()
    if metadata:
        model_lookup, mission_model_aliases, alias_to_primary, week_mapping, points_mapping, difficulty_mapping = metadata
        _rebuild_challenge_attempts_from_chats(
            chats_payload,
            model_lookup=model_lookup,
            mission_model_aliases=mission_model_aliases,
            alias_to_primary=alias_to_primary,
            week_mapping=week_mapping,
            points_mapping=points_mapping,
            difficulty_mapping=difficulty_mapping,
            persist_mode="truncate",
        )
    else:
        persist_challenge_attempts([], mode="truncate")
    return rows


def _get_or_build_challenge_attempt_payloads(data_file: Optional[str] = None) -> List[dict]:
    """
    Retrieve cached challenge attempts, rebuilding them from chats if necessary.
    """
    attempt_payloads = load_challenge_attempts()
    if attempt_payloads:
        return attempt_payloads

    chats_payload = load_chats()
    if not chats_payload:
        remote_chats = _fetch_remote_chats()
        if remote_chats:
            chats_payload = remote_chats
        else:
            target_file = data_file or find_latest_export()
            if target_file:
                try:
                    with open(target_file, "r", encoding="utf-8") as f:
                        chats_payload = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    chats_payload = None

    if not chats_payload:
        return []

    _persist_chats_and_rebuild_attempts(chats_payload, mode="upsert")
    return load_challenge_attempts()


def build_mission_analysis_context(
    *,
    data_file: Optional[str] = None,
    user_names_file: Optional[str] = None,
    sort_by: SortOption = SortOption.completions,
    filter_week: Optional[str] = None,
    filter_challenge: Optional[str] = None,
    filter_user: Optional[str] = None,
    filter_status: Optional[str] = None,
    force_refresh: bool = False,
    reload_mode: str = "upsert",
    strict: bool = True,
) -> Optional[MissionAnalysisContext]:
    """
    Build and cache a MissionAnalyzer instance plus supporting metadata so other
    services can reuse the same mission calculations.

    Args:
        strict: When False, failures to assemble the analyzer return ``None`` so
            callers can gracefully skip mission-derived features without
            surfacing errors to end users.
    """
    resolved_user_names = user_names_file or str(Path(DATA_DIR) / "user_names.json")

    try:
        (
            model_lookup,
            mission_model_aliases,
            alias_to_primary,
            week_mapping,
            points_mapping,
            difficulty_mapping,
        ) = _load_model_metadata(
            force_refresh=force_refresh,
            mode=reload_mode,
        )

        data_source = "challenge_attempts"
        chats_payload: Optional[List[dict]] = None
        attempt_payloads: List[dict] = [] if force_refresh else load_challenge_attempts()

        if force_refresh:
            chats_payload = _fetch_remote_chats()
            if chats_payload is not None:
                persist_chats(chats_payload, mode=reload_mode)
                attempt_payloads = _rebuild_challenge_attempts_from_chats(
                    chats_payload,
                    model_lookup=model_lookup,
                    mission_model_aliases=mission_model_aliases,
                    alias_to_primary=alias_to_primary,
                    week_mapping=week_mapping,
                    points_mapping=points_mapping,
                    difficulty_mapping=difficulty_mapping,
                    persist_mode="truncate",
                )
                data_source = "api"

        if not attempt_payloads:
            attempt_payloads = load_challenge_attempts()

        if not attempt_payloads:
            if not chats_payload:
                chats_payload = load_chats()
                if chats_payload:
                    data_source = "database"

            if not chats_payload:
                target_file = data_file or find_latest_export()
                if not target_file:
                    raise HTTPException(
                        status_code=503,
                        detail="No data available. Please configure Open WebUI credentials or provide a chat export.",
                    )
                logger.info("Using fallback export file: %s", target_file)
                try:
                    with open(target_file, "r", encoding="utf-8") as f:
                        chats_payload = json.load(f)
                    data_source = "file"
                    persist_chats(chats_payload, mode="upsert")
                except (FileNotFoundError, json.JSONDecodeError) as exc:
                    logger.error("Failed to load fallback export: %s", exc)
                    raise HTTPException(
                        status_code=503,
                        detail="Data is unavailable. Please refresh from Open WebUI.",
                    ) from exc

            if not chats_payload:
                raise HTTPException(
                    status_code=503,
                    detail="Unable to load chat data. Please refresh from Open WebUI.",
                )

            attempt_payloads = _rebuild_challenge_attempts_from_chats(
                chats_payload,
                model_lookup=model_lookup,
                mission_model_aliases=mission_model_aliases,
                alias_to_primary=alias_to_primary,
                week_mapping=week_mapping,
                points_mapping=points_mapping,
                difficulty_mapping=difficulty_mapping,
                persist_mode="truncate",
            )

        if not attempt_payloads:
            raise HTTPException(
                status_code=503,
                detail="Unable to process mission attempts. Please refresh from Open WebUI.",
            )

        logger.info("Loaded %d cached challenge attempts (data source=%s)", len(attempt_payloads), data_source)

        user_info_map: Dict[str, dict] = {}
        if force_refresh:
            remote_users_payload = _fetch_remote_users()
            if remote_users_payload:
                user_info_map, raw_users = remote_users_payload
                persist_users(raw_users, mode=reload_mode)

        if not user_info_map:
            stored_users_map, _ = load_users()
            if stored_users_map:
                user_info_map = stored_users_map

        user_names_only = {uid: details.get("name", "") for uid, details in user_info_map.items()}

        analyzer = MissionAnalyzer(
            json_file=None,
            data=[],
            user_names_file=resolved_user_names,
            user_names=user_names_only,
            model_lookup=model_lookup,
            mission_model_aliases=mission_model_aliases,
            model_alias_to_primary=alias_to_primary,
            week_mapping=week_mapping,
            points_mapping=points_mapping,
            difficulty_mapping=difficulty_mapping,
            verbose=False,
        )

        analyzer.load_challenge_attempts(
            attempt_payloads,
            filter_challenge=filter_challenge,
            filter_user=filter_user,
            filter_status=filter_status,
            filter_week=filter_week,
        )

        return MissionAnalysisContext(
            analyzer=analyzer,
            data_source=data_source,
            user_info_map=user_info_map,
            model_lookup=model_lookup,
            mission_model_aliases=mission_model_aliases,
            alias_to_primary=alias_to_primary,
            week_mapping=week_mapping,
            points_mapping=points_mapping,
            difficulty_mapping=difficulty_mapping,
        )
    except HTTPException as exc:
        if strict:
            raise
        logger.warning("Mission analysis unavailable: %s", getattr(exc, "detail", exc))
        return None


def _fetch_remote_users() -> Optional[Tuple[Dict[str, dict], List[dict]]]:
    # Mirrors chat fetch logic but normalizes user metadata for display names.
    hostname = os.getenv("OPEN_WEBUI_HOSTNAME") or os.getenv("OPEN_WEB_UI_HOSTNAME")
    api_key = os.getenv("OPEN_WEBUI_API_KEY")

    if not hostname or not api_key:
        logger.debug("Skipping remote user fetch; credentials not configured")
        return None

    url = f"{hostname.rstrip('/')}/api/v1/users/all"
    headers = {"Authorization": f"Bearer {api_key}"}
    logger.debug("Requesting users from OpenWebUI at %s", url)
    start_time = perf_counter()

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:  # pragma: no cover - surface auth errors
        raise HTTPException(status_code=502, detail=f"Failed to fetch users from OpenWebUI: {exc}") from exc
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:  # pragma: no cover - network failure
        logger.warning("OpenWebUI users fetch failed (%s); falling back to stored users", exc)
        return None
    except requests.exceptions.RequestException as exc:  # pragma: no cover - network failure
        logger.warning("OpenWebUI users fetch failed (%s); falling back to stored users", exc)
        return None

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

    # Normalize user records for downstream consumers
    raw_records: List[dict] = []
    user_map: Dict[str, dict] = {}
    for item in payload:
        user_id = item.get("id")
        if not user_id:
            continue
        name = item.get("name") or ""
        email = item.get("email") or ""
        display = name.strip() or (email.split("@")[0] if email else user_id[:8])
        user_map[user_id] = {"name": display, "email": email}

        item_copy = dict(item)
        item_copy.setdefault("name", display)
        raw_records.append(item_copy)

    duration = perf_counter() - start_time
    logger.info(
        "Fetched %d users from OpenWebUI in %.2fs",
        len(raw_records),
        duration,
    )

    return user_map, raw_records


def _fetch_remote_models() -> Optional[List[dict]]:
    """Retrieve model metadata from OpenWebUI."""
    hostname = os.getenv("OPEN_WEBUI_HOSTNAME") or os.getenv("OPEN_WEB_UI_HOSTNAME")
    api_key = os.getenv("OPEN_WEBUI_API_KEY")

    if not hostname or not api_key:
        logger.debug("Skipping remote model fetch; credentials not configured")
        return None

    url = f"{hostname.rstrip('/')}/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    logger.debug("Requesting models from OpenWebUI at %s", url)
    start_time = perf_counter()

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("OpenWebUI models fetch failed (%s)", exc)
        return None

    payload = response.json()
    records: List[dict] | dict | None
    if isinstance(payload, dict):
        records = payload.get("data") or payload.get("models") or payload.get("items") or []
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    if isinstance(records, dict):
        for key in ("items", "data", "models", "results"):
            nested = records.get(key)
            if isinstance(nested, list):
                records = nested
                break
        else:
            # Fallback: keep only dict values that are themselves dicts to avoid iterating over keys.
            records = [value for value in records.values() if isinstance(value, dict)]

    if not isinstance(records, list):
        logger.error("Unexpected OpenWebUI models payload structure: %s", type(records))
        return None

    duration = perf_counter() - start_time
    logger.info("Fetched %d models from OpenWebUI in %.2fs", len(records), duration)

    return records


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
    filter_week: Optional[str] = None,
    model_lookup: Optional[Dict[str, str]] = None,
) -> List[ChatPreview]:
    """Transform cached challenge attempts into lightweight cards for the frontend."""
    previews: List[ChatPreview] = []
    model_lookup = model_lookup or {}

    for mission_chat in analyzer.mission_chats:
        user_id = mission_chat.get("user_id", "Unknown")
        if filter_user and user_id != filter_user:
            continue

        mission_info = mission_chat.get("mission_info") or {}
        mission_model = mission_chat.get("model")
        mission_week = mission_info.get("week")
        mission_display_name = mission_info.get("mission_id") or model_lookup.get(mission_model, mission_model)
        completed = mission_chat.get("completed", False)

        if filter_challenge and not analyzer._mission_matches_filter(mission_model, filter_challenge):
            continue

        if filter_status and filter_status.lower() != "not_attempted":
            status_filter = filter_status.lower()
            if status_filter == "completed" and not completed:
                continue
            if status_filter == "attempted" and completed:
                continue

        if filter_week:
            compare_week = mission_week
            if compare_week is None:
                compare_week = analyzer._lookup_week_for_model(mission_model)
            if not compare_week or str(compare_week) != str(filter_week):
                continue

        mission_messages = mission_chat.get("messages") or []
        mission_message_count = mission_chat.get("message_count", len(mission_messages))

        previews.append(
            ChatPreview(
                num=mission_chat.get("chat_num") or len(previews) + 1,
                title=mission_chat.get("title", "Untitled"),
                user_id=user_id,
                user_name=analyzer.get_user_name(user_id),
                created_at=mission_chat.get("created_at"),
                model=mission_display_name or mission_model or "Unknown",
                message_count=mission_message_count,
                is_mission=True,
                completed=completed,
                week=mission_week,
                challenge_name=mission_display_name,
                attempt_id=mission_chat.get("attempt_id"),
                messages=[
                    ChatMessage(
                        role=msg.get("role"),
                        content=msg.get("content"),
                        timestamp=msg.get("timestamp") or msg.get("created_at") or msg.get("updated_at"),
                    )
                    for msg in mission_messages
                ],
            )
        )

    return previews


def _build_challenge_attempt_entries(
    analyzer: MissionAnalyzer,
    model_lookup: Optional[Dict[str, str]] = None,
) -> List[ChallengeAttemptRecord]:
    """
    Transform mission analyzer attempts into a flattened structure for dashboard tables.
    """
    entries: List[ChallengeAttemptRecord] = []
    model_lookup = model_lookup or {}

    for mission_chat in analyzer.mission_chats:
        user_id = mission_chat.get("user_id", "Unknown")
        mission_info = mission_chat.get("mission_info") or {}
        mission_model = mission_chat.get("model")
        mission_week = mission_info.get("week")
        challenge_name = mission_info.get("mission_id") or model_lookup.get(mission_model, mission_model) or "Unknown mission"
        attempt_identifier = mission_chat.get("attempt_id") or mission_chat.get("chat_id") or str(
            mission_chat.get("chat_num") or len(entries) + 1
        )

        message_count = mission_chat.get("message_count")
        if message_count is None:
            message_count = len(mission_chat.get("messages") or [])
        user_message_count = mission_chat.get("user_message_count") or 0

        entries.append(
            ChallengeAttemptRecord(
                attempt_id=str(attempt_identifier),
                attempt_number=mission_chat.get("chat_num") or len(entries) + 1,
                chat_id=mission_chat.get("chat_id"),
                chat_title=mission_chat.get("title"),
                user_id=user_id,
                user_name=analyzer.get_user_name(user_id),
                challenge_name=challenge_name,
                mission_model=mission_model,
                mission_week=mission_week,
                completed=bool(mission_chat.get("completed")),
                message_count=message_count,
                user_message_count=user_message_count,
                started_at=mission_chat.get("created_at"),
                updated_at=mission_chat.get("updated_at"),
            )
        )

    return entries


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
                unique_missions_not_started=item.get("unique_missions_not_started", 0),
                missions_attempted_details=item.get("missions_attempted_details", []),
                missions_completed_details=item.get("missions_completed_details", []),
                missions_not_started_details=item.get("missions_not_started_details", []),
                first_attempt=item.get("first_attempt"),
                last_attempt=item.get("last_attempt"),
                total_points=item.get("total_points", 0),
            )
        )
    return entries


def _decorate_summary(analyzer: MissionAnalyzer, raw_summary: dict, user_info_map: Dict[str, dict]) -> Summary:
    participation_rate = (
        raw_summary["unique_users"] / raw_summary["total_chats"] * 100
        if raw_summary["total_chats"]
        else 0.0
    )

    # Enhance users_list with email information
    users_list = []
    for user in raw_summary.get("users_list", []):
        user_id = user.get("user_id")
        user_info = user_info_map.get(user_id, {})
        users_list.append({
            "user_id": user_id,
            "user_name": user.get("user_name"),
            "email": user_info.get("email", "")
        })

    return Summary(
        total_chats=raw_summary["total_chats"],
        mission_attempts=raw_summary["mission_attempts"],
        mission_completions=raw_summary["mission_completions"],
        success_rate=raw_summary["success_rate"],
        unique_users=raw_summary["unique_users"],
        unique_missions=raw_summary["unique_missions"],
        missions_list=raw_summary["missions_list"],
        missions_with_weeks=raw_summary.get("missions_with_weeks", {}),
        weeks_list=raw_summary.get("weeks_list", []),
        users_list=users_list,
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
            users_attempted=item["users_attempted"],
            users_completed=item["users_completed"],
            users_not_started=item["users_not_started"],
            avg_messages_to_complete=item["avg_messages_to_complete"],
            avg_attempts_to_complete=item["avg_attempts_to_complete"],
            week=item["week"],
            difficulty=item["difficulty"],
            points=item["points"],
        )
        for item in mission_breakdown
    ]


def _decorate_challenge_results(challenge_results: List[dict]) -> List[ChallengeResultEntry]:
    """Transform raw challenge results into Pydantic models."""
    return [
        ChallengeResultEntry(
            user_id=item["user_id"],
            user_name=item["user_name"],
            status=item["status"],
            num_attempts=item["num_attempts"],
            first_attempt_time=item["first_attempt_time"],
            completed_time=item["completed_time"],
            num_messages=item["num_messages"],
        )
        for item in challenge_results
    ]


def _generate_export_data(
    analyzer: MissionAnalyzer,
    user_info_map: Dict[str, dict],
    model_lookup: Dict[str, str],
    week_mapping: Dict[str, str],
    points_mapping: Dict[str, int],
    difficulty_mapping: Dict[str, str],
    mission_model_aliases: Set[str],
    alias_to_primary: Dict[str, str],
) -> List[dict]:
    """
    Generate export data with one row per user/challenge combination.

    Args:
        analyzer: MissionAnalyzer instance with analyzed data
        user_info_map: Mapping of user_id -> {"name": name, "email": email}
        model_lookup: Mapping of model aliases to friendly names
        week_mapping: Mapping of model aliases to week numbers
        points_mapping: Mapping of model aliases to point values
        difficulty_mapping: Mapping of model aliases to difficulty levels
        mission_model_aliases: Set of model aliases tagged as missions
        alias_to_primary: Mapping of aliases to primary identifiers

    Returns:
        List of dicts, each representing a user/challenge combination
    """
    def lookup_with_fallback(mapping: Dict[str, Any], *keys: str) -> Any:
        """
        Retrieve a mapping value with case-insensitive fallbacks across
        multiple candidate keys (alias, primary id, display name).
        """
        for key in keys:
            if not key:
                continue
            if key in mapping:
                return mapping[key]
            key_lower = str(key).lower()
            for map_key, val in mapping.items():
                if str(map_key).lower() == key_lower:
                    return val
        return None

    default_points_by_difficulty = {"easy": 15, "medium": 20, "hard": 25}
    export_rows = []

    # Get all users from available mission data. The analyzer is often populated
    # from cached challenge attempts, which leaves ``analyzer.data`` empty, so
    # fall back to the mission chat payloads that always include user_ids.
    all_users = set()
    mission_source = analyzer.mission_chats or analyzer.data
    for item in mission_source:
        if not isinstance(item, dict):
            continue
        user_id = item.get("user_id", "Unknown")
        if user_id and user_id != "Unknown":
            all_users.add(user_id)

    # Get all mission models (challenges)
    all_missions = []
    seen_missions = set()
    for alias in mission_model_aliases:
        display_name = model_lookup.get(alias, alias)
        primary_id = alias_to_primary.get(alias, alias)
        if display_name not in seen_missions:
            all_missions.append({
                "display_name": display_name,
                "primary_id": primary_id,
                "alias": alias
            })
            seen_missions.add(display_name)

    # For each user/challenge combination
    for user_id in sorted(all_users):
        user_info = user_info_map.get(user_id, {"name": analyzer.get_user_name(user_id), "email": ""})
        user_name = user_info.get("name", analyzer.get_user_name(user_id))
        user_email = user_info.get("email", "")

        for mission in all_missions:
            challenge_name = mission["display_name"]
            primary_id = mission["primary_id"]
            alias = mission["alias"]

            # Get challenge results for this specific challenge and user
            # We need to filter mission_chats to find this user's attempts for this challenge
            user_attempts = []
            for chat in analyzer.mission_chats:
                if chat["user_id"] != user_id:
                    continue

                # Check if this chat is for the current mission
                chat_model = chat["model"]
                if analyzer._mission_matches_filter(chat_model, challenge_name):
                    user_attempts.append(chat)

            # Calculate metrics
            if not user_attempts:
                # No attempts
                status = "Empty"
                completed = "No"
                num_attempts = 0
                num_messages = 0
                datetime_started = None
                datetime_completed = None
                points_earned = 0
            else:
                # Sort by created_at
                user_attempts.sort(key=lambda x: x.get("created_at") or 0)

                # Check if completed
                completed_attempts = [a for a in user_attempts if a["completed"]]
                if completed_attempts:
                    status = "Completed"
                    completed = "Yes"
                    # Find first completion
                    first_completion = completed_attempts[0]
                    completed_idx = user_attempts.index(first_completion)
                    num_attempts = completed_idx + 1
                    num_messages = 0
                    for attempt in user_attempts[:num_attempts]:
                        if "user_message_count" in attempt:
                            num_messages += attempt["user_message_count"]
                        else:
                            num_messages += analyzer._count_user_messages(attempt.get("messages", []))
                    datetime_started = user_attempts[0].get("created_at")
                    datetime_completed = first_completion.get("created_at")
                    points_earned = 0
                else:
                    status = "Attempted"
                    completed = "No"
                    num_attempts = len(user_attempts)
                    num_messages = 0
                    for attempt in user_attempts:
                        if "user_message_count" in attempt:
                            num_messages += attempt["user_message_count"]
                        else:
                            num_messages += analyzer._count_user_messages(attempt.get("messages", []))
                    datetime_started = user_attempts[0].get("created_at")
                    datetime_completed = None
                    points_earned = 0

            # Get week for this challenge
            week = lookup_with_fallback(week_mapping, alias, primary_id, challenge_name) or ""
            if not week:
                week_match = re.search(r"week\s*(\d+)", challenge_name, re.IGNORECASE)
                if week_match:
                    week = week_match.group(1)

            # Get difficulty for this challenge with regex fallback from the display name
            difficulty = lookup_with_fallback(difficulty_mapping, alias, primary_id, challenge_name) or ""
            if not difficulty:
                diff_match = re.search(r"\b(easy|medium|hard)\b", challenge_name, re.IGNORECASE)
                if diff_match:
                    difficulty = diff_match.group(1).capitalize()
            elif str(difficulty).lower() in default_points_by_difficulty:
                difficulty = str(difficulty).lower().capitalize()

            # Resolve points; if metadata is missing, infer from difficulty
            points = lookup_with_fallback(points_mapping, alias, primary_id, challenge_name)
            if points is None and difficulty:
                points = default_points_by_difficulty.get(str(difficulty).lower())

            # Format timestamps as strings if they exist
            datetime_started_str = None
            datetime_completed_str = None
            if datetime_started:
                if isinstance(datetime_started, (int, float)):
                    from datetime import datetime
                    datetime_started_str = datetime.fromtimestamp(datetime_started).isoformat()
                else:
                    datetime_started_str = str(datetime_started)

            if datetime_completed:
                if isinstance(datetime_completed, (int, float)):
                    from datetime import datetime
                    datetime_completed_str = datetime.fromtimestamp(datetime_completed).isoformat()
                else:
                    datetime_completed_str = str(datetime_completed)

            export_rows.append({
                "user_name": user_name,
                "email": user_email,
                "challenge_name": challenge_name,
                "status": status,
                "completed": completed,
                "num_attempts": num_attempts,
                "num_messages": num_messages,
                "week": str(week) if week else "",
                "difficulty": str(difficulty) if difficulty else "",
                "datetime_started": datetime_started_str,
                "datetime_completed": datetime_completed_str,
                "points_earned": points if points is not None else points_earned,
            })

    return export_rows


def build_dashboard_response(
    *,
    data_file: Optional[str] = None,
    user_names_file: Optional[str] = None,
    sort_by: SortOption = SortOption.completions,
    filter_week: Optional[str] = None,
    filter_challenge: Optional[str] = None,
    filter_user: Optional[str] = None,
    filter_status: Optional[str] = None,
    force_refresh: bool = False,
    reload_mode: str = "upsert",
) -> DashboardResponse:
    """
    Build dashboard response with mission analytics data.

    Args:
        reload_mode: Controls how data is persisted when a refresh occurs. Supports
            ``"upsert"`` (default) and ``"truncate"`` for a full reset.
    """
    logger.info(
        "Building dashboard response (force_refresh=%s, reload_mode=%s, sort_by=%s, filters: week=%s, challenge=%s, user=%s, status=%s)",
        force_refresh,
        reload_mode,
        sort_by.value,
        filter_week,
        filter_challenge,
        filter_user,
        filter_status,
    )
    context = build_mission_analysis_context(
        data_file=data_file,
        user_names_file=user_names_file,
        sort_by=sort_by,
        filter_week=filter_week,
        filter_challenge=filter_challenge,
        filter_user=filter_user,
        filter_status=filter_status,
        force_refresh=force_refresh,
        reload_mode=reload_mode,
        strict=True,
    )
    if context is None:  # pragma: no cover - strict=True prevents None
        raise HTTPException(status_code=503, detail="Mission analysis unavailable.")

    analyzer = context.analyzer
    user_info_map = context.user_info_map

    # Compose the response sections in the order expected by the frontend.
    summary = _decorate_summary(analyzer, analyzer.get_summary(), user_info_map)
    leaderboard = _decorate_leaderboard(analyzer, analyzer.get_leaderboard(sort_by=sort_by.value))
    missions = _decorate_mission_breakdown(analyzer.get_mission_breakdown())
    chats = _build_chat_previews(
        analyzer,
        filter_challenge=filter_challenge,
        filter_user=filter_user,
        filter_status=filter_status,
        filter_week=filter_week,
        model_lookup=context.model_lookup,
    )
    challenge_attempts = _build_challenge_attempt_entries(
        analyzer,
        model_lookup=context.model_lookup,
    )
    challenge_results = _decorate_challenge_results(
        analyzer.get_challenge_results(filter_challenge=filter_challenge, filter_status=filter_status)
    )

    # Generate export data (all user/challenge combinations)
    export_data_raw = _generate_export_data(
        analyzer=analyzer,
        user_info_map=user_info_map,
        model_lookup=context.model_lookup,
        week_mapping=context.week_mapping,
        points_mapping=context.points_mapping,
        difficulty_mapping=context.difficulty_mapping,
        mission_model_aliases=context.mission_model_aliases,
        alias_to_primary=context.alias_to_primary,
    )

    export_data = [UserChallengeExportRow(**row) for row in export_data_raw]

    latest_log = get_latest_status()
    last_fetched = None
    if latest_log and latest_log.finished_at:
        try:
            normalized = _normalize_to_utc(latest_log.finished_at)
            last_fetched = normalized.isoformat() if normalized else None
        except AttributeError:
            last_fetched = None

    logger.info(
        "Dashboard response generated (missions=%d, leaderboard entries=%d, export rows=%d, users=%d)",
        len(missions),
        len(leaderboard),
        len(export_data),
        len(user_info_map),
    )

    return DashboardResponse(
        generated_at=datetime.now(timezone.utc),
        last_fetched=last_fetched,
        data_source=context.data_source,
        summary=summary,
        leaderboard=leaderboard,
        mission_breakdown=missions,
        all_chats=chats,
        challenge_attempts=challenge_attempts,
        challenge_results=challenge_results,
        export_data=export_data,
    )


def _build_reload_result(resource: str, requested_mode: str, rows: int | None) -> Dict[str, Any]:
    log = get_latest_status(resource)
    finished_at = None
    status = "success"
    message = None
    rows_logged = rows
    previous_count = None
    new_records = None
    total_records = None
    duration = None
    if log:
        status = log.status
        message = log.message
        rows_logged = log.rows_affected if log.rows_affected is not None else rows_logged
        previous_count = log.previous_count
        new_records = log.new_records
        total_records = log.total_count
        duration = log.duration_seconds
        if log.finished_at:
            try:
                normalized = _normalize_to_utc(log.finished_at)
                finished_at = normalized.isoformat() if normalized else None
            except AttributeError:
                finished_at = None

    return {
        "resource": resource,
        "mode": requested_mode,
        "status": status,
        "rows": rows_logged,
        "message": message,
        "finished_at": finished_at,
        "previous_count": previous_count,
        "new_records": new_records,
        "total_records": total_records,
        "duration_seconds": duration,
    }


def reload_models(mode: str = "upsert") -> Dict[str, Any]:
    mode_normalized = mode.lower()
    if mode_normalized not in {"upsert", "truncate"}:
        raise HTTPException(status_code=400, detail="mode must be 'upsert' or 'truncate'")

    logger.info("Starting model reload (mode=%s)", mode_normalized)
    records = _fetch_remote_models()
    if records is None:
        raise HTTPException(status_code=503, detail="Unable to fetch models from Open WebUI.")

    try:
        rows = persist_models(records, mode=mode_normalized)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Model reload failed")
        raise HTTPException(status_code=500, detail=f"Model reload failed: {exc}") from exc
    logger.info("Model reload completed with %s rows processed", rows)
    return _build_reload_result("models", mode_normalized, rows)


def reload_users(mode: str = "upsert") -> Dict[str, Any]:
    mode_normalized = mode.lower()
    if mode_normalized not in {"upsert", "truncate"}:
        raise HTTPException(status_code=400, detail="mode must be 'upsert' or 'truncate'")

    if mode_normalized == "truncate":
        raise HTTPException(
            status_code=400,
            detail="Truncate mode for users is only supported via the combined reload endpoint.",
        )

    logger.info("Starting user reload (mode=%s)", mode_normalized)
    payload = _fetch_remote_users()
    if payload is None:
        raise HTTPException(status_code=503, detail="Unable to fetch users from Open WebUI.")

    _user_map, raw_users = payload
    try:
        rows = persist_users(raw_users, mode=mode_normalized)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("User reload failed")
        raise HTTPException(status_code=500, detail=f"User reload failed: {exc}") from exc
    logger.info("User reload completed with %s rows processed", rows)
    return _build_reload_result("users", mode_normalized, rows)


def reload_chats(mode: str = "upsert") -> Dict[str, Any]:
    mode_normalized = mode.lower()
    if mode_normalized not in {"upsert", "truncate"}:
        raise HTTPException(status_code=400, detail="mode must be 'upsert' or 'truncate'")

    logger.info("Starting chat reload (mode=%s)", mode_normalized)
    chats_payload = _fetch_remote_chats()
    if chats_payload is None:
        raise HTTPException(status_code=503, detail="Unable to fetch chats from Open WebUI.")

    try:
        rows = _persist_chats_and_rebuild_attempts(chats_payload, mode=mode_normalized)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Chat reload failed")
        raise HTTPException(status_code=500, detail=f"Chat reload failed: {exc}") from exc
    logger.info("Chat reload completed with %s rows processed", rows)
    return _build_reload_result("chats", mode_normalized, rows)


def reload_all(mode: str = "upsert") -> List[Dict[str, Any]]:
    mode_normalized = mode.lower()
    if mode_normalized not in {"upsert", "truncate"}:
        raise HTTPException(status_code=400, detail="mode must be 'upsert' or 'truncate'")

    logger.info("Starting full data reload (mode=%s)", mode_normalized)
    overall_start = perf_counter()
    models_data = _fetch_remote_models()
    users_payload = _fetch_remote_users()
    chats_payload = _fetch_remote_chats()

    if models_data is None or users_payload is None or chats_payload is None:
        raise HTTPException(
            status_code=503,
            detail="Unable to fetch data from Open WebUI. Verify credentials and try again.",
        )

    logger.debug(
        "Fetched remote payload sizes -> models=%s, users=%s, chats=%s",
        len(models_data),
        len(users_payload[1]),
        len(chats_payload),
    )

    _, raw_users = users_payload
    results: List[Dict[str, Any]] = []

    try:
        rows_models = persist_models(models_data, mode=mode_normalized)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Full reload failed during model persistence")
        raise HTTPException(status_code=500, detail=f"Model persistence failed: {exc}") from exc
    results.append(_build_reload_result("models", mode_normalized, rows_models))

    if mode_normalized == "truncate":
        # Remove chats first to satisfy foreign key constraints before truncating users.
        try:
            persist_chats([], mode="truncate")
            persist_challenge_attempts([], mode="truncate")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Full reload failed while truncating chats")
            raise HTTPException(status_code=500, detail=f"Chat truncation failed: {exc}") from exc

        try:
            rows_users = persist_users(raw_users, mode="truncate")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Full reload failed during user persistence (truncate)")
            raise HTTPException(status_code=500, detail=f"User persistence failed: {exc}") from exc
        results.append(_build_reload_result("users", "truncate", rows_users))

        try:
            rows_chats = _persist_chats_and_rebuild_attempts(chats_payload, mode="upsert")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Full reload failed during chat persistence after truncate")
            raise HTTPException(status_code=500, detail=f"Chat persistence failed: {exc}") from exc
        chat_result = _build_reload_result("chats", "truncate", rows_chats)
    else:
        try:
            rows_users = persist_users(raw_users, mode="upsert")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Full reload failed during user persistence")
            raise HTTPException(status_code=500, detail=f"User persistence failed: {exc}") from exc
        results.append(_build_reload_result("users", "upsert", rows_users))

        try:
            rows_chats = _persist_chats_and_rebuild_attempts(chats_payload, mode="upsert")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Full reload failed during chat persistence")
            raise HTTPException(status_code=500, detail=f"Chat persistence failed: {exc}") from exc
        chat_result = _build_reload_result("chats", "upsert", rows_chats)

    results.append(chat_result)

    total_rows = sum((item.get("rows") or 0) for item in results)
    aggregate_previous = sum((item.get("previous_count") or 0) for item in results if item.get("previous_count") is not None)
    aggregate_new = sum((item.get("new_records") or 0) for item in results if item.get("new_records") is not None)
    aggregate_total = sum((item.get("total_records") or 0) for item in results if item.get("total_records") is not None)
    overall_elapsed = perf_counter() - overall_start

    def _none_if_empty(value: float | int | None) -> float | int | None:
        return value if value or value == 0 else None

    aggregate_log = record_custom_reload(
        "all",
        mode_normalized,
        "success",
        None,
        total_rows,
        previous_count=_none_if_empty(aggregate_previous),
        new_records=_none_if_empty(aggregate_new),
        total_count=_none_if_empty(aggregate_total),
        duration_seconds=_none_if_empty(overall_elapsed),
    )
    results.append(
        {
            "resource": "all",
            "mode": mode_normalized,
            "status": aggregate_log.status,
            "rows": total_rows,
            "message": aggregate_log.message,
            "finished_at": (_normalize_to_utc(aggregate_log.finished_at).isoformat() if aggregate_log.finished_at else None),
            "previous_count": aggregate_log.previous_count,
            "new_records": aggregate_log.new_records,
            "total_records": aggregate_log.total_count,
            "duration_seconds": aggregate_log.duration_seconds,
        }
    )

    logger.info(
        "Full data reload completed in %.2fs (models_rows=%s, users_rows=%s, chats_rows=%s, total_rows=%s)",
        overall_elapsed,
        results[0].get("rows"),
        results[1].get("rows") if len(results) > 1 else None,
        chat_result.get("rows"),
        total_rows,
    )

    return results


def build_users_response() -> UsersResponse:
    """
    Build a response with all users and their challenge participation details.

    Returns:
        UsersResponse: Contains a list of users with their attempted/completed challenges.
    """
    # Load model metadata and user information
    model_lookup, mission_model_aliases, alias_to_primary, week_mapping, points_mapping, difficulty_mapping = _load_model_metadata()

    attempt_payloads = _get_or_build_challenge_attempt_payloads()
    if not attempt_payloads:
        raise HTTPException(
            status_code=503,
            detail="No mission attempt data available. Please reload chats.",
        )

    user_info_map, _ = load_users()
    if not user_info_map:
        remote_users_payload = _fetch_remote_users()
        if remote_users_payload:
            user_info_map, raw_users = remote_users_payload
            persist_users(raw_users, mode="upsert")

    user_names_only = {uid: info.get("name", "") for uid, info in user_info_map.items()}

    # Initialize analyzer
    analyzer = MissionAnalyzer(
        json_file=None,
        data=[],
        user_names=user_names_only,
        model_lookup=model_lookup,
        mission_model_aliases=mission_model_aliases,
        model_alias_to_primary=alias_to_primary,
        week_mapping=week_mapping,
        points_mapping=points_mapping,
        difficulty_mapping=difficulty_mapping,
        verbose=False,
    )

    analyzer.load_challenge_attempts(attempt_payloads)

    # Get all users
    all_users = {chat["user_id"] for chat in analyzer.mission_chats if chat.get("user_id")}

    # Get all missions
    all_missions = []
    seen_missions = {}  # mission_display_name -> {alias, primary_id}
    for alias in mission_model_aliases:
        display_name = model_lookup.get(alias, alias)
        primary_id = alias_to_primary.get(alias, alias)
        if display_name not in seen_missions:
            seen_missions[display_name] = {
                "alias": alias,
                "primary_id": primary_id
            }
            all_missions.append(display_name)

    # Build user data
    users_list = []
    for user_id in sorted(all_users):
        user_info = user_info_map.get(user_id, {"name": analyzer.get_user_name(user_id), "email": ""})
        user_name = user_info.get("name", analyzer.get_user_name(user_id))
        user_email = user_info.get("email", "")

        challenges = []
        total_attempts = 0
        total_completions = 0
        total_points = 0

        for challenge_name in all_missions:
            mission_info = seen_missions[challenge_name]
            alias = mission_info["alias"]
            primary_id = mission_info["primary_id"]

            # Get user attempts for this challenge
            user_attempts = []
            for chat in analyzer.mission_chats:
                if chat["user_id"] != user_id:
                    continue
                if analyzer._mission_matches_filter(chat["model"], challenge_name):
                    user_attempts.append(chat)

            # Calculate metrics
            if not user_attempts:
                status = "Not Started"
                num_attempts = 0
                num_messages = 0
                first_attempt_time = None
                completed_time = None
                points_earned = 0
            else:
                user_attempts.sort(key=lambda x: x.get("created_at") or 0)
                completed_attempts = [a for a in user_attempts if a["completed"]]

                if completed_attempts:
                    status = "Completed"
                    first_completion = completed_attempts[0]
                    completed_idx = user_attempts.index(first_completion)
                    num_attempts = completed_idx + 1
                    num_messages = sum(
                        a.get("user_message_count", analyzer._count_user_messages(a.get("messages", [])))
                        for a in user_attempts[:num_attempts]
                    )
                    first_attempt_time = user_attempts[0].get("created_at")
                    completed_time = first_completion.get("created_at")

                    # Get points
                    points = points_mapping.get(alias) or points_mapping.get(primary_id)
                    if points is None:
                        for key, val in points_mapping.items():
                            if key.lower() == alias.lower() or key.lower() == primary_id.lower():
                                points = val
                                break
                    points_earned = points if points is not None else 0
                    total_completions += 1
                    total_points += points_earned
                else:
                    status = "Attempted"
                    num_attempts = len(user_attempts)
                    num_messages = sum(
                        a.get("user_message_count", analyzer._count_user_messages(a.get("messages", [])))
                        for a in user_attempts
                    )
                    first_attempt_time = user_attempts[0].get("created_at")
                    completed_time = None
                    points_earned = 0

                total_attempts += num_attempts

            # Get metadata
            week = week_mapping.get(alias) or week_mapping.get(primary_id) or ""
            if not week:
                for key, val in week_mapping.items():
                    if key.lower() == alias.lower() or key.lower() == primary_id.lower():
                        week = val
                        break

            difficulty = difficulty_mapping.get(alias) or difficulty_mapping.get(primary_id) or ""
            if not difficulty:
                for key, val in difficulty_mapping.items():
                    if key.lower() == alias.lower() or key.lower() == primary_id.lower():
                        difficulty = val
                        break

            points = points_mapping.get(alias) or points_mapping.get(primary_id) or 0
            if points == 0:
                for key, val in points_mapping.items():
                    if key.lower() == alias.lower() or key.lower() == primary_id.lower():
                        points = val
                        break

            challenges.append(ChallengeAttempt(
                challenge_name=challenge_name,
                challenge_id=primary_id,
                week=str(week) if week else "",
                difficulty=str(difficulty) if difficulty else "",
                points=int(points) if points else 0,
                status=status,
                num_attempts=num_attempts,
                num_messages=num_messages,
                first_attempt_time=first_attempt_time,
                completed_time=completed_time,
            ))

        efficiency = (total_completions / total_attempts * 100) if total_attempts > 0 else 0.0

        users_list.append(UserWithChallenges(
            user_id=user_id,
            user_name=user_name,
            email=user_email,
            total_attempts=total_attempts,
            total_completions=total_completions,
            total_points=total_points,
            efficiency=efficiency,
            challenges=challenges,
        ))

    return UsersResponse(
        generated_at=datetime.now(timezone.utc),
        users=users_list,
    )


def build_challenges_response() -> ChallengesResponse:
    """
    Build a response with all challenges and their participant details.

    Returns:
        ChallengesResponse: Contains a list of challenges with users who attempted/completed them.
    """
    # Load model metadata and user information
    model_lookup, mission_model_aliases, alias_to_primary, week_mapping, points_mapping, difficulty_mapping = _load_model_metadata()

    attempt_payloads = _get_or_build_challenge_attempt_payloads()
    if not attempt_payloads:
        raise HTTPException(
            status_code=503,
            detail="No mission attempt data available. Please reload chats.",
        )

    user_info_map, _ = load_users()
    if not user_info_map:
        remote_users_payload = _fetch_remote_users()
        if remote_users_payload:
            user_info_map, raw_users = remote_users_payload
            persist_users(raw_users, mode="upsert")

    user_names_only = {uid: info.get("name", "") for uid, info in user_info_map.items()}

    # Initialize analyzer
    analyzer = MissionAnalyzer(
        json_file=None,
        data=[],
        user_names=user_names_only,
        model_lookup=model_lookup,
        mission_model_aliases=mission_model_aliases,
        model_alias_to_primary=alias_to_primary,
        week_mapping=week_mapping,
        points_mapping=points_mapping,
        difficulty_mapping=difficulty_mapping,
        verbose=False,
    )

    analyzer.load_challenge_attempts(attempt_payloads)

    # Get all users
    all_users = {chat["user_id"] for chat in analyzer.mission_chats if chat.get("user_id")}

    total_users = len(all_users)

    # Get all missions
    all_missions = []
    seen_missions = {}  # mission_display_name -> {alias, primary_id}
    for alias in mission_model_aliases:
        display_name = model_lookup.get(alias, alias)
        primary_id = alias_to_primary.get(alias, alias)
        if display_name not in seen_missions:
            seen_missions[display_name] = {
                "alias": alias,
                "primary_id": primary_id
            }
            all_missions.append(display_name)

    # Build challenge data
    challenges_list = []
    for challenge_name in all_missions:
        mission_info = seen_missions[challenge_name]
        alias = mission_info["alias"]
        primary_id = mission_info["primary_id"]

        # Get metadata
        week = week_mapping.get(alias) or week_mapping.get(primary_id) or ""
        if not week:
            for key, val in week_mapping.items():
                if key.lower() == alias.lower() or key.lower() == primary_id.lower():
                    week = val
                    break

        difficulty = difficulty_mapping.get(alias) or difficulty_mapping.get(primary_id) or ""
        if not difficulty:
            for key, val in difficulty_mapping.items():
                if key.lower() == alias.lower() or key.lower() == primary_id.lower():
                    difficulty = val
                    break

        points = points_mapping.get(alias) or points_mapping.get(primary_id) or 0
        if points == 0:
            for key, val in points_mapping.items():
                if key.lower() == alias.lower() or key.lower() == primary_id.lower():
                    points = val
                    break

        # Track participants
        participants = []
        users_attempted_set = set()
        users_completed_set = set()
        total_attempts = 0
        total_completions = 0
        completion_data = []  # For calculating averages

        for user_id in all_users:
            user_info = user_info_map.get(user_id, {"name": analyzer.get_user_name(user_id), "email": ""})
            user_name = user_info.get("name", analyzer.get_user_name(user_id))
            user_email = user_info.get("email", "")

            # Get user attempts for this challenge
            user_attempts = []
            for chat in analyzer.mission_chats:
                if chat["user_id"] != user_id:
                    continue
                if analyzer._mission_matches_filter(chat["model"], challenge_name):
                    user_attempts.append(chat)

            # Calculate metrics
            if not user_attempts:
                participants.append(UserParticipation(
                    user_id=user_id,
                    user_name=user_name,
                    email=user_email,
                    status="Not Started",
                    num_attempts=0,
                    num_messages=0,
                    first_attempt_time=None,
                    completed_time=None,
                ))
            else:
                user_attempts.sort(key=lambda x: x.get("created_at") or 0)
                completed_attempts = [a for a in user_attempts if a["completed"]]
                users_attempted_set.add(user_id)

                if completed_attempts:
                    status = "Completed"
                    first_completion = completed_attempts[0]
                    completed_idx = user_attempts.index(first_completion)
                    num_attempts = completed_idx + 1
                    num_messages = sum(
                        a.get("user_message_count", analyzer._count_user_messages(a.get("messages", [])))
                        for a in user_attempts[:num_attempts]
                    )
                    first_attempt_time = user_attempts[0].get("created_at")
                    completed_time = first_completion.get("created_at")

                    users_completed_set.add(user_id)
                    total_completions += 1
                    completion_data.append({
                        "num_attempts": num_attempts,
                        "num_messages": num_messages
                    })
                else:
                    status = "Attempted"
                    num_attempts = len(user_attempts)
                    num_messages = sum(
                        a.get("user_message_count", analyzer._count_user_messages(a.get("messages", [])))
                        for a in user_attempts
                    )
                    first_attempt_time = user_attempts[0].get("created_at")
                    completed_time = None

                total_attempts += num_attempts

                participants.append(UserParticipation(
                    user_id=user_id,
                    user_name=user_name,
                    email=user_email,
                    status=status,
                    num_attempts=num_attempts,
                    num_messages=num_messages,
                    first_attempt_time=first_attempt_time,
                    completed_time=completed_time,
                ))

        # Calculate averages
        avg_messages_to_complete = 0.0
        avg_attempts_to_complete = 0.0
        if completion_data:
            avg_messages_to_complete = sum(d["num_messages"] for d in completion_data) / len(completion_data)
            avg_attempts_to_complete = sum(d["num_attempts"] for d in completion_data) / len(completion_data)

        success_rate = (total_completions / total_attempts * 100) if total_attempts > 0 else 0.0
        users_attempted = len(users_attempted_set)
        users_completed = len(users_completed_set)
        users_not_started = total_users - users_attempted

        challenges_list.append(ChallengeWithUsers(
            challenge_name=challenge_name,
            challenge_id=primary_id,
            week=str(week) if week else "",
            difficulty=str(difficulty) if difficulty else "",
            points=int(points) if points else 0,
            total_attempts=total_attempts,
            total_completions=total_completions,
            success_rate=success_rate,
            users_attempted=users_attempted,
            users_completed=users_completed,
            users_not_started=users_not_started,
            avg_messages_to_complete=avg_messages_to_complete,
            avg_attempts_to_complete=avg_attempts_to_complete,
            participants=participants,
        ))

    return ChallengesResponse(
        generated_at=datetime.now(timezone.utc),
        challenges=challenges_list,
    )
