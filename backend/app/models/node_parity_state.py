"""Last used parity per (user, node) — drives the opposite suggestion (spec 06)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class NodeParityState(Base):
    __tablename__ = "node_parity_state"
    __table_args__ = (
        UniqueConstraint("user_id", "node_id", name="uq_parity_user_node"),
        CheckConstraint("last_parity IN ('odd', 'even')", name="ck_parity_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("book_nodes.id"), index=True)
    last_parity: Mapped[str] = mapped_column(String(8))
    last_used_at: Mapped[datetime] = mapped_column(default=utcnow)
