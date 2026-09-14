"""Question model (spec 02/04). answer_key NULLABLE (spec 11/13 missing-key flow)."""

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("book_id", "stable_key", name="uq_question_book_stable_key"),
        UniqueConstraint("test_set_id", "sequence_no", name="uq_question_testset_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    stable_key: Mapped[str] = mapped_column(String(256), index=True)
    test_set_id: Mapped[int] = mapped_column(ForeignKey("test_sets.id"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, index=True)
    difficulty_level: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    answer_type: Mapped[str] = mapped_column(String(32), default="choice")
    answer_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata_json", JSON, default=dict)
