"""TestSet model (spec 02/04). test_type is a closed v1 vocabulary."""

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ALLOWED_TEST_TYPES: tuple[str, ...] = (
    "normal",
    "checkup",
    "chapter_exam",
    "comprehensive",
    "concours",
    "mock",
    "custom",
)


class TestSet(Base):
    __tablename__ = "test_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    test_type: Mapped[str] = mapped_column(String(32), index=True)
    node_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True, index=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata_json", JSON, default=dict)
