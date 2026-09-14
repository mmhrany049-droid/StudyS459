"""Question attempts — APPEND-ONLY evidence log (spec 02/06/13).

- Re-answering NEVER updates: every submission inserts a new row.
- Scoring always uses the LATEST row per (session, question).
- result NULL = not yet corrected (missing answer key -> pending flow).
  "unanswered" is DERIVED (no row, or latest row has NULL answer) and is
  never stored — finish creates zero rows (idempotent by construction).
- client_attempt_id (uuid, unique) makes double-submits safe (spec 13).
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"
    __table_args__ = (
        CheckConstraint("result IN ('correct', 'wrong')", name="ck_attempt_result"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    answer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    answered_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    response_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_attempt_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
