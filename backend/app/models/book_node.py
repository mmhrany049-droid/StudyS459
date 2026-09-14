"""BookNode — generic tree, any depth, open node types (spec 02/04/05).

Node types are NOT an enum: chapter/lesson/title/section/subsection/leaf
or any custom type from the book config. No per-book conditions anywhere.
"""

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BookNode(Base):
    __tablename__ = "book_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True, index=True)
    node_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    code: Mapped[str] = mapped_column(String(128), index=True)
    order_index: Mapped[int] = mapped_column(Integer)
    # Column is `metadata_json` per spec; attribute shortened (Base.metadata taken).
    meta: Mapped[dict[str, Any]] = mapped_column("metadata_json", JSON, default=dict)
