"""Planner persistence: tasks, placements, school-day overrides."""

from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DailyTaskPlacement, SchoolDayOverride, Task


def get_task(db: Session, user_id: int, task_id: int) -> Task | None:
    return db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    ).scalar_one_or_none()


def list_tasks(db: Session, user_id: int) -> list[Task]:
    return list(
        db.execute(
            select(Task).where(Task.user_id == user_id).order_by(Task.id)
        ).scalars().all()
    )


def create_task(db: Session, **fields) -> Task:
    task = Task(**fields)
    db.add(task)
    db.flush()
    return task


def tasks_by_source(db: Session, source_type: str, source_id: int) -> list[Task]:
    return list(
        db.execute(
            select(Task).where(Task.source_type == source_type, Task.source_id == source_id)
            .order_by(Task.id)
        ).scalars().all()
    )


def latest_task_by_source(db: Session, source_type: str, source_id: int) -> Task | None:
    rows = tasks_by_source(db, source_type, source_id)
    return rows[-1] if rows else None


def complete_tasks_by_source(
    db: Session, source_type: str, source_id: int, *, completed_at: datetime
) -> list[Task]:
    flipped: list[Task] = []
    for task in tasks_by_source(db, source_type, source_id):
        if task.status in ("planned", "in_progress"):
            task.status = "completed"
            task.completed_at = completed_at
            flipped.append(task)
    db.flush()
    return flipped


def complete_task_if_open(db: Session, task_id: int, *, completed_at: datetime) -> bool:
    """Idempotent completion for engine hooks. Returns True if it flipped."""
    task = db.get(Task, task_id)
    if task is None or task.status in ("completed", "cancelled"):
        return False
    task.status = "completed"
    task.completed_at = completed_at
    db.flush()
    return True


def placements_on(db: Session, user_id: int, day: date) -> list[DailyTaskPlacement]:
    return list(
        db.execute(
            select(DailyTaskPlacement)
            .join(Task, Task.id == DailyTaskPlacement.task_id)
            .where(Task.user_id == user_id, DailyTaskPlacement.date == day)
            .order_by(DailyTaskPlacement.position, DailyTaskPlacement.task_id)
        ).scalars().all()
    )


def placements_between(
    db: Session, user_id: int, start: date, end: date
) -> list[DailyTaskPlacement]:
    return list(
        db.execute(
            select(DailyTaskPlacement)
            .join(Task, Task.id == DailyTaskPlacement.task_id)
            .where(
                Task.user_id == user_id,
                DailyTaskPlacement.date >= start,
                DailyTaskPlacement.date <= end,
            )
            .order_by(DailyTaskPlacement.date, DailyTaskPlacement.position,
                      DailyTaskPlacement.task_id)
        ).scalars().all()
    )


def clear_dates(db: Session, user_id: int, days: list[date]) -> None:
    if not days:
        return
    sub = select(Task.id).where(Task.user_id == user_id)
    db.execute(
        delete(DailyTaskPlacement).where(
            DailyTaskPlacement.task_id.in_(sub),
            DailyTaskPlacement.date.in_(days),
        )
    )
    db.flush()


def upsert_placement(db: Session, *, task_id: int, day: date, position: int) -> DailyTaskPlacement:
    row = db.get(DailyTaskPlacement, task_id)
    if row is None:
        row = DailyTaskPlacement(task_id=task_id, date=day, position=position)
        db.add(row)
    else:
        row.date = day
        row.position = position
    db.flush()
    return row


def get_override(db: Session, user_id: int, day: date) -> SchoolDayOverride | None:
    return db.execute(
        select(SchoolDayOverride).where(
            SchoolDayOverride.user_id == user_id, SchoolDayOverride.date == day
        )
    ).scalar_one_or_none()


def upsert_override(
    db: Session, *, user_id: int, day: date, is_school_day: bool, reason: str | None
) -> SchoolDayOverride:
    row = get_override(db, user_id, day)
    if row is None:
        row = SchoolDayOverride(
            user_id=user_id, date=day, is_school_day=is_school_day, reason=reason)
        db.add(row)
    else:
        row.is_school_day = is_school_day
        row.reason = reason
    db.flush()
    return row
