"""Track challenge attempts for faster dashboard loading

Revision ID: 20241105001
Revises: 20240904001
Create Date: 2024-11-05 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20241105001"
down_revision = "20240904001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "challenge_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("chat_id", sa.String(), nullable=True),
        sa.Column("chat_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("mission_id", sa.String(), nullable=True),
        sa.Column("mission_model", sa.String(), nullable=True),
        sa.Column("mission_week", sa.String(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.String(), nullable=True),
        sa.Column("updated_at_raw", sa.String(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_challenge_attempts_chat_id", "challenge_attempts", ["chat_id"])
    op.create_index("ix_challenge_attempts_user_id", "challenge_attempts", ["user_id"])
    op.create_index("ix_challenge_attempts_mission_id", "challenge_attempts", ["mission_id"])
    op.create_index("ix_challenge_attempts_mission_model", "challenge_attempts", ["mission_model"])
    op.create_index("ix_challenge_attempts_mission_week", "challenge_attempts", ["mission_week"])


def downgrade() -> None:
    op.drop_index("ix_challenge_attempts_mission_week", table_name="challenge_attempts")
    op.drop_index("ix_challenge_attempts_mission_model", table_name="challenge_attempts")
    op.drop_index("ix_challenge_attempts_mission_id", table_name="challenge_attempts")
    op.drop_index("ix_challenge_attempts_user_id", table_name="challenge_attempts")
    op.drop_index("ix_challenge_attempts_chat_id", table_name="challenge_attempts")
    op.drop_table("challenge_attempts")
