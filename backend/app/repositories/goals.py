"""Weekly goals persistence (spec 04 planning section)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WeeklyGoal, WeeklyGoalItem


def get_goal_by_week(db: Session, user_id: int, week_start: date) -> WeeklyGoal | None:
    return db.execute(
        select(WeeklyGoal).where(
            WeeklyGoal.user_id == user_id, WeeklyGoal.week_start == week_start
        )
    ).scalar_one_or_none()


def get_goal(db: Session, user_id: int, goal_id: int) -> WeeklyGoal | None:
    return db.execute(
        select(WeeklyGoal).where(WeeklyGoal.id == goal_id, WeeklyGoal.user_id == user_id)
    ).scalar_one_or_none()


def create_goal(
    db: Session, *, user_id: int, week_start: date, week_end: date, active: bool = True
) -> WeeklyGoal:
    goal = WeeklyGoal(user_id=user_id, week_start=week_start, week_end=week_end, active=active)
    db.add(goal)
    db.flush()
    return goal


def add_item(
    db: Session,
    *,
    goal_id: int,
    goal_type: str,
    target_value: float,
    subject_id: int | None = None,
    book_id: int | None = None,
    node_id: int | None = None,
) -> WeeklyGoalItem:
    item = WeeklyGoalItem(
        goal_id=goal_id, goal_type=goal_type, target_value=target_value,
        subject_id=subject_id, book_id=book_id, node_id=node_id,
    )
    db.add(item)
    db.flush()
    return item


def replace_items(db: Session, goal: WeeklyGoal, items: list[dict]) -> None:
    for existing in list(goal.items):
        db.delete(existing)
    db.flush()
    for it in items:
        add_item(db, goal_id=goal.id, **it)
