#!/usr/bin/env python3
"""Debug script to test week mapping"""

import json
import sqlite3
import sys
from pathlib import Path

# Direct implementation without imports
DATA_DIR = Path(__file__).parent.parent / "data"
SQLITE_DB_FILE = DATA_DIR / "mission_dashboard.sqlite"


def _load_models_from_sqlite(db_path: Path):
    """Load model records from the SQLite database."""
    if not db_path.exists():
        return None

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT data FROM models").fetchall()
    except sqlite3.DatabaseError:
        return None
    finally:
        if conn is not None:
            conn.close()

    models = []
    for row in rows:
        payload = row["data"]
        if isinstance(payload, str):
            try:
                models.append(json.loads(payload))
            except json.JSONDecodeError:
                continue
        elif isinstance(payload, (bytes, bytearray)):
            try:
                models.append(json.loads(payload.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        elif isinstance(payload, dict):
            models.append(payload)
    return models if models else None

def _extract_model_metadata(records):
    """Extract metadata from model records"""
    lookup = {}
    mission_aliases = set()
    alias_to_primary = {}
    week_mapping = {}
    points_mapping = {}
    difficulty_mapping = {}

    for item in records:
        if not isinstance(item, dict):
            continue

        # Capture top-level model_id before processing raw data
        top_level_model_id = item.get("id") or item.get("model_id")

        # Handle production data format with model_id and raw fields
        if "model_id" in item and "raw" in item:
            raw = item.get("raw", {})
            if isinstance(raw, dict):
                item = raw

        identifiers = set()

        # Add top-level model_id to identifiers if present
        if top_level_model_id and isinstance(top_level_model_id, str):
            identifiers.add(top_level_model_id.strip())

        def add_identifier(value):
            if value is None:
                return
            if not isinstance(value, str):
                return
            text = value.strip()
            if not text:
                return
            identifiers.add(text)

        # Gather identifiers from top level fields
        for key in ("id", "slug", "model", "preset", "name", "display_name", "displayName", "model_id"):
            add_identifier(item.get(key))

        # Include identifiers defined within nested metadata blocks
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

        # Pick a canonical identifier
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

        tags = []
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
                        if isinstance(tag, dict):
                            tag_name = tag.get("name")
                            if tag_name:
                                tags.append(str(tag_name))
                        elif isinstance(tag, str):
                            tags.append(tag)

        # Extract maip_week, maip_points_value, and maip_difficulty_level from custom_params
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

        for identifier in identifiers:
            lookup[identifier] = display_name
            alias_to_primary[identifier] = primary_id
            if maip_week:
                week_mapping[identifier] = str(maip_week)
            if maip_points:
                try:
                    points_mapping[identifier] = int(maip_points)
                except (ValueError, TypeError):
                    pass
            if maip_difficulty:
                difficulty_mapping[identifier] = str(maip_difficulty)

        if any(tag.lower() == "missions" for tag in tags):
            mission_aliases.update(identifiers)

    return lookup, mission_aliases, alias_to_primary, week_mapping, points_mapping, difficulty_mapping

cached_models = _load_models_from_sqlite(SQLITE_DB_FILE)
if not cached_models:
    print("ERROR: Could not load models from mission_dashboard.sqlite")
    sys.exit(1)

model_lookup, mission_model_aliases, alias_to_primary, week_mapping, points_mapping, difficulty_mapping = _extract_model_metadata(cached_models)

print("=" * 80)
print("MODEL LOOKUP (first 10):")
print("=" * 80)
for i, (alias, name) in enumerate(list(model_lookup.items())[:10]):
    print(f"{alias[:50]:50s} -> {name}")
print()

print("=" * 80)
print("MISSION MODEL ALIASES:")
print("=" * 80)
for alias in sorted(mission_model_aliases):
    print(f"  {alias}")
print()

print("=" * 80)
print("WEEK MAPPING:")
print("=" * 80)
for alias, week in sorted(week_mapping.items()):
    print(f"{alias[:60]:60s} -> Week {week}")
print()

print("=" * 80)
print("TESTING WEEK 1 MISSION LOOKUPS:")
print("=" * 80)

# Test the two week 1 missions
test_aliases = [
    "maip---week-1---challenge-1",
    "mission-prompt-guardian"
]

for alias in test_aliases:
    print(f"\nTesting: {alias}")
    print(f"  In mission_model_aliases: {alias in mission_model_aliases}")
    print(f"  Display name: {model_lookup.get(alias, 'NOT FOUND')}")
    print(f"  Week (direct): {week_mapping.get(alias, 'NOT FOUND')}")

    # Try lowercase
    alias_lower = alias.lower()
    week_lower = None
    for key, val in week_mapping.items():
        if key.lower() == alias_lower:
            week_lower = val
            break
    print(f"  Week (lowercase): {week_lower or 'NOT FOUND'}")

    # Try primary
    primary = alias_to_primary.get(alias, alias)
    print(f"  Primary identifier: {primary}")
    print(f"  Week (via primary): {week_mapping.get(primary, 'NOT FOUND')}")

print()
print("=" * 80)
print("SIMULATING get_summary() LOGIC:")
print("=" * 80)

missions_with_weeks = {}
missions_list = []
seen_names = set()

for alias in mission_model_aliases:
    display_name = model_lookup.get(alias, alias)
    if display_name not in seen_names:
        missions_list.append(display_name)
        seen_names.add(display_name)

        # Get week - try multiple variations
        week = week_mapping.get(alias)

        if not week:
            primary = alias_to_primary.get(alias, alias)
            week = week_mapping.get(primary)

        if not week:
            alias_lower = str(alias).lower()
            for key, val in week_mapping.items():
                if key.lower() == alias_lower:
                    week = val
                    break

        if week:
            missions_with_weeks[display_name] = str(week)
            print(f"✓ {display_name[:50]:50s} -> Week {week}")
        else:
            print(f"✗ {display_name[:50]:50s} -> NO WEEK FOUND")

print()
print(f"Total missions: {len(missions_list)}")
print(f"Missions with weeks: {len(missions_with_weeks)}")
print()
print("missions_with_weeks dictionary:")
print(json.dumps(missions_with_weeks, indent=2))
