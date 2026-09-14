"""Import receipts: content hash per import (idempotency, spec 13).

Kept as a separate table so `books` stays exactly per spec 04 columns.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class BookImport(Base):
    __tablename__ = "book_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    config_hash: Mapped[str] = mapped_column(String(64), index=True)
    config_version: Mapped[int] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(default=utcnow)
