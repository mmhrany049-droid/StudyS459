"""Weekly goals: one row per user+week, items carry count/topic targets (spec 02)."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class WeeklyGoal(Base):
    __tablename__ = "weekly_goals"
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_weekly_goal_user_week"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[date] = mapped_column(Date)  # Saturday
    week_end: Mapped[date] = mapped_column(Date)  # Friday
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["WeeklyGoalItem"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", order_by="WeeklyGoalItem.id"
    )


class WeeklyGoalItem(Base):
    __tablename__ = "weekly_goal_items"
    __table_args__ = (
        CheckConstraint("goal_type IN ('count','topic')", name="ck_goal_item_type"),
        CheckConstraint("target_value > 0", name="ck_goal_item_target_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_goals.id", ondelete="CASCADE"), index=True
    )
    goal_type: Mapped[str] = mapped_column(String(16))  # count | topic
    target_value: Mapped[float] = mapped_column(Float)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True
    )
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    goal: Mapped[WeeklyGoal] = relationship(back_populates="items")
