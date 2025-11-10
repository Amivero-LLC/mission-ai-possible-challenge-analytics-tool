"""Add campaign dashboard tables and columns

Revision ID: 20240904001
Revises:
Create Date: 2024-09-04 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = "20240904001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submitted_activity_list",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_sharepoint_id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("activity_type", sa.Text(), nullable=False),
        sa.Column("activity_status", sa.Text(), nullable=False),
        sa.Column("points_awarded", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("week_id", sa.Integer(), nullable=False),
        sa.Column("attachments", sa.Integer(), nullable=True),
        sa.Column("use_case_title", sa.Text(), nullable=True),
        sa.Column("use_case_type", sa.Text(), nullable=True),
        sa.Column("use_case_story", sa.Text(), nullable=True),
        sa.Column("use_case_how", sa.Text(), nullable=True),
        sa.Column("use_case_value", sa.Text(), nullable=True),
        sa.Column("training_title", sa.Text(), nullable=True),
        sa.Column("training_reflection", sa.Text(), nullable=True),
        sa.Column("training_duration", sa.Numeric(6, 2), nullable=True),
        sa.Column("training_link", sa.Text(), nullable=True),
        sa.Column("demo_title", sa.Text(), nullable=True),
        sa.Column("demo_description", sa.Text(), nullable=True),
        sa.Column("mission_challenge_week", sa.Text(), nullable=True),
        sa.Column("mission_challenge", sa.Text(), nullable=True),
        sa.Column("mission_challenge_response", sa.Numeric(10, 2), nullable=True),
        sa.Column("quiz_topic", sa.Text(), nullable=True),
        sa.Column("quiz_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("quiz_completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mission_model_id", sa.String(), sa.ForeignKey("models.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("idx_sal_user", "submitted_activity_list", ["user_sharepoint_id"])
    op.create_index("idx_sal_week", "submitted_activity_list", ["week_id"])
    op.create_index("idx_sal_activity", "submitted_activity_list", ["activity_id"])
    op.create_index("idx_sal_model", "submitted_activity_list", ["mission_model_id"])
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_sal_email ON submitted_activity_list (LOWER(email))"))

    op.add_column("users", sa.Column("sharepoint_user_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("total_points", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("current_rank", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("uq_users_sharepoint", "users", ["sharepoint_user_id"], unique=True)
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email_lc ON users (LOWER(email))"))

    op.create_table(
        "ranks",
        sa.Column("rank_number", sa.Integer(), primary_key=True),
        sa.Column("rank_name", sa.Text(), nullable=False),
        sa.Column("minimum_points", sa.Integer(), nullable=False),
        sa.Column("swag", sa.Text(), nullable=True),
        sa.Column("total_raffle_tickets", sa.Integer(), nullable=False),
    )

    ranks_table = sa.table(
        "ranks",
        sa.column("rank_number", sa.Integer()),
        sa.column("rank_name", sa.Text()),
        sa.column("minimum_points", sa.Integer()),
        sa.column("swag", sa.Text()),
        sa.column("total_raffle_tickets", sa.Integer()),
    )
    op.bulk_insert(
        ranks_table,
        [
            {"rank_number": 0, "rank_name": "None", "minimum_points": 0, "swag": "None", "total_raffle_tickets": 0},
            {"rank_number": 1, "rank_name": "Analyst", "minimum_points": 150, "swag": "Sticker", "total_raffle_tickets": 1},
            {"rank_number": 2, "rank_name": "Agent", "minimum_points": 300, "swag": None, "total_raffle_tickets": 3},
            {"rank_number": 3, "rank_name": "Field Agent", "minimum_points": 500, "swag": "Custom Water Bottle", "total_raffle_tickets": 7},
            {"rank_number": 4, "rank_name": "Secret Agent", "minimum_points": 750, "swag": "Custom Hoodie", "total_raffle_tickets": 15},
        ],
    )


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS idx_users_email_lc"))
    op.drop_table("ranks")
    op.drop_index("uq_users_sharepoint", table_name="users")
    op.drop_column("users", "current_rank")
    op.drop_column("users", "total_points")
    op.drop_column("users", "sharepoint_user_id")
    op.execute(text("DROP INDEX IF EXISTS idx_sal_email"))
    op.drop_index("idx_sal_model", table_name="submitted_activity_list")
    op.drop_index("idx_sal_activity", table_name="submitted_activity_list")
    op.drop_index("idx_sal_week", table_name="submitted_activity_list")
    op.drop_index("idx_sal_user", table_name="submitted_activity_list")
    op.drop_table("submitted_activity_list")
