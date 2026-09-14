"""book review queue (Phase 3, spec 04 analytics section).

Revision ID: 0004_review_queue
Revises: 0003_test_engine
Create Date: 2026-09-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_review_queue"
down_revision: str | None = "0003_test_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # 'question' in v1; open vocabulary (Phase 6 exams may add types).
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        # Always NULL in v1: spaced repetition is deferred (spec 18 #3).
        sa.Column("scheduled_for", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("reason IN ('wrong', 'unanswered')", name="ck_review_reason"),
        sa.CheckConstraint("priority IN ('high', 'normal')", name="ck_review_priority"),
        sa.CheckConstraint("status IN ('pending', 'done')", name="ck_review_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_queue_user_id", "review_queue", ["user_id"])
    op.create_index("ix_review_queue_status", "review_queue", ["status"])
    op.create_index("ix_review_queue_entity", "review_queue", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("review_queue")
