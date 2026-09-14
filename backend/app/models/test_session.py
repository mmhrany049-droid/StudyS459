"""Test session + session questions (spec 04/06).

- One row per selected question; composite PK (session_id, question_id)
  makes "no duplicate inside a session" STRUCTURAL (spec 13).
- task_id is a plain nullable int for now: the tasks table lands in
  Phase 4/5, which will add validation/FK. Stored as-is until then.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow

SESSION_STATUSES: tuple[str, ...] = ("in_progress", "pending_correction", "completed")
SESSION_PARITIES: tuple[str, ...] = ("odd", "even", "any")


class TestSession(Base):
    __tablename__ = "test_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('in_progress', 'pending_correction', 'completed')", name="ck_session_status"),
        CheckConstraint("parity IN ('odd', 'even', 'any')", name="ck_session_parity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    timed: Mapped[bool] = mapped_column(default=False)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parity: Mapped[str] = mapped_column(String(8), default="any")
    started_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="in_progress", index=True)


class TestSessionQuestion(Base):
    __tablename__ = "test_session_questions"

    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    display_order: Mapped[int] = mapped_column(Integer)  # 1-based, sampled order
