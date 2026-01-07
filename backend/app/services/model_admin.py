from __future__ import annotations

from copy import deepcopy
from typing import Dict, Iterable, Optional

from sqlalchemy.orm import Session

from ..db.crud import _extract_maip_metadata
from ..db.models import Model


def _normalize_tag_name(value: object) -> Optional[str]:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str):
            text = name.strip()
            return text or None
    return None


def _has_missions_tag(payload: dict) -> bool:
    for candidate in (
        payload.get("tags"),
        payload.get("meta", {}).get("tags") if isinstance(payload.get("meta"), dict) else None,
        payload.get("info", {}).get("meta", {}).get("tags") if isinstance(payload.get("info"), dict) else None,
    ):
        if isinstance(candidate, list):
            for item in candidate:
                name = _normalize_tag_name(item)
                if name and name.lower() == "missions":
                    return True
    return False


def _set_missions_tag(tags: list, enabled: bool) -> list:
    updated: list = []
    for entry in tags:
        name = _normalize_tag_name(entry)
        if name and name.lower() == "missions":
            continue
        updated.append(entry)
    if enabled:
        updated.append({"name": "Missions"})
    return updated


def _apply_missions_tag(payload: dict, enabled: bool) -> dict:
    if not isinstance(payload, dict):
        return {}

    tags = payload.get("tags")
    if not isinstance(tags, list):
        tags = []
    payload["tags"] = _set_missions_tag(tags, enabled)

    info = payload.get("info")
    if isinstance(info, dict):
        meta = info.get("meta")
        if isinstance(meta, dict):
            info_tags = meta.get("tags")
            if isinstance(info_tags, list):
                meta["tags"] = _set_missions_tag(info_tags, enabled)
            else:
                meta["tags"] = _set_missions_tag([], enabled)
            info["meta"] = meta
            payload["info"] = info

    return payload


def _ensure_custom_params(payload: dict, *, week: Optional[str], points: Optional[int], difficulty: Optional[str]) -> dict:
    if not isinstance(payload, dict):
        return {}
    params = payload.get("params")
    if not isinstance(params, dict):
        params = {}
    custom_params = params.get("custom_params")
    if not isinstance(custom_params, dict):
        custom_params = {}

    updates = {
        "maip_week": week,
        "maip_points_value": points,
        "maip_difficulty_level": difficulty,
    }
    for key, value in updates.items():
        if value is None:
            custom_params.pop(key, None)
        else:
            custom_params[key] = value

    if custom_params:
        params["custom_params"] = custom_params
        payload["params"] = params
    else:
        params.pop("custom_params", None)
        payload["params"] = params

    return payload


def _extract_model_id(record: dict) -> Optional[str]:
    if not isinstance(record, dict):
        return None
    return (
        record.get("id")
        or record.get("model_id")
        or record.get("slug")
        or record.get("model")
    )


def _extract_display_name(record: dict) -> Optional[str]:
    if not isinstance(record, dict):
        return None
    return (
        record.get("name")
        or record.get("display_name")
        or record.get("preset")
        or record.get("model")
    )


def serialize_model(model: Model) -> Dict[str, object]:
    payload = model.data if isinstance(model.data, dict) else {}
    return {
        "id": model.id,
        "name": model.name,
        "maip_week": model.maip_week,
        "maip_points": model.maip_points,
        "maip_difficulty": model.maip_difficulty,
        "is_challenge": _has_missions_tag(payload),
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }


def collect_model_identifiers(model: Model) -> set[str]:
    payload = model.data if isinstance(model.data, dict) else {}
    identifiers: set[str] = set()
    identifiers.add(str(model.id))

    def add(value: object) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text:
                identifiers.add(text)

    for key in ("id", "slug", "model", "preset", "name", "display_name", "displayName", "model_id"):
        add(payload.get(key))

    meta = payload.get("meta")
    if isinstance(meta, dict):
        for key in ("id", "slug", "model", "preset", "name"):
            add(meta.get(key))

    info = payload.get("info")
    if isinstance(info, dict):
        for key in ("id", "slug", "model", "preset", "name"):
            add(info.get(key))
        info_meta = info.get("meta")
        if isinstance(info_meta, dict):
            for key in ("id", "slug", "model", "preset", "name"):
                add(info_meta.get(key))

    return identifiers


def update_model(session: Session, model_id: str, updates: dict) -> Model:
    model = session.get(Model, model_id)
    if not model:
        raise ValueError("Model not found")

    changed_fields = set()
    if "name" in updates:
        model.name = updates["name"]
        changed_fields.add("name")
    if "maip_week" in updates:
        model.maip_week = updates["maip_week"]
        changed_fields.add("maip_week")
    if "maip_points" in updates:
        model.maip_points = updates["maip_points"]
        changed_fields.add("maip_points")
    if "maip_difficulty" in updates:
        model.maip_difficulty = updates["maip_difficulty"]
        changed_fields.add("maip_difficulty")

    payload = model.data if isinstance(model.data, dict) else {}
    payload = deepcopy(payload)
    payload.setdefault("id", model.id)

    if "name" in updates:
        if updates["name"]:
            payload["name"] = updates["name"]
        else:
            payload.pop("name", None)

    if "is_challenge" in updates:
        payload = _apply_missions_tag(payload, bool(updates["is_challenge"]))

    if changed_fields.intersection({"maip_week", "maip_points", "maip_difficulty"}):
        payload = _ensure_custom_params(
            payload,
            week=model.maip_week,
            points=model.maip_points,
            difficulty=model.maip_difficulty,
        )

    model.data = payload
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


def sync_models(session: Session, records: Iterable[dict]) -> int:
    affected = 0
    for record in records:
        if not isinstance(record, dict):
            continue

        model_id = _extract_model_id(record)
        if not model_id:
            continue

        existing = session.get(Model, model_id)
        data_payload = deepcopy(record)
        display_name = _extract_display_name(record) or model_id

        maip_week, maip_points, maip_difficulty = _extract_maip_metadata(record)
        if existing:
            if maip_week is None:
                maip_week = existing.maip_week
            if maip_points is None:
                maip_points = existing.maip_points
            if maip_difficulty is None:
                maip_difficulty = existing.maip_difficulty

            existing_challenge = _has_missions_tag(existing.data if isinstance(existing.data, dict) else {})
            data_payload = _apply_missions_tag(data_payload, existing_challenge)
            data_payload.setdefault("id", model_id)
            data_payload = _ensure_custom_params(
                data_payload,
                week=maip_week,
                points=maip_points,
                difficulty=maip_difficulty,
            )

            if display_name:
                data_payload["name"] = display_name

            existing.name = display_name
            existing.data = data_payload
            existing.maip_week = maip_week
            existing.maip_points = maip_points
            existing.maip_difficulty = maip_difficulty
            session.add(existing)
        else:
            data_payload = _apply_missions_tag(data_payload, _has_missions_tag(data_payload))
            data_payload = _ensure_custom_params(
                data_payload,
                week=maip_week,
                points=maip_points,
                difficulty=maip_difficulty,
            )
            data_payload.setdefault("id", model_id)
            if display_name:
                data_payload.setdefault("name", display_name)
            session.add(
                Model(
                    id=model_id,
                    name=display_name,
                    data=data_payload,
                    maip_week=maip_week,
                    maip_points=maip_points,
                    maip_difficulty=maip_difficulty,
                )
            )

        affected += 1

    session.commit()
    return affected
