from __future__ import annotations

from typing import Dict, List

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


class CampaignLeaderboardRow(BaseModel):
    user: CampaignUserInfo
    pointsByWeek: Dict[int, float] = Field(default_factory=dict)
    totalPoints: float = Field(..., ge=0)
    currentRank: int = Field(..., ge=0)


class CampaignSummaryResponse(BaseModel):
    weeks_present: List[int] = Field(default_factory=list)
    rows: List[CampaignLeaderboardRow] = Field(default_factory=list)
    last_upload_at: str | None = None
