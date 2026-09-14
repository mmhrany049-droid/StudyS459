"""Subject model (spec 04). Auto-created from book configs (get-or-create)."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("name", "grade", "track", name="uq_subject_name_grade_track"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    grade: Mapped[int] = mapped_column(Integer)
    track: Mapped[str] = mapped_column(String(64))
    # Column is `type` per spec; attribute renamed to avoid shadowing builtin.
    subject_type: Mapped[str] = mapped_column("type", String(64))
