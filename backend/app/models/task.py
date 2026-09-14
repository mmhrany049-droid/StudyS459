"""Planner tasks + daily placements + school-day overrides (spec 04/08)."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

TASK_TYPES = ("test", "review", "study")
TASK_SOURCES = ("goal", "review", "weakness", "manual", "homework", "exam")
TASK_STATUSES = ("planned", "in_progress", "completed", "cancelled")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("task_type IN ('test','review','study')", name="ck_task_type"),
        CheckConstraint(
            "source_type IN ('goal','review','weakness','manual','homework','exam')",
            name="ck_task_source",
        ),
        CheckConstraint(
            "status IN ('planned','in_progress','completed','cancelled')",
            name="ck_task_status",
        ),
        CheckConstraint("estimated_minutes >= 0", name="ck_task_minutes_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256))
    source_type: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Test execution params (pinned at creation; the engine never re-derives).
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True
    )
    question_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parity: Mapped[str | None] = mapped_column(String(8), nullable=True)
    priority: Mapped[float] = mapped_column(Float, default=0.5)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="planned")
    recommendation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    placement: Mapped["DailyTaskPlacement | None"] = relationship(
        back_populates="task", cascade="all, delete-orphan", uselist=False
    )


class DailyTaskPlacement(Base):
    """One placement per task (v1); moves are delete+insert via PUT."""

    __tablename__ = "daily_task_placements"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    task: Mapped[Task] = relationship(back_populates="placement")


class SchoolDayOverride(Base):
    __tablename__ = "school_day_overrides"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_override_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    is_school_day: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
