"""Review queue model (spec 04). Populated at session finish (spec 03 chain)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class ReviewQueue(Base):
    __tablename__ = "review_queue"
    __table_args__ = (
        CheckConstraint("reason IN ('wrong', 'unanswered')", name="ck_review_reason"),
        CheckConstraint("priority IN ('high', 'normal')", name="ck_review_priority"),
        CheckConstraint("status IN ('pending', 'done')", name="ck_review_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    reason: Mapped[str] = mapped_column(String(16))
    priority: Mapped[str] = mapped_column(String(16))
    scheduled_for: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
