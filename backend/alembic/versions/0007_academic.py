"""Academic: schedules, class sessions, taught lessons, homework, exams (Phase 6).

Deliberately NOT built: exam_subject_results (its percentage/score columns
conflict with open decisions #1/#6 — no percent/score formulas in v1).
Exam analytics stay count-based and are computed live.
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_academic"
down_revision = "0006_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("schedule_type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("recurring", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(32), nullable=True),
        sa.CheckConstraint("schedule_type IN ('school','external')", name="ck_schedule_type"),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_schedule_dow"),
    )
    op.create_table(
        "class_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attended", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "taught_lessons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("class_session_id", sa.Integer(), sa.ForeignKey("class_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("taught_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "homework",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priority", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.CheckConstraint("source_type IN ('school','external','manual')", name="ck_homework_source"),
        sa.CheckConstraint("status IN ('pending','done','cancelled')", name="ck_homework_status"),
        sa.CheckConstraint("estimated_minutes >= 0", name="ck_homework_minutes_nonneg"),
    )
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("exam_type", sa.String(32), nullable=False, server_default="custom"),
        sa.Column("provider", sa.String(128), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("images_metadata", sa.JSON(), nullable=True),
    )
    op.create_table(
        "exam_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic_node_id", sa.Integer(), sa.ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("answer_key", sa.String(8), nullable=True),
        sa.Column("user_answer", sa.String(8), nullable=True),
        sa.Column("result", sa.String(16), nullable=True),
        sa.UniqueConstraint("exam_id", "sequence_no", name="uq_exam_question_seq"),
        sa.CheckConstraint("result IN ('correct','wrong','unanswered')", name="ck_exam_question_result"),
    )


def downgrade() -> None:
    op.drop_table("exam_questions")
    op.drop_table("exams")
    op.drop_table("homework")
    op.drop_table("taught_lessons")
    op.drop_table("class_sessions")
    op.drop_table("schedules")
