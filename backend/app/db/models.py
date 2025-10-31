from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chats: Mapped[list["Chat"]] = relationship("Chat", back_populates="user")


class Model(Base):
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at_remote: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at_remote: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User | None] = relationship("User", back_populates="chats")


class ReloadLog(Base):
    __tablename__ = "reload_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False, default="upsert")
    status: Mapped[str] = mapped_column(String, nullable=False, default="success")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rows_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
