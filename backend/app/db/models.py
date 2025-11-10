from __future__ import annotations

from typing import List, Optional

from sqlalchemy import (
    Boolean,
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    sharepoint_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True)
    total_points: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    current_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chats: Mapped[List["Chat"]] = relationship("Chat", back_populates="user")


class Model(Base):
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    maip_week: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    maip_difficulty: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    maip_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), index=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at_remote: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at_remote: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[Optional["User"]] = relationship("User", back_populates="chats")


class SubmittedActivity(Base):
    __tablename__ = "submitted_activity_list"
    __table_args__ = (
        Index("idx_sal_user", "user_sharepoint_id"),
        Index("idx_sal_week", "week_id"),
        Index("idx_sal_activity", "activity_id"),
        Index("idx_sal_model", "mission_model_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_sharepoint_id: Mapped[int] = mapped_column(Integer, nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    activity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)
    activity_status: Mapped[str] = mapped_column(Text, nullable=False)
    points_awarded: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    week_id: Mapped[int] = mapped_column(Integer, nullable=False)
    attachments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    use_case_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    use_case_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    use_case_story: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    use_case_how: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    use_case_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    training_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    training_reflection: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    training_duration: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    training_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    demo_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    demo_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mission_challenge_week: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mission_challenge: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mission_challenge_response: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    quiz_topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quiz_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    quiz_completion_date: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    created: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    mission_model_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("models.id", ondelete="SET NULL"), nullable=True)

    mission_model: Mapped[Optional["Model"]] = relationship("Model")


class Rank(Base):
    __tablename__ = "ranks"

    rank_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    rank_name: Mapped[str] = mapped_column(Text, nullable=False)
    minimum_points: Mapped[int] = mapped_column(Integer, nullable=False)
    swag: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_raffle_tickets: Mapped[int] = mapped_column(Integer, nullable=False)


class ReloadLog(Base):
    __tablename__ = "reload_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False, default="upsert")
    status: Mapped[str] = mapped_column(String, nullable=False, default="success")
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rows_affected: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    previous_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    new_records: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)


Index("idx_sal_email", func.lower(SubmittedActivity.email))
Index("idx_users_email_lc", func.lower(User.email))
