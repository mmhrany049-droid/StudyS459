"""Activation flag per (user, book). Deactivation NEVER deletes history (spec 05/13)."""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class UserBookActivation(Base):
    __tablename__ = "user_book_activations"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    activated_at: Mapped[datetime] = mapped_column(default=utcnow)
