"""test engine tables (Phase 2, spec 04 test section).

Revision ID: 0003_test_engine
Revises: 0002_book_engine
Create Date: 2026-09-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_test_engine"
down_revision: str | None = "0002_book_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # Plain int for now: tasks table (Phase 4/5) adds validation/FK.
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("timed", sa.Boolean(), nullable=False),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=True),
        sa.Column("sequence_from", sa.Integer(), nullable=True),
        sa.Column("sequence_to", sa.Integer(), nullable=True),
        sa.Column("parity", sa.String(length=8), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.CheckConstraint(
            "status IN ('in_progress', 'pending_correction', 'completed')",
            name="ck_session_status",
        ),
        sa.CheckConstraint("parity IN ('odd', 'even', 'any')", name="ck_session_parity"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_sessions_user_id", "test_sessions", ["user_id"])
    op.create_index("ix_test_sessions_task_id", "test_sessions", ["task_id"])
    op.create_index("ix_test_sessions_started_at", "test_sessions", ["started_at"])
    op.create_index("ix_test_sessions_status", "test_sessions", ["status"])

    op.create_table(
        "test_session_questions",
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["test_sessions.id"]),
        sa.PrimaryKeyConstraint("session_id", "question_id"),
    )

    op.create_table(
        "question_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("answer", sa.String(length=64), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
        sa.Column("response_time_seconds", sa.Integer(), nullable=True),
        sa.Column("client_attempt_id", sa.String(length=36), nullable=False),
        sa.CheckConstraint("result IN ('correct', 'wrong')", name="ck_attempt_result"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["test_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_attempts_session_id", "question_attempts", ["session_id"])
    op.create_index("ix_question_attempts_question_id", "question_attempts", ["question_id"])
    op.create_index("ix_question_attempts_user_id", "question_attempts", ["user_id"])
    op.create_index("ix_question_attempts_answered_at", "question_attempts", ["answered_at"])
    op.create_index(
        "ix_question_attempts_client_id", "question_attempts", ["client_attempt_id"], unique=True
    )

    op.create_table(
        "node_parity_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("last_parity", sa.String(length=8), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("last_parity IN ('odd', 'even')", name="ck_parity_value"),
        sa.ForeignKeyConstraint(["node_id"], ["book_nodes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "node_id", name="uq_parity_user_node"),
    )
    op.create_index("ix_node_parity_state_user_id", "node_parity_state", ["user_id"])
    op.create_index("ix_node_parity_state_node_id", "node_parity_state", ["node_id"])


def downgrade() -> None:
    op.drop_table("node_parity_state")
    op.drop_table("question_attempts")
    op.drop_table("test_session_questions")
    op.drop_table("test_sessions")
