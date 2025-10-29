from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field

# Pydantic models capture the shape of the dashboard API response payloads.


class SortOption(str, Enum):
    completions = "completions"
    attempts = "attempts"
    efficiency = "efficiency"


class UserInfo(BaseModel):
    user_id: str
    user_name: str
    email: Optional[str] = None


class Summary(BaseModel):
    total_chats: int = Field(..., ge=0)
    mission_attempts: int = Field(..., ge=0)
    mission_completions: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0)
    unique_users: int = Field(..., ge=0)
    unique_missions: int = Field(..., ge=0)
    missions_list: List[str] = Field(default_factory=list)
    missions_with_weeks: dict = Field(default_factory=dict)  # mission_name -> week
    weeks_list: List[int] = Field(default_factory=list)
    users_list: List[UserInfo] = Field(default_factory=list)
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
    first_attempt: Optional[Union[str, int, float]] = None
    last_attempt: Optional[Union[str, int, float]] = None
    total_points: int = Field(default=0, ge=0)


class MissionBreakdownEntry(BaseModel):
    mission: str
    attempts: int = Field(..., ge=0)
    completions: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0)
    unique_users: int = Field(..., ge=0)
    users_attempted: int = Field(..., ge=0)
    users_completed: int = Field(..., ge=0)
    users_not_started: int = Field(..., ge=0)
    avg_messages_to_complete: float = Field(..., ge=0)
    avg_attempts_to_complete: float = Field(..., ge=0)
    week: str = ""
    difficulty: str = ""
    points: int = Field(default=0, ge=0)


class ChatMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[Union[str, int, float]] = None


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
    week: Optional[Union[int, str]] = None
    challenge_name: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)


class ChallengeResultEntry(BaseModel):
    user_id: str
    user_name: str
    status: str  # "Completed", "Attempted", or empty string
    num_attempts: int = Field(..., ge=0)
    first_attempt_time: Optional[Union[str, int, float]] = None
    completed_time: Optional[Union[str, int, float]] = None
    num_messages: int = Field(..., ge=0)


class UserChallengeExportRow(BaseModel):
    user_name: str
    email: str
    challenge_name: str
    status: str  # "Completed", "Attempted", or "Empty"
    completed: str  # "Yes" or "No"
    num_attempts: int = Field(default=0, ge=0)
    num_messages: int = Field(default=0, ge=0)
    week: str
    difficulty: str
    datetime_started: Optional[str] = None
    datetime_completed: Optional[str] = None
    points_earned: int = Field(default=0, ge=0)


class DashboardResponse(BaseModel):
    generated_at: datetime
    last_fetched: Optional[str] = None
    data_source: Optional[str] = None
    summary: Summary
    leaderboard: List[LeaderboardEntry] = Field(default_factory=list)
    mission_breakdown: List[MissionBreakdownEntry] = Field(default_factory=list)
    all_chats: List[ChatPreview] = Field(default_factory=list)
    challenge_results: List[ChallengeResultEntry] = Field(default_factory=list)
    export_data: List[UserChallengeExportRow] = Field(default_factory=list)


class ChallengeAttempt(BaseModel):
    challenge_name: str
    challenge_id: str
    week: str
    difficulty: str
    points: int = Field(default=0, ge=0)
    status: str  # "Completed", "Attempted", or "Not Started"
    num_attempts: int = Field(default=0, ge=0)
    num_messages: int = Field(default=0, ge=0)
    first_attempt_time: Optional[Union[str, int, float]] = None
    completed_time: Optional[Union[str, int, float]] = None


class UserWithChallenges(BaseModel):
    user_id: str
    user_name: str
    email: Optional[str] = None
    total_attempts: int = Field(default=0, ge=0)
    total_completions: int = Field(default=0, ge=0)
    total_points: int = Field(default=0, ge=0)
    efficiency: float = Field(default=0.0, ge=0)
    challenges: List[ChallengeAttempt] = Field(default_factory=list)


class UsersResponse(BaseModel):
    generated_at: datetime
    users: List[UserWithChallenges] = Field(default_factory=list)


class UserParticipation(BaseModel):
    user_id: str
    user_name: str
    email: Optional[str] = None
    status: str  # "Completed", "Attempted", or "Not Started"
    num_attempts: int = Field(default=0, ge=0)
    num_messages: int = Field(default=0, ge=0)
    first_attempt_time: Optional[Union[str, int, float]] = None
    completed_time: Optional[Union[str, int, float]] = None


class ChallengeWithUsers(BaseModel):
    challenge_name: str
    challenge_id: str
    week: str
    difficulty: str
    points: int = Field(default=0, ge=0)
    total_attempts: int = Field(default=0, ge=0)
    total_completions: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0)
    users_attempted: int = Field(default=0, ge=0)
    users_completed: int = Field(default=0, ge=0)
    users_not_started: int = Field(default=0, ge=0)
    avg_messages_to_complete: float = Field(default=0.0, ge=0)
    avg_attempts_to_complete: float = Field(default=0.0, ge=0)
    participants: List[UserParticipation] = Field(default_factory=list)


class ChallengesResponse(BaseModel):
    generated_at: datetime
    challenges: List[ChallengeWithUsers] = Field(default_factory=list)
