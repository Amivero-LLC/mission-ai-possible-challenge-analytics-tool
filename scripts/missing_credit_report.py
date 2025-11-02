import importlib.util
import json
import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv


# Get the project root directory (parent of scripts directory)
script_dir = Path(__file__).parent
project_root = script_dir.parent
sqlite_db = project_root / "data" / "mission_dashboard.sqlite"

# Load environment variables from .env file
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Dynamically load MissionAnalyzer without importing the full backend package (avoids SQLAlchemy dependency)
def load_mission_analyzer_class():
    module_path = project_root / "backend" / "app" / "services" / "mission_analyzer.py"
    if not module_path.exists():
        raise FileNotFoundError(f"Mission analyzer module not found at {module_path}")

    spec = importlib.util.spec_from_file_location("mission_analyzer_module", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load mission analyzer module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "MissionAnalyzer"):
        raise ImportError("MissionAnalyzer class not found in mission_analyzer module")
    return module.MissionAnalyzer


try:
    MissionAnalyzer = load_mission_analyzer_class()
except Exception as exc:  # pragma: no cover - defensive guard
    print(f"✗ Failed to load MissionAnalyzer: {exc}")
    print("Ensure you are running this script from the project root.")
    exit(1)


def extract_model_metadata(records: List[dict]) -> Tuple[
    Dict[str, str],
    Set[str],
    Dict[str, str],
    Dict[str, str],
    Dict[str, int],
    Dict[str, str],
]:
    """
    Replicate backend metadata extraction to avoid importing SQLAlchemy-heavy modules.
    Only retains models tagged with the Missions label.
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

        top_level_model_id = item.get("id") or item.get("model_id")
        if "model_id" in item and "raw" in item and isinstance(item.get("raw"), dict):
            item = item["raw"]

        identifiers: Set[str] = set()
        if isinstance(top_level_model_id, str) and top_level_model_id.strip():
            identifiers.add(top_level_model_id.strip())

        def add_identifier(value: Optional[str]) -> None:
            if not value or not isinstance(value, str):
                return
            text = value.strip()
            if text:
                identifiers.add(text)

        for key in ("id", "slug", "model", "preset", "name", "display_name", "displayName", "model_id"):
            add_identifier(item.get(key))

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
            info.get("meta", {}).get("tags")
            if isinstance(info, dict) and isinstance(info.get("meta"), dict)
            else None,
        ):
            if isinstance(candidate, list):
                for tag in candidate:
                    if isinstance(tag, dict):
                        tag_name = tag.get("name")
                        if tag_name:
                            tags.append(str(tag_name))
                    elif isinstance(tag, str):
                        tags.append(tag)

        maip_week = None
        maip_points = None
        maip_difficulty = None

        params = item.get("params")
        if isinstance(params, dict):
            custom_params = params.get("custom_params")
            if isinstance(custom_params, dict):
                maip_week = custom_params.get("maip_week", maip_week)
                maip_points = custom_params.get("maip_points_value", maip_points)
                maip_difficulty = custom_params.get("maip_difficulty_level", maip_difficulty)

        if not maip_week or not maip_points or not maip_difficulty:
            info_obj = item.get("info")
            if isinstance(info_obj, dict):
                info_params = info_obj.get("params")
                if isinstance(info_params, dict):
                    custom_params = info_params.get("custom_params")
                    if isinstance(custom_params, dict):
                        if not maip_week:
                            maip_week = custom_params.get("maip_week")
                        if not maip_points:
                            maip_points = custom_params.get("maip_points_value")
                        if not maip_difficulty:
                            maip_difficulty = custom_params.get("maip_difficulty_level")

        if not any(isinstance(tag, str) and tag.lower() == "missions" for tag in tags):
            continue

        mission_aliases.update(identifiers)

        for identifier in identifiers:
            lookup[identifier] = display_name
            alias_to_primary[identifier] = primary_id
            if maip_week:
                week_mapping[identifier] = str(maip_week)
            if maip_points:
                try:
                    points_mapping[identifier] = int(maip_points)
                except (TypeError, ValueError):
                    pass
            if maip_difficulty:
                difficulty_mapping[identifier] = str(maip_difficulty)

    return lookup, mission_aliases, alias_to_primary, week_mapping, points_mapping, difficulty_mapping


def filter_mission_chats(chats: List[dict], mission_model_aliases: Set[str]) -> List[dict]:
    """Filter chats to those referencing mission models."""
    if not mission_model_aliases:
        return []

    filtered = []
    mission_aliases_lower = {alias.lower() for alias in mission_model_aliases}

    for chat in chats:
        if not isinstance(chat, dict):
            continue
        chat_data = chat.get("chat") or {}
        models = chat_data.get("models") or []

        def model_matches(candidate) -> bool:
            if isinstance(candidate, str):
                return candidate.lower() in mission_aliases_lower
            if isinstance(candidate, dict):
                for key in ("id", "model", "slug"):
                    value = candidate.get(key)
                    if isinstance(value, str) and value.lower() in mission_aliases_lower:
                        return True
            return False

        if any(model_matches(model) for model in models):
            filtered.append(chat)
            continue

        messages = chat_data.get("messages") or []
        for message in messages:
            if not isinstance(message, dict):
                continue
            msg_model = message.get("model")
            if isinstance(msg_model, str) and msg_model.lower() in mission_aliases_lower:
                filtered.append(chat)
                break

    return filtered


def load_sqlite_payloads(db_path: Path) -> Tuple[List[dict], List[dict], Dict[str, Dict[str, str]]]:
    """Load models, chats, and users from the SQLite database using stdlib only."""
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        models = [
            json.loads(row["data"]) for row in conn.execute("SELECT data FROM models")
            if row["data"]
        ]
        chats = [
            json.loads(row["data"]) for row in conn.execute("SELECT data FROM chats")
            if row["data"]
        ]
        users = {}
        for row in conn.execute("SELECT id, name, email FROM users"):
            users[row["id"]] = {
                "name": row["name"] or "",
                "email": row["email"] or "",
            }
    finally:
        conn.close()

    return models, chats, users


# === 1. Check if data refresh is needed ===
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def get_last_reload_timestamp(db_path: Path) -> Optional[datetime]:
    """Return the most recent reload completion time recorded in the database."""
    if not db_path.exists():
        return None

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT finished_at
            FROM reload_logs
            WHERE finished_at IS NOT NULL
            ORDER BY finished_at DESC
            LIMIT 1
            """
        ).fetchone()
    except sqlite3.DatabaseError:
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    if not row:
        return None

    finished_at = row["finished_at"]
    if not finished_at:
        return None

    if isinstance(finished_at, datetime):
        return finished_at

    if isinstance(finished_at, str):
        try:
            normalized = finished_at.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    return None


def check_and_refresh_if_needed():
    """Check if data is stale and refresh if necessary."""
    last_fetched = get_last_reload_timestamp(sqlite_db)
    needs_refresh = False

    if not last_fetched:
        print("⚠️  No reload history found - data refresh required")
        needs_refresh = True
    else:
        now = datetime.now(timezone.utc)
        time_since_refresh = now - last_fetched
        if time_since_refresh > timedelta(hours=1):
            hours_old = time_since_refresh.total_seconds() / 3600
            print(f"⚠️  Data is {hours_old:.1f} hours old - refreshing...")
            needs_refresh = True
        else:
            minutes = time_since_refresh.total_seconds() / 60
            print(f"✓ Data is fresh ({minutes:.1f} minutes old)")

    if needs_refresh:
        print("\n🔄 Refreshing data from Open WebUI...")
        try:
            response = requests.post(f"{API_BASE_URL}/refresh", timeout=60)
            response.raise_for_status()
            result = response.json()
            print("✓ Data refresh successful!")
            print(f"  Last fetched: {result.get('last_fetched', 'unknown')}")
            print(f"  Data source: {result.get('data_source', 'unknown')}")
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 400:
                print("✗ Warning: Cannot refresh - Open WebUI credentials not configured")
                print("  Set OPEN_WEBUI_HOSTNAME and OPEN_WEBUI_API_KEY to enable auto-refresh")
            else:
                print(f"✗ Warning: Data refresh failed: {exc}")
            print("  Continuing with existing stored data...")
        except requests.exceptions.RequestException as exc:
            print(f"✗ Warning: Data refresh failed: {exc}")
            print("  Continuing with existing stored data...")


print("=== CHECKING DATA FRESHNESS ===")
check_and_refresh_if_needed()

print("\n=== FETCHING DATA FROM SQLITE DATABASE ===")
try:
    models_payload, chats_payload, user_info_map = load_sqlite_payloads(sqlite_db)
except Exception as exc:
    print(f"✗ Failed to load raw data from SQLite database: {exc}")
    print("Ensure the backend database is initialized and populated with mission data.")
    exit(1)

model_lookup, mission_aliases, alias_to_primary, week_mapping, points_mapping, difficulty_mapping = extract_model_metadata(models_payload)

if not mission_aliases:
    print("✗ No mission-enabled models found in SQLite database.")
    exit(1)

filtered_chats = filter_mission_chats(chats_payload, mission_aliases)
if not filtered_chats:
    print("✗ No mission chats found in SQLite database.")
    exit(1)

user_names_only = {uid: info.get("name", "") for uid, info in user_info_map.items()}

analyzer = MissionAnalyzer(
    json_file=None,
    data=filtered_chats,
    user_names=user_names_only,
    model_lookup=model_lookup,
    mission_model_aliases=mission_aliases,
    model_alias_to_primary=alias_to_primary,
    week_mapping=week_mapping,
    points_mapping=points_mapping,
    difficulty_mapping=difficulty_mapping,
    verbose=False,
)
analyzer.analyze_missions()

seen_missions: Dict[str, Dict[str, str]] = {}
mission_display_names: List[str] = []
for alias in mission_aliases:
    display_name = model_lookup.get(alias, alias)
    primary_id = alias_to_primary.get(alias, alias)
    if display_name not in seen_missions:
        seen_missions[display_name] = {"alias": alias, "primary_id": primary_id}
        mission_display_names.append(display_name)

all_user_ids: Set[str] = set(user_info_map.keys())
for chat in analyzer.mission_chats:
    uid = chat.get("user_id")
    if uid:
        all_user_ids.add(uid)

completed_records: List[Dict[str, Optional[str]]] = []

for user_id in all_user_ids:
    user_capture = user_info_map.get(user_id, {})
    user_name = user_capture.get("name") or analyzer.get_user_name(user_id) or user_id
    user_email = user_capture.get("email", "")

    for challenge_name in mission_display_names:
        mission_info = seen_missions[challenge_name]
        alias = mission_info["alias"]
        primary_id = mission_info["primary_id"]

        user_attempts = [
            chat for chat in analyzer.mission_chats
            if chat.get("user_id") == user_id and analyzer._mission_matches_filter(chat.get("model"), challenge_name)
        ]

        if not user_attempts:
            continue

        user_attempts.sort(key=lambda chat: chat.get("created_at") or 0)
        completed_attempts = [attempt for attempt in user_attempts if attempt.get("completed")]
        if not completed_attempts:
            continue

        first_completion = completed_attempts[0]
        completed_idx = user_attempts.index(first_completion)
        completed_time = first_completion.get("created_at")

        points = points_mapping.get(alias) or points_mapping.get(primary_id)
        if points is None:
            for key, value in points_mapping.items():
                if key.lower() == alias.lower() or key.lower() == primary_id.lower():
                    points = value
                    break

        if isinstance(completed_time, (int, float)):
            completed_iso = datetime.fromtimestamp(completed_time).isoformat()
        else:
            completed_iso = completed_time

        completed_records.append(
            {
                "Name": user_name,
                "Email": user_email,
                "Challenge Name": challenge_name,
                "Status": "Completed",
                "Points Earned": points if points is not None else 0,
                "DateTime Completed": completed_iso,
            }
        )

if not completed_records:
    print("✗ No completed challenges found in SQLite data.")
    exit(1)

completed_df = pd.DataFrame(completed_records)

# Load awarded credit data from CSV file
awarded_df = pd.read_csv(project_root / "data" / "SubmittedActivityList.csv")

print("\n=== INITIAL DATA ===")
print(f"Total completed records: {len(completed_df)}")
print(f"Total awarded records: {len(awarded_df)}")

# === 2. Filter to only relevant rows ===
completed_df = completed_df[completed_df["Status"] == "Completed"].copy()
print(f"\nFiltered to completed challenges: {len(completed_df)} rows")

awarded_df = awarded_df[awarded_df["ActivityStatus"] == "Review Completed"].copy()
print(f"Filtered to awarded credit: {len(awarded_df)} rows")


# === 3. Normalize challenge names ===
def normalize_challenge_name(name):
    """Extract core challenge name from various formats."""
    if pd.isna(name):
        return None
    name = re.sub(r"Week \d+ - ", "", str(name))
    name = re.sub(r"Mission: ", "", name)
    name = re.sub(r" \(Easy\)", "", name)
    name = re.sub(r" \(Medium\)", "", name)
    name = re.sub(r" \(Hard\)", "", name)
    name = re.sub(r" \(Easy Difficulty\)", "", name)
    name = re.sub(r" \(Medium Difficulty\)", "", name)
    name = re.sub(r" \(Hard Difficulty\)", "", name)
    name = re.sub(r" Challenge$", "", name)
    return name.strip()


completed_df["normalized_challenge"] = completed_df["Challenge Name"].apply(normalize_challenge_name)
awarded_df["normalized_challenge"] = awarded_df["MissionChallenge"].apply(normalize_challenge_name)

print("\n=== NORMALIZED CHALLENGE NAMES ===")
print("Completed challenges:", completed_df["normalized_challenge"].unique())
print("Awarded challenges:", awarded_df["normalized_challenge"].unique())

# === 4. Normalize email addresses ===
completed_df["email_lower"] = completed_df["Email"].str.lower().str.strip()
awarded_df["email_lower"] = awarded_df["Email"].str.lower().str.strip()

# === 5. Create composite keys for matching ===
completed_df["match_key"] = completed_df["email_lower"] + "|" + completed_df["normalized_challenge"]
awarded_df["match_key"] = awarded_df["email_lower"] + "|" + awarded_df["normalized_challenge"]

# === 6. Merge to find who received credit ===
merged = completed_df.merge(
    awarded_df[["match_key", "PointsAwarded"]],
    on="match_key",
    how="left",
    indicator=True,
)

# === 7. Flag who received credit ===
merged["received_credit"] = merged["_merge"] == "both"

# === 8. Create detailed report ===
report = merged[
    [
        "Name",
        "Email",
        "Challenge Name",
        "normalized_challenge",
        "Points Earned",
        "PointsAwarded",
        "received_credit",
        "DateTime Completed",
    ]
].copy()

# Sort by received_credit (False first) and then by name
report = report.sort_values(["received_credit", "Name"])

# === 9. Summary statistics ===
print("\n" + "=" * 60)
print("SUMMARY REPORT")
print("=" * 60)
total = len(report)
received = report["received_credit"].sum()
not_received = total - received

print(f"\n✅ Total completed challenges: {total}")
print(f"🏆 Received credit: {received}")
print(f"❌ Did NOT receive credit: {not_received}")
print(f"📊 Credit rate: {received / total * 100:.1f}%")

# === 10. Show users who didn't receive credit ===
no_credit = report[~report["received_credit"]]
if len(no_credit) > 0:
    print(f"\n⚠️  {len(no_credit)} CHALLENGES COMPLETED BUT NOT CREDITED:")
    print("-" * 60)
    for _, row in no_credit.iterrows():
        print(f"  • {row['Name']} ({row['Email']})")
        print(f"    Challenge: {row['Challenge Name']}")
        print(f"    Completed: {row['DateTime Completed']}")
        print()

# === 11. Show unique users who are missing credit ===
users_missing_credit = no_credit.groupby(["Name", "Email"]).size().reset_index(name="challenges_missing")
if len(users_missing_credit) > 0:
    print(f"\n👥 {len(users_missing_credit)} USERS WITH MISSING CREDIT:")
    print("-" * 60)
    for _, row in users_missing_credit.iterrows():
        print(f"  • {row['Name']} ({row['Email']}) - {row['challenges_missing']} challenge(s)")

# === 12. Print detailed missing credit report to console ===
if len(no_credit) > 0:

    def extract_week(challenge_name):
        match = re.search(r"Week (\d+)", str(challenge_name))
        return match.group(1) if match else "N/A"

    no_credit_display = no_credit.copy()
    no_credit_display["Week"] = no_credit_display["Challenge Name"].apply(extract_week)

    print(f"\n{'=' * 90}")
    print("DETAILED MISSING CREDIT REPORT")
    print(f"{'=' * 90}")
    print(f"\n{'Name':<25} {'Email':<30} {'Week':<6} {'Challenge':<35} {'Points':<10}")
    print(f"{'-' * 25} {'-' * 30} {'-' * 6} {'-' * 35} {'-' * 10}")
    for _, row in no_credit_display.iterrows():
        print(
            f"{row['Name']:<25} {row['Email']:<30} "
            f"{row['Week']:<6} {row['normalized_challenge']:<35} {row['Points Earned']:<10}"
        )
    print(f"{'-' * 90}")
    print(f"Total missing credit: {len(no_credit)} challenges")

# === 13. Save combined output ===
exports_dir = project_root / "exports"
exports_dir.mkdir(exist_ok=True)

report.to_excel(exports_dir / "combined_report.xlsx", index=False)
print(f"\n📄 Full report saved as {exports_dir / 'combined_report.xlsx'}")

if len(no_credit) > 0:
    no_credit.to_excel(exports_dir / "missing_credit_report.xlsx", index=False)
    print(f"📄 Missing credit report saved as {exports_dir / 'missing_credit_report.xlsx'}")
