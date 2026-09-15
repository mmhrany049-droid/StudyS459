"""Rewards: events + badges + user badges (Phase 7, spec 10).

Badge rows are seeded idempotently by the rewards service (single mechanism
that also works for test databases built via create_all).
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_rewards"
down_revision = "0007_academic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reward_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("related_entity_type", sa.String(32), nullable=True),
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "badges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("condition_type", sa.String(64), nullable=False),
        sa.Column("condition_value", sa.String(64), nullable=False),
    )
    op.create_table(
        "user_badges",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("badge_id", sa.Integer(), sa.ForeignKey("badges.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("earned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_badges")
    op.drop_table("badges")
    op.drop_table("reward_events")
