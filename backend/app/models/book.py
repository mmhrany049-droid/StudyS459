"""Book model (spec 02/04). Identity = stable_key (never reused)."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stable_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256))
    publisher: Mapped[str] = mapped_column(String(128))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    grade: Mapped[int] = mapped_column(Integer)
    track: Mapped[str] = mapped_column(String(64))
    edition: Mapped[str] = mapped_column(String(64))
    config_version: Mapped[int] = mapped_column(Integer)
