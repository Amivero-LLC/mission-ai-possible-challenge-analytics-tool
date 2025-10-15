"""
Mission Analysis System for OpenWebUI challenge tracking.

This module parses OpenWebUI chat exports (or live API payloads) to identify AI
mission participation, completions, and other telemetry used by the analytics
dashboard. The goal is to provide a reusable, testable service layer that can
feed both CLI tools and the FastAPI backend.
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"


class MissionAnalyzer:
    """
    Core analytics engine used by the API and legacy CLI tools.

    The analyzer inspects chat transcripts, determines which conversations are
    mission-related, derives per-user statistics, and produces leaderboards and
    mission-specific breakdowns. It supports both on-disk JSON exports and
    in-memory payloads retrieved from the OpenWebUI REST API.

    Example:
        >>> analyzer = MissionAnalyzer(json_file="data/all-chats-export-20240101.json")
        >>> analyzer.analyze_missions(filter_week=1)
        12
        >>> summary = analyzer.get_summary()
        >>> summary["success_rate"]
        58.3
    """

    def __init__(self, json_file=None, user_names_file=None, verbose=True, data=None, user_names=None):
        """
        Initialize the analyzer with either a file path or an in-memory dataset.

        Args:
            json_file (str | pathlib.Path | None): Path to an OpenWebUI chat export.
                Required if ``data`` is not supplied. Supports relative paths.
            user_names_file (str | pathlib.Path | None): Optional mapping of
                ``user_id -> friendly_name``. Defaults to ``data/user_names.json``.
            verbose (bool): When True, prints informational messages about file
                loading and user-name merging. Useful for CLI usage.
            data (list[dict] | None): Preloaded chat objects (same structure as
                the export JSON). Supply this when streaming from OpenWebUI APIs.
            user_names (dict[str, str] | None): Additional name overrides, such
                as a dictionary returned from ``/api/v1/users/all``.

        Raises:
            ValueError: If both ``json_file`` and ``data`` are omitted, the class
                cannot operate because it has no chats to inspect.

        Side Effects:
            Loads chat data and user-name mappings eagerly so the instance is
            ready for analysis immediately after construction.
        """
        if json_file is None and data is None:
            raise ValueError("Either json_file or data must be provided to MissionAnalyzer")

        self.json_file = Path(json_file) if json_file else None
        self.user_names_file = Path(user_names_file) if user_names_file else DATA_DIR / "user_names.json"
        self.data = data or []
        self.mission_chats = []
        self.user_names = {}
        self.verbose = verbose
        # Tracks per-user aggregates used to build leaderboard and summaries.
        self.user_stats = defaultdict(
            lambda: {
                "user_id": "",
                "missions_attempted": [],
                "missions_completed": [],
                "total_attempts": 0,
                "total_completions": 0,
                "total_messages": 0,
                "first_attempt": None,
                "last_attempt": None,
            }
        )

        # Mission model patterns
        self.mission_patterns = [
            r"maip.*challenge",
            r"maip.*week",
            r".*mission.*",
            r".*challenge.*",
        ]

        # Success indicators (keywords in AI responses that indicate success)
        self.success_keywords = [
            "congratulations",
            "you did it",
            "success",
            "correct",
            "well done",
            "you found it",
            "unlocked",
            "revealed",
            "mission accomplished",
            "you passed",
            "challenge complete",
            "great job",
            "excellent work",
            "you succeeded",
            "you win",
            "you got it",
        ]

        if user_names:
            self.user_names.update(user_names)
            self.load_user_names(merge=True)
        else:
            self.load_user_names()
        if not self.data:
            self.load_data()

    def load_user_names(self, merge=False):
        """
        Populate ``self.user_names`` from the configured JSON mapping.

        Args:
            merge (bool): When True, incoming mappings are merged with the
                existing dictionary rather than replacing it. Use this when
                combining local mapping files with remote OpenWebUI user data.

        Returns:
            None. ``self.user_names`` is updated in place.

        Error Handling:
            - Missing files log a warning (when ``verbose`` is True) and leave
              ``self.user_names`` empty so the UI can fall back to UUIDs.
            - Invalid JSON triggers a warning and resets the mapping to {}.

        Side Effects:
            Reads from disk (``user_names_file``) and prints to stdout when
            ``verbose`` is enabled.
        """
        try:
            with open(self.user_names_file, "r", encoding="utf-8") as f:
                file_names = json.load(f)
            # Remove comment fields
            file_names = {k: v for k, v in file_names.items() if not k.startswith("_")}
            if merge:
                original = len(self.user_names)
                self.user_names.update(file_names)
                if self.verbose:
                    print(f"Merged {len(file_names)} user name mappings (from {original} existing)")
            else:
                self.user_names = file_names
                if self.verbose:
                    print(f"Loaded {len(self.user_names)} user name mappings")
        except FileNotFoundError:
            if self.verbose:
                print(f"No user_names.json found at {self.user_names_file} - showing user IDs")
            if not merge:
                self.user_names = {}
        except json.JSONDecodeError:
            if self.verbose:
                print(f"Warning: Invalid user_names.json at {self.user_names_file} - using default names")
            if not merge:
                self.user_names = {}

    def get_user_name(self, user_id):
        """
        Retrieve a display-friendly name for a user.

        Args:
            user_id (str): Raw identifier found in the chat export or API payload.

        Returns:
            str: Friendly name pulled from ``self.user_names`` if available,
            otherwise a shortened UUID (first 13 characters) to aid recognition.

        Usage:
            ``analyzer.get_user_name(chat["user_id"])`` inside aggregation loops.
        """
        if user_id in self.user_names:
            return self.user_names[user_id]
        # Show first 13 characters of UUID for better identification
        return user_id[:13] if len(user_id) > 13 else user_id

    def load_data(self):
        """
        Read chat transcripts from the configured JSON export.

        Returns:
            None. Populates ``self.data`` with the parsed list of chat records.

        Error Handling:
            - Missing files log an error (when ``verbose`` is True) and set
              ``self.data`` to an empty list so downstream loops are safe.
            - Malformed JSON triggers a similar warning and resets to [].

        Notes:
            ``self.json_file`` must be set; otherwise the method exits early.
        """
        if not self.json_file:
            if self.verbose:
                print("No JSON file provided; using data supplied directly.")
            return

        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            if self.verbose:
                print(f"Loaded {len(self.data)} chats from {self.json_file}")
        except FileNotFoundError:
            if self.verbose:
                print(f"Error: File {self.json_file} not found")
            self.data = []
        except json.JSONDecodeError:
            if self.verbose:
                print(f"Error: Invalid JSON in {self.json_file}")
            self.data = []

    def is_mission_model(self, model_name):
        """
        Determine whether a model string represents a mission challenge.

        Args:
            model_name (str): Model identifier taken from chat metadata.

        Returns:
            bool: True when the model matches any of the regex patterns defined
            in ``self.mission_patterns`` (case-insensitive).

        Business Rules:
            Mission models are identified heuristically via substring/regex
            matches on tokens like ``maip``, ``mission``, ``week``, and
            ``challenge``. These rules encapsulate naming conventions used by
            the challenge program.
        """
        model_lower = str(model_name).lower()
        for pattern in self.mission_patterns:
            if re.search(pattern, model_lower):
                return True
        return False

    def extract_mission_info(self, model_name):
        """
        Parse mission metadata (week/challenge identifiers) from a model string.

        Args:
            model_name (str): Original model descriptor as stored in a chat
                transcript or message.

        Returns:
            dict: Structure with the canonical ``mission_id`` plus numeric
            ``week`` and ``challenge`` fields when they can be derived. Missing
            values are represented as ``None``.

        Notes:
            Regular expressions are intentionally tolerant to account for
            hyphen/underscore variations (e.g., ``week-1`` or ``week_1``).
        """
        model_str = str(model_name).lower()

        # Try to extract week number
        week_match = re.search(r"week[-_]?(\d+)", model_str)
        week = int(week_match.group(1)) if week_match else None

        # Try to extract challenge number
        challenge_match = re.search(r"challenge[-_]?(\d+)", model_str)
        challenge = int(challenge_match.group(1)) if challenge_match else None

        return {
            "model": model_name,
            "week": week,
            "challenge": challenge,
            "mission_id": f"Week {week}, Challenge {challenge}" if week and challenge else model_name,
        }

    def check_success(self, messages):
        """
        Assess whether a mission chat ended in success.

        Args:
            messages (list[dict]): Sequence of chat messages. Each entry is
                expected to include ``role`` (assistant/user) and ``content``.

        Returns:
            bool: True if any assistant message includes a success keyword,
            signalling that the mission was marked complete.

        Business Rules:
            The keyword list encodes domain-specific phrases like
            ``"mission accomplished"`` and ``"you did it"`` that appear in AI
            confirmations when a challenge is solved.
        """
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()
                if any(keyword in content for keyword in self.success_keywords):
                    return True
        return False

    def analyze_missions(self, filter_challenge=None, filter_user=None, filter_status=None, filter_date_from=None, filter_date_to=None):
        """
        Inspect chats and populate mission-related aggregates.

        Args:
            filter_challenge (str | None): Restrict analysis to missions matching
                the given model name or mission ID. ``None`` keeps all challenges.
            filter_user (str | None): Restrict analysis to chats by the given
                ``user_id``. Useful for per-participant reports.
            filter_status (str | None): Restrict analysis based on completion status.
                Options: "completed" (only completed missions) or "attempted" 
                (only incomplete attempts). ``None`` keeps all statuses.
            filter_date_from (str | None): Filter chats created on or after this date (ISO format).
            filter_date_to (str | None): Filter chats created on or before this date (ISO format).

        Returns:
            int: Count of mission-attempt chats that satisfied the filters.

        Side Effects:
            - Resets and repopulates ``self.mission_chats`` with structured
              mission metadata per chat.
            - Mutates ``self.user_stats`` so subsequent calls to
              ``get_leaderboard`` and ``get_summary`` use fresh aggregates.

        Example:
            >>> analyzer.analyze_missions(filter_status="completed", filter_date_from="2025-01-01")
            4

        Notes:
            The method attempts to detect mission participation from both the
            chat-level ``models`` array and per-message ``model`` fields to
            handle exports where model attribution differs.
        """
        self.mission_chats = []

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

        for i, item in enumerate(self.data, 1):
            chat = item.get("chat", {})
            models = chat.get("models", [])
            messages = chat.get("messages", [])

            # Check if any model is a mission model
            mission_model = None
            for model in models:
                if self.is_mission_model(model):
                    mission_model = model
                    break

            # Also check individual messages
            if not mission_model:
                for msg in messages:
                    msg_model = msg.get("model", "")
                    if msg_model and self.is_mission_model(msg_model):
                        mission_model = msg_model
                        break

            if mission_model:
                mission_info = self.extract_mission_info(mission_model)
                user_id = item.get("user_id", "Unknown")
                title = item.get("title", "Untitled")
                created_at = item.get("created_at")

                # Check if completed
                completed = self.check_success(messages)

                # Apply filters
                if filter_challenge and mission_info["mission_id"] != filter_challenge:
                    continue
                if filter_user and user_id != filter_user:
                    continue
                if filter_status:
                    if filter_status.lower() == "completed" and not completed:
                        continue
                    elif filter_status.lower() == "attempted" and completed:
                        continue
                
                # Apply date filter
                if date_from_ts or date_to_ts:
                    chat_timestamp = created_at if isinstance(created_at, (int, float)) else None
                    if chat_timestamp:
                        if date_from_ts and chat_timestamp < date_from_ts:
                            continue
                        if date_to_ts and chat_timestamp > date_to_ts:
                            continue

                mission_data = {
                    "chat_num": i,
                    "user_id": user_id,
                    "title": title,
                    "model": mission_model,
                    "mission_info": mission_info,
                    "messages": messages,
                    "message_count": len(messages),
                    "created_at": created_at,
                    "completed": completed,
                }

                self.mission_chats.append(mission_data)

                # Update user stats
                self.user_stats[user_id]["user_id"] = user_id
                self.user_stats[user_id]["missions_attempted"].append(mission_info["mission_id"])
                self.user_stats[user_id]["total_attempts"] += 1
                self.user_stats[user_id]["total_messages"] += len(messages)

                if completed:
                    self.user_stats[user_id]["missions_completed"].append(mission_info["mission_id"])
                    self.user_stats[user_id]["total_completions"] += 1

                if not self.user_stats[user_id]["first_attempt"]:
                    self.user_stats[user_id]["first_attempt"] = created_at
                self.user_stats[user_id]["last_attempt"] = created_at

        return len(self.mission_chats)

    def get_leaderboard(self, sort_by="completions"):
        """
        Produce a mission leaderboard with selectable ordering.

        Args:
            sort_by (str): One of ``"completions"``, ``"attempts"``, or
                ``"efficiency"``. Defaults to completions.

        Returns:
            list[dict]: Each entry contains mission attempt/completion counts,
            efficiency percentage, and message totals for a user.

        Business Rules:
            - Efficiency represents ``completions / attempts * 100``.
            - Sorting prioritizes the requested metric and falls back to
              secondary keys (e.g., completions also considers attempts to break ties).

        Example:
            >>> leaderboard = analyzer.get_leaderboard(sort_by="efficiency")
            >>> leaderboard[0]["user_id"]
            'user-123'
        """
        leaderboard = []

        for user_id, stats in self.user_stats.items():
            # Calculated percentages drive the efficiency leaderboard view.
            efficiency = (
                stats["total_completions"] / stats["total_attempts"] * 100 if stats["total_attempts"] > 0 else 0
            )

            leaderboard.append(
                {
                    "user_id": user_id,
                    "attempts": stats["total_attempts"],
                    "completions": stats["total_completions"],
                    "efficiency": efficiency,
                    "total_messages": stats["total_messages"],
                    "unique_missions_attempted": len(set(stats["missions_attempted"])),
                    "unique_missions_completed": len(set(stats["missions_completed"])),
                    "first_attempt": stats["first_attempt"],
                    "last_attempt": stats["last_attempt"],
                }
            )

        # Sort based on criteria
        if sort_by == "completions":
            leaderboard.sort(key=lambda x: (x["completions"], -x["attempts"]), reverse=True)
        elif sort_by == "attempts":
            leaderboard.sort(key=lambda x: x["attempts"], reverse=True)
        elif sort_by == "efficiency":
            leaderboard.sort(key=lambda x: (x["efficiency"], x["completions"]), reverse=True)

        return leaderboard

    def get_summary(self):
        """
        Summarize high-level mission statistics for dashboards.

        Returns:
            dict: Aggregate metrics such as ``total_chats``, ``mission_attempts``,
            ``mission_completions``, ``success_rate``, and unique counts.

        Notes:
            Success rate is calculated as ``completions / attempts * 100`` and
            guarded against division by zero.
        """
        total_attempts = len(self.mission_chats)
        total_completions = sum(1 for chat in self.mission_chats if chat["completed"])
        unique_users = len(self.user_stats)

        success_rate = (total_completions / total_attempts * 100) if total_attempts > 0 else 0

        # Get unique missions and weeks
        unique_missions = set()
        unique_weeks = set()
        for chat in self.mission_chats:
            unique_missions.add(chat["mission_info"]["mission_id"])
            week = chat["mission_info"]["week"]
            if week is not None:
                unique_weeks.add(week)

        # Get unique users with their names from ALL chats (not just mission participants)
        users_list = []
        seen_users = set()
        for item in self.data:
            user_id = item.get("user_id", "Unknown")
            if user_id and user_id not in seen_users and user_id != "Unknown":
                users_list.append({
                    "user_id": user_id,
                    "user_name": self.get_user_name(user_id)
                })
                seen_users.add(user_id)
        
        # Sort by user name
        users_list.sort(key=lambda x: x["user_name"])

        return {
            "total_chats": len(self.data),
            "mission_attempts": total_attempts,
            "mission_completions": total_completions,
            "success_rate": success_rate,
            "unique_users": unique_users,
            "unique_missions": len(unique_missions),
            "missions_list": sorted(unique_missions),
            "weeks_list": sorted(list(unique_weeks)),
            "users_list": users_list,
        }

    def get_mission_breakdown(self):
        """
        Return mission-level attempt and completion counts.

        Returns:
            list[dict]: Sorted in descending order by attempts. Each dictionary
            contains ``mission``, ``attempts``, ``completions``, ``success_rate``,
            and ``unique_users`` metrics.

        Usage:
            Feed directly into dashboard tables or CSV exports.
        """
        breakdown = defaultdict(lambda: {"attempts": 0, "completions": 0, "users": set()})

        for chat in self.mission_chats:
            mission_id = chat["mission_info"]["mission_id"]
            breakdown[mission_id]["attempts"] += 1
            breakdown[mission_id]["users"].add(chat["user_id"])
            if chat["completed"]:
                breakdown[mission_id]["completions"] += 1

        # Convert to list
        result = []
        for mission_id, stats in breakdown.items():
            result.append(
                {
                    "mission": mission_id,
                    "attempts": stats["attempts"],
                    "completions": stats["completions"],
                    "success_rate": (stats["completions"] / stats["attempts"] * 100) if stats["attempts"] > 0 else 0,
                    "unique_users": len(stats["users"]),
                }
            )

        result.sort(key=lambda x: x["attempts"], reverse=True)
        return result


def find_latest_export():
    """
    Locate the newest OpenWebUI export in the ``data/`` directory.

    Returns:
        str | None: Path to the most recent export file (by filename ordering),
        or ``None`` if the directory is missing or empty.

    Dependencies:
        Relies on consistent naming (`all-chats-export-<timestamp>.json`).
    """
    if not DATA_DIR.exists():
        return None

    json_files = sorted(DATA_DIR.glob("all-chats-export-*.json"), reverse=True)
    if not json_files:
        return None
    # Sort by filename (timestamp in filename)
    return str(json_files[0])


if __name__ == "__main__":
    # Find latest export
    latest_file = find_latest_export()

    if not latest_file:
        print("No export files found! Please add a chat export JSON file to the data/ directory.")
        exit(1)

    print(f"Using: {latest_file}\n")

    # Initialize analyzer
    analyzer = MissionAnalyzer(latest_file)

    # Analyze all missions
    mission_count = analyzer.analyze_missions()

    # Get summary
    summary = analyzer.get_summary()

    print("=" * 80)
    print("MISSION ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total Chats in Export: {summary['total_chats']}")
    print(f"Mission Attempts: {mission_count}")
    print(f"Mission Completions: {summary['mission_completions']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Unique Participants: {summary['unique_users']}")
    print(f"Unique Missions: {summary['unique_missions']}")

    if summary["missions_list"]:
        print(f"\nMissions Found:")
        for mission in summary["missions_list"]:
            print(f"  - {mission}")

    print("\n" + "=" * 80)

    if mission_count == 0:
        print("No mission attempts found yet!")
        print("\nWaiting for employees to attempt missions using models like:")
        print("  - maip---week-1---challenge-1")
        print("  - maip---week-1---challenge-2")
        print("  - etc.")
    else:
        # Show leaderboard
        print("\nTOP PERFORMERS (by completions):")
        print("-" * 80)
        leaderboard = analyzer.get_leaderboard(sort_by="completions")

        for i, user in enumerate(leaderboard[:10], 1):
            print(f"{i}. User: {user['user_id'][:30]}...")
            print(
                f"   Completions: {user['completions']} | Attempts: {user['attempts']} | "
                f"Efficiency: {user['efficiency']:.1f}%"
            )

        # Mission breakdown
        print("\n" + "=" * 80)
        print("MISSION BREAKDOWN")
        print("=" * 80)
        breakdown = analyzer.get_mission_breakdown()
        for mission_stats in breakdown:
            print(f"\n{mission_stats['mission']}")
            print(f"  Attempts: {mission_stats['attempts']}")
            print(f"  Completions: {mission_stats['completions']}")
            print(f"  Success Rate: {mission_stats['success_rate']:.1f}%")
            print(f"  Unique Users: {mission_stats['unique_users']}")

    print("\n" + "=" * 80)
