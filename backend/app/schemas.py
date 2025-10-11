from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class SortOption(str, Enum):
    completions = "completions"
    attempts = "attempts"
    efficiency = "efficiency"


class Summary(BaseModel):
    total_chats: int = Field(..., ge=0)
    mission_attempts: int = Field(..., ge=0)
    mission_completions: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0)
    unique_users: int = Field(..., ge=0)
    unique_missions: int = Field(..., ge=0)
    missions_list: List[str] = Field(default_factory=list)
    participation_rate: float = Field(..., ge=0)


class LeaderboardEntry(BaseModel):
    user_id: str
    user_name: str
    attempts: int = Field(..., ge=0)
    completions: int = Field(..., ge=0)
    efficiency: float = Field(..., ge=0)
    total_messages: int = Field(..., ge=0)
    unique_missions_attempted: int = Field(..., ge=0)
    unique_missions_completed: int = Field(..., ge=0)


class MissionBreakdownEntry(BaseModel):
    mission: str
    attempts: int = Field(..., ge=0)
    completions: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0)
    unique_users: int = Field(..., ge=0)


class ChatMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class ChatPreview(BaseModel):
    num: int = Field(..., ge=1)
    title: str
    user_id: str
    user_name: str
    created_at: Optional[Union[str, int, float]] = None
    model: str
    message_count: int = Field(..., ge=0)
    is_mission: bool
    completed: bool
    messages: List[ChatMessage] = Field(default_factory=list)


class ModelStatsEntry(BaseModel):
    model: str
    total: int = Field(..., ge=0)
    mission: int = Field(..., ge=0)
    completed: int = Field(..., ge=0)
    mission_percentage: float = Field(..., ge=0)


class DashboardResponse(BaseModel):
    generated_at: datetime
    summary: Summary
    leaderboard: List[LeaderboardEntry] = Field(default_factory=list)
    mission_breakdown: List[MissionBreakdownEntry] = Field(default_factory=list)
    all_chats: List[ChatPreview] = Field(default_factory=list)
    model_stats: List[ModelStatsEntry] = Field(default_factory=list)
