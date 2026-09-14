"""Planner: tasks + daily placements + school-day overrides (Phase 5).

school_day_overrides is included here (not Phase 6) because capacity depends
on it; full class schedules deepen capacity in Phase 6.
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_planner"
down_revision = "0005_weekly_goals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("task_type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=True),
        sa.Column("sequence_from", sa.Integer(), nullable=True),
        sa.Column("sequence_to", sa.Integer(), nullable=True),
        sa.Column("parity", sa.String(8), nullable=True),
        sa.Column("priority", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="planned"),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("task_type IN ('test','review','study')", name="ck_task_type"),
        sa.CheckConstraint("source_type IN ('goal','review','weakness','manual','homework','exam')", name="ck_task_source"),
        sa.CheckConstraint("status IN ('planned','in_progress','completed','cancelled')", name="ck_task_status"),
        sa.CheckConstraint("estimated_minutes >= 0", name="ck_task_minutes_nonneg"),
    )
    op.create_table(
        "daily_task_placements",
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "school_day_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("is_school_day", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "date", name="uq_override_user_date"),
    )


def downgrade() -> None:
    op.drop_table("school_day_overrides")
    op.drop_table("daily_task_placements")
    op.drop_table("tasks")
