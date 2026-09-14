"""Weekly goals + goal items (Phase 4, spec 04 planning section).

tasks / daily_task_placements arrive with the Planner (Phase 5):
candidate tasks in Phase 4 are computed, not stored.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_weekly_goals"
down_revision = "0004_review_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "week_start", name="uq_weekly_goal_user_week"),
    )
    op.create_table(
        "weekly_goal_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("weekly_goals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("goal_type", sa.String(16), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("goal_type IN ('count','topic')", name="ck_goal_item_type"),
        sa.CheckConstraint("target_value > 0", name="ck_goal_item_target_positive"),
    )


def downgrade() -> None:
    op.drop_table("weekly_goal_items")
    op.drop_table("weekly_goals")
