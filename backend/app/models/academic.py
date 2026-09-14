"""Academic records: schedules, class sessions, taught, homework, exams (spec 04/09).

Taught lessons NEVER feed analytics (taught != learned). Exam analytics stay
count-based (open decisions #1/#6 forbid percent/score formulas in v1).
"""

from datetime import date as dt_date, datetime, time  # dt_date: fields named `date` can't self-annotate

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

SCHEDULE_TYPES = ("school", "external")
HOMEWORK_SOURCES = ("school", "external", "manual")
HOMEWORK_STATUSES = ("pending", "done", "cancelled")
EXAM_QUESTION_RESULTS = ("correct", "wrong", "unanswered")


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint("schedule_type IN ('school','external')", name="ck_schedule_type"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_schedule_dow"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    schedule_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256))
    day_of_week: Mapped[int] = mapped_column(Integer)  # Monday=0..Sunday=6
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    recurring: Mapped[bool] = mapped_column(Boolean, default=True)
    date: Mapped[dt_date | None] = mapped_column(Date, nullable=True)  # one-offs only
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ClassSession(Base):
    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True)
    date: Mapped[dt_date] = mapped_column(Date, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"))
    attended: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class TaughtLesson(Base):
    __tablename__ = "taught_lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    class_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_sessions.id", ondelete="SET NULL"), nullable=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"))
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True)
    taught_at: Mapped[datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Homework(Base):
    __tablename__ = "homework"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('school','external','manual')", name="ck_homework_source"),
        CheckConstraint(
            "status IN ('pending','done','cancelled')", name="ck_homework_status"),
        CheckConstraint("estimated_minutes >= 0", name="ck_homework_minutes_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"))
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(16), default="pending")


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    exam_type: Mapped[str] = mapped_column(String(32), default="custom")
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exam_date: Mapped[dt_date] = mapped_column(Date)
    total_questions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    images_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    __table_args__ = (
        UniqueConstraint("exam_id", "sequence_no", name="uq_exam_question_seq"),
        CheckConstraint(
            "result IN ('correct','wrong','unanswered')", name="ck_exam_question_result"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer)
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    topic_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True)
    answer_key: Mapped[str | None] = mapped_column(String(8), nullable=True)
    user_answer: Mapped[str | None] = mapped_column(String(8), nullable=True)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
