from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from .schemas import StatusIndicator, StatusSeverity


@dataclass
class CompletionRecord:
    """Represents a mission completion detected from OpenWebUI chats."""

    display_name: str
    normalized_name: str
    count: int = 1


@dataclass
class SubmissionRecord:
    """Represents a credited submission stored in SharePoint exports."""

    challenge_name: str
    normalized_name: str | None
    points_awarded: int
    expected_points: int | None


@dataclass
class UserStatusPayload:
    """Aggregated data passed to status rules for a single leaderboard row."""

    email: str
    normalized_email: str
    completions: Dict[str, CompletionRecord]
    submissions: List[SubmissionRecord]


class StatusRule:
    code: str
    label: str
    severity: StatusSeverity

    def evaluate(self, payload: UserStatusPayload) -> StatusIndicator | None:  # pragma: no cover - abstract behavior
        raise NotImplementedError


def _format_examples(names: List[str], limit: int = 3) -> List[str]:
    if not names:
        return []
    trimmed = names[:limit]
    if len(names) > limit:
        trimmed.append("…")
    return trimmed


class MissingCreditRule(StatusRule):
    code = "missing-credit"
    label = "Missing Credit"
    severity: StatusSeverity = "warning"

    def evaluate(self, payload: UserStatusPayload) -> StatusIndicator | None:
        if not payload.completions:
            return None

        credited = {
            record.normalized_name
            for record in payload.submissions
            if record.normalized_name
        }

        missing = [
            record.display_name
            for key, record in payload.completions.items()
            if key not in credited
        ]

        if not missing:
            return None

        message = "Completed missions detected in OpenWebUI are still missing Review Completed credit."
        return StatusIndicator(
            code=self.code,
            label=self.label,
            severity=self.severity,
            message=message,
            count=len(missing),
            examples=_format_examples(missing),
        )


class PointsMismatchRule(StatusRule):
    code = "points-mismatch"
    label = "Points Mismatch"
    severity: StatusSeverity = "error"

    def evaluate(self, payload: UserStatusPayload) -> StatusIndicator | None:
        mismatches: List[str] = []

        for record in payload.submissions:
            if record.expected_points is None:
                continue
            if record.points_awarded != record.expected_points:
                mismatches.append(record.challenge_name)

        if not mismatches:
            return None

        message = "Awarded points do not match the configured mission values."
        return StatusIndicator(
            code=self.code,
            label=self.label,
            severity=self.severity,
            message=message,
            count=len(mismatches),
            examples=_format_examples(mismatches),
        )


DEFAULT_STATUS_RULES: Sequence[StatusRule] = (
    MissingCreditRule(),
    PointsMismatchRule(),
)


def evaluate_status_rules(
    payload: UserStatusPayload,
    rules: Sequence[StatusRule] | None = None,
) -> List[StatusIndicator]:
    indicators: List[StatusIndicator] = []
    active_rules = rules or DEFAULT_STATUS_RULES
    for rule in active_rules:
        indicator = rule.evaluate(payload)
        if indicator:
            indicators.append(indicator)
    return indicators
