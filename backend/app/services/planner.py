"""Planner: tasks, placements, capacity, catch-up (spec 02/08, Phase 5).

- Friday plans the Sat..Fri week; mid-week edits stay valid till Friday.
- Sat..Wed are school days, Thu/Fri free (rule 7); an explicit override
  flips any date. Phase 5 capacity = weekday default; class schedules
  subtract from it in Phase 6.
- The user owns placement; the system only warns on over-capacity and
  never deletes anything automatically.
"""

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.analytics.metrics import normalize_week, user_day
from app.db import utcnow
from app.errors import AppError
from app.models import Task
from app.repositories import books as book_repo
from app.repositories import planner as repo
from app.schemas.planner import (
    DayPlanOut,
    OverrideIn,
    OverrideOut,
    PlacedTaskOut,
    PlacementIn,
    TaskCreate,
    TaskOut,
    TaskPatch,
    WeekPlanOut,
    WorkloadRowOut,
)
from app.services.users import get_or_create_single_user

SCHOOL_DAY_CAPACITY_MINUTES = 90
FREE_DAY_CAPACITY_MINUTES = 240
# Monday=0..Sunday=6: Thu(3)/Fri(4) are free days (rule 7).
FREE_WEEKDAYS = frozenset({3, 4})
OPEN_STATUSES = ("planned", "in_progress")
TRANSITIONS = {
    "planned": ("in_progress", "completed", "cancelled"),
    "in_progress": ("planned", "completed", "cancelled"),
    "completed": (),
    "cancelled": (),
}


def _today(tz: str) -> date:
    return user_day(utcnow().replace(tzinfo=None), tz)


def _day_kind(db: Session, user_id: int, day: date) -> tuple[bool, bool]:
    """(is_school_day, override_present)."""
    override = repo.get_override(db, user_id, day)
    if override is not None:
        return override.is_school_day, True
    return day.weekday() not in FREE_WEEKDAYS, False


def _capacity(is_school_day: bool) -> int:
    return SCHOOL_DAY_CAPACITY_MINUTES if is_school_day else FREE_DAY_CAPACITY_MINUTES


def _is_overdue(task: Task, today: date, tz: str) -> bool:
    return (
        task.status in OPEN_STATUSES
        and task.due_at is not None
        and user_day(task.due_at, tz) < today
    )


def _placed_map(db: Session, tasks: list[Task]) -> dict[int, date]:
    from app.models import DailyTaskPlacement

    ids = [t.id for t in tasks]
    if not ids:
        return {}
    from sqlalchemy import select

    rows = db.execute(
        select(DailyTaskPlacement.task_id, DailyTaskPlacement.date).where(
            DailyTaskPlacement.task_id.in_(ids)
        )
    ).all()
    return {tid: d for tid, d in rows}


def _task_out(
    task: Task, *, today: date, tz: str, placed_on: date | None,
    points_earned: int | None = None,
) -> TaskOut:
    return TaskOut(
        id=task.id, task_type=task.task_type,  # type: ignore[arg-type]
        title=task.title, source_type=task.source_type,  # type: ignore[arg-type]
        source_id=task.source_id, node_id=task.node_id,
        question_count=task.question_count, sequence_from=task.sequence_from,
        sequence_to=task.sequence_to, parity=task.parity, priority=task.priority,
        estimated_minutes=task.estimated_minutes, due_at=task.due_at,
        status=task.status,  # type: ignore[arg-type]
        is_overdue=_is_overdue(task, today, tz),
        recommendation_reason=task.recommendation_reason,
        created_at=task.created_at, completed_at=task.completed_at,
        placed_on=placed_on, points_earned=points_earned,
    )


def _validate_source(db: Session, source_type: str, source_id: int | None) -> None:
    if source_id is None:
        return
    if source_type == "goal":
        from app.models import WeeklyGoalItem

        if db.get(WeeklyGoalItem, source_id) is None:
            raise AppError("invalid_task_source", "آیتم هدف یافت نشد.", status_code=422)
    elif source_type == "review":
        from app.models import ReviewQueue

        if db.get(ReviewQueue, source_id) is None:
            raise AppError("invalid_task_source", "ردیف مرور یافت نشد.", status_code=422)
    elif source_type == "weakness":
        if book_repo.get_node(db, source_id) is None:
            raise AppError("invalid_task_source", "گره ضعف یافت نشد.", status_code=422)
    elif source_type == "homework":
        from app.models import Homework

        if db.get(Homework, source_id) is None:
            raise AppError("invalid_task_source", "تکلیف یافت نشد.", status_code=422)
    elif source_type == "exam":
        from app.models import Exam

        if db.get(Exam, source_id) is None:
            raise AppError("invalid_task_source", "امتحان یافت نشد.", status_code=422)


def create_task(db: Session, *, user_id: int, payload: TaskCreate) -> TaskOut:
    user = get_or_create_single_user(db, user_id)
    _validate_source(db, payload.source_type, payload.source_id)
    if not 0 <= payload.priority <= 1:
        raise AppError("invalid_task", "اولویت باید بین ۰ تا ۱ باشد.", status_code=422)
    if payload.estimated_minutes < 0:
        raise AppError("invalid_task", "زمان تخمینی نمی‌تواند منفی باشد.", status_code=422)
    node_id = payload.node_id
    parity = payload.parity or "any"
    if payload.task_type == "test":
        if node_id is None or book_repo.get_node(db, node_id) is None:
            raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
        if not payload.question_count or payload.question_count < 1:
            raise AppError("invalid_task", "تسک تست نیاز به question_count مثبت دارد.", status_code=422)
        if payload.sequence_from is not None and payload.sequence_from < 1:
            raise AppError("invalid_task", "sequence_from باید مثبت باشد.", status_code=422)
        if (payload.sequence_from is not None and payload.sequence_to is not None
                and payload.sequence_to < payload.sequence_from):
            raise AppError("invalid_task", "sequence_to نمی‌تواند کمتر از sequence_from باشد.", status_code=422)
    elif node_id is not None and book_repo.get_node(db, node_id) is None:
        raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
    try:
        task = repo.create_task(
            db, user_id=user.id, task_type=payload.task_type, title=payload.title,
            source_type=payload.source_type, source_id=payload.source_id,
            node_id=node_id, question_count=payload.question_count,
            sequence_from=payload.sequence_from, sequence_to=payload.sequence_to,
            parity=parity if payload.task_type == "test" else None,
            priority=payload.priority, estimated_minutes=payload.estimated_minutes,
            due_at=payload.due_at, status="planned",
            recommendation_reason=payload.recommendation_reason,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    today = _today(user.timezone)
    return _task_out(task, today=today, tz=user.timezone, placed_on=None)


def patch_task(db: Session, *, user_id: int, task_id: int, payload: TaskPatch) -> TaskOut:
    from app.services import rewards as rewards_service

    user = get_or_create_single_user(db, user_id)
    task = repo.get_task(db, user.id, task_id)
    if task is None:
        raise AppError("task_not_found", "تسک یافت نشد.", status_code=404)
    if payload.priority is not None and not 0 <= payload.priority <= 1:
        raise AppError("invalid_task", "اولویت باید بین ۰ تا ۱ باشد.", status_code=422)
    if payload.estimated_minutes is not None and payload.estimated_minutes < 0:
        raise AppError("invalid_task", "زمان تخمینی نمی‌تواند منفی باشد.", status_code=422)
    points: int | None = None
    try:
        if payload.status is not None and payload.status != task.status:
            if payload.status not in TRANSITIONS[task.status]:
                raise AppError(
                    "invalid_transition",
                    f"تغییر وضعیت از {task.status} به {payload.status} مجاز نیست.",
                    status_code=422,
                )
            task.status = payload.status
            task.completed_at = utcnow().replace(tzinfo=None) if payload.status == "completed" else None
            if payload.status == "completed":
                db.flush()
                points = rewards_service.on_task_completed(
                    db, user.id, task, tz=user.timezone)
        if payload.title is not None:
            task.title = payload.title
        if payload.priority is not None:
            task.priority = payload.priority
        if payload.estimated_minutes is not None:
            task.estimated_minutes = payload.estimated_minutes
        if payload.due_at is not None:
            task.due_at = payload.due_at
        if payload.recommendation_reason is not None:
            task.recommendation_reason = payload.recommendation_reason
        db.commit()
    except AppError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    today = _today(user.timezone)
    placed = _placed_map(db, [task]).get(task.id)
    return _task_out(task, today=today, tz=user.timezone, placed_on=placed,
                     points_earned=points)


def complete_task(db: Session, *, user_id: int, task_id: int) -> TaskOut:
    """Manual completion; already-completed is an idempotent success."""
    from app.services import rewards as rewards_service

    user = get_or_create_single_user(db, user_id)
    task = repo.get_task(db, user.id, task_id)
    if task is None:
        raise AppError("task_not_found", "تسک یافت نشد.", status_code=404)
    if task.status == "cancelled":
        raise AppError("invalid_transition", "تسک لغوشده را نمی‌توان کامل کرد.", status_code=422)
    points: int | None = None
    try:
        if task.status != "completed":
            task.status = "completed"
            task.completed_at = utcnow().replace(tzinfo=None)
            db.flush()
            points = rewards_service.on_task_completed(
                db, user.id, task, tz=user.timezone)
        db.commit()
    except Exception:
        db.rollback()
        raise
    today = _today(user.timezone)
    placed = _placed_map(db, [task]).get(task.id)
    return _task_out(task, today=today, tz=user.timezone, placed_on=placed,
                     points_earned=points)


def put_placements(
    db: Session, *, user_id: int, items: list[PlacementIn], extra_dates: list[date] | None = None
) -> list[DayPlanOut]:
    """Replace placements wholesale for every date in the payload.

    Replaced = dates of the rows + explicit `dates` (so a day can be
    cleared by naming it with no rows).
    """
    user = get_or_create_single_user(db, user_id)
    if not items and not extra_dates:
        raise AppError("empty_placements", "لیست placement خالی است.", status_code=422)
    by_task = {it.task_id: it for it in items}  # last wins on duplicates
    for task_id in by_task:
        if repo.get_task(db, user.id, task_id) is None:
            raise AppError("task_not_found", f"تسک {task_id} یافت نشد.",
                           status_code=404, details={"task_id": task_id})
    days = sorted({it.date for it in by_task.values()} | set(extra_dates or []))
    try:
        repo.clear_dates(db, user.id, days)
        for it in by_task.values():
            repo.upsert_placement(db, task_id=it.task_id, day=it.date, position=it.position)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return [_day_plan(db, user.id, user.timezone, d) for d in days]


def _day_plan(db: Session, user_id: int, tz: str, day: date) -> DayPlanOut:
    from app.schemas.academic import ScheduleOut
    from app.services import academic as academic_service

    is_school, overridden = _day_kind(db, user_id, day)
    scheduled_minutes, sched_rows = academic_service.day_schedules(
        db, user_id, day, is_school_day=is_school)
    capacity = max(0, _capacity(is_school) - scheduled_minutes)
    today = _today(tz)
    rows = repo.placements_on(db, user_id, day)
    tasks = [db.get(Task, r.task_id) for r in rows]
    placed = _placed_map(db, [t for t in tasks if t])
    items: list[PlacedTaskOut] = []
    workload: list[WorkloadRowOut] = []
    total = 0
    for r, task in zip(rows, tasks):
        if task is None:  # pragma: no cover - FK cascade prevents this
            continue
        items.append(PlacedTaskOut(
            position=r.position,
            task=_task_out(task, today=today, tz=tz, placed_on=placed.get(task.id)),
        ))
        if task.status in OPEN_STATUSES:
            workload.append(WorkloadRowOut(
                task_id=task.id, title=task.title, estimated_minutes=task.estimated_minutes))
            total += task.estimated_minutes
    return DayPlanOut(
        date=day, weekday=day.weekday(), is_school_day=is_school,
        override=overridden, capacity_minutes=capacity,
        scheduled_minutes=scheduled_minutes,
        workload_minutes=total, over_capacity=total > capacity,
        workload=workload, placements=items,
        schedules=[
            ScheduleOut(
                id=s.id, schedule_type=s.schedule_type,  # type: ignore[arg-type]
                title=s.title, day_of_week=s.day_of_week,
                start_time=s.start_time, end_time=s.end_time,
                recurring=s.recurring, date=s.date,
                subject_id=s.subject_id, node_id=s.node_id, source=s.source,
                duration_minutes=int(
                    (s.end_time.hour * 60 + s.end_time.minute)
                    - (s.start_time.hour * 60 + s.start_time.minute)),
            )
            for s in sched_rows
        ],
    )


def day_plan(db: Session, *, user_id: int, day: date) -> DayPlanOut:
    user = get_or_create_single_user(db, user_id)
    return _day_plan(db, user.id, user.timezone, day)


def week_plan(db: Session, *, user_id: int, week: str) -> WeekPlanOut:
    from datetime import timedelta

    from app.services.goals import parse_week

    user = get_or_create_single_user(db, user_id)
    start, end = parse_week(week)
    days = [_day_plan(db, user.id, user.timezone, start + timedelta(days=i)) for i in range(7)]
    today = _today(user.timezone)
    open_tasks = [t for t in repo.list_tasks(db, user.id) if t.status in OPEN_STATUSES]
    placed = _placed_map(db, open_tasks)
    unplaced = [
        _task_out(t, today=today, tz=user.timezone, placed_on=None)
        for t in open_tasks if t.id not in placed
    ]

    def catch_key(t: Task):
        overdue = _is_overdue(t, today, user.timezone)
        return (
            not overdue,
            t.task_type != "review",
            t.source_type != "goal",
            -t.priority,
            t.due_at is None,
            t.due_at or datetime.max,
            t.id,
        )

    catch_up = [
        _task_out(t, today=today, tz=user.timezone, placed_on=placed.get(t.id))
        for t in sorted(open_tasks, key=catch_key)
    ]
    return WeekPlanOut(week_start=start, week_end=end, days=days,
                       unplaced=unplaced, catch_up=catch_up)


def set_override(db: Session, *, user_id: int, payload: OverrideIn) -> OverrideOut:
    user = get_or_create_single_user(db, user_id)
    try:
        row = repo.upsert_override(
            db, user_id=user.id, day=payload.date,
            is_school_day=payload.is_school_day, reason=payload.reason,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return OverrideOut(date=row.date, is_school_day=row.is_school_day, reason=row.reason)
