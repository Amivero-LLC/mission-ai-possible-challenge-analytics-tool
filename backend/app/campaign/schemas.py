from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field


class SubmissionReloadSummary(BaseModel):
    rows_inserted: int = Field(..., ge=0)
    users_created: int = Field(..., ge=0)
    users_updated: int = Field(..., ge=0)
    missions_linked: int = Field(..., ge=0)


class CampaignUserInfo(BaseModel):
    firstName: str | None = None
    lastName: str | None = None
    email: str


StatusSeverity = Literal["info", "warning", "error"]


class StatusIndicator(BaseModel):
    code: str
    label: str
    severity: StatusSeverity = Field(default="info")
    message: str
    count: int | None = Field(default=None, ge=0)
    examples: List[str] = Field(default_factory=list)


class ActivityWeekSummary(BaseModel):
    participants: int = Field(..., ge=0)
    points: int = Field(..., ge=0)


class ActivityOverviewEntry(BaseModel):
    activityType: str
    totalParticipants: int = Field(..., ge=0)
    totalPoints: int = Field(..., ge=0)
    weeks: Dict[int, ActivityWeekSummary] = Field(default_factory=dict)


class CampaignLeaderboardRow(BaseModel):
    user: CampaignUserInfo
    pointsByWeek: Dict[int, float] = Field(default_factory=dict)
    totalPoints: float = Field(..., ge=0)
    currentRank: int = Field(..., ge=0)
    statusIndicators: List[StatusIndicator] = Field(default_factory=list)


class CampaignSummaryResponse(BaseModel):
    weeks_present: List[int] = Field(default_factory=list)
    rows: List[CampaignLeaderboardRow] = Field(default_factory=list)
    last_upload_at: str | None = None
    activity_overview: List[ActivityOverviewEntry] = Field(default_factory=list)
