"""Planning router: tasks (manual control), weekly planner, capacity, activities."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.timeutil import today_local, week_end, week_label_fa, week_start
from ...db import models
from ...db.base import get_db
from ...domain import activity_types as activity_registry
from ...services import (
    capacity as capacity_service,
    common,
    planner,
    tasks as tasks_service,
)
from ..deps import current_user, parse_day

router = APIRouter(tags=["planning"])


class TaskPayload(BaseModel):
    title: str
    task_type: str = "other"
    intervention_type: Optional[str] = None
    book_id: Optional[int] = None
    topic_id: Optional[int] = None
    goal_id: Optional[int] = None
    exam_id: Optional[int] = None
    planned_date: Optional[str] = None
    planned_start_time: Optional[str] = None
    planned_question_count: Optional[int] = None
    planned_minutes: Optional[int] = None
    duration_low: Optional[int] = None
    duration_high: Optional[int] = None
    parity: Optional[str] = None
    sequence_from: Optional[int] = None
    sequence_to: Optional[int] = None
    source: str = "manual"
    override_reason: Optional[str] = None
    priority_score: Optional[float] = None
    status: Optional[str] = None


class MovePayload(BaseModel):
    planned_date: str
    reason: Optional[str] = None


class SplitPayload(BaseModel):
    parts: int = 2
    reason: Optional[str] = None


class MergePayload(BaseModel):
    task_ids: list[int]
    title: Optional[str] = None


class CompletePayload(BaseModel):
    actual_minutes: Optional[int] = None
    perceived_difficulty: Optional[int] = None
    blocker: Optional[str] = None
    note: Optional[str] = None
    started_at: Optional[str] = None


class ActivityPayload(BaseModel):
    title: str
    category: str = "other"
    scheduling_type: str = "fixed"
    date: Optional[str] = None
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    recurring: bool = False
    is_exceptional: bool = False
    note: Optional[str] = None


class ClassPayload(BaseModel):
    title: str
    subject_id: Optional[int] = None
    kind: str = "external_class"
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    recurring: bool = True
    notes: Optional[str] = None


class SchoolOverridePayload(BaseModel):
    date: str
    is_school_day: bool
    reason: Optional[str] = None


class PlanningSessionPayload(BaseModel):
    week_start: Optional[str] = None
    force_new: bool = False


class AnswerPayload(BaseModel):
    code: str
    answer: dict = {}
    skipped: bool = False


class PriorityFeedbackPayload(BaseModel):
    items: list[dict] = []


class RebuildPayload(BaseModel):
    confirm: bool = False


# ---------------------------------------------------------------------------
# Tasks — the user always owns the plan
# ---------------------------------------------------------------------------


@router.get("/tasks")
def list_tasks(
    date: Optional[str] = Query(None),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    day = parse_day(date) or today_local()
    if from_date or to_date:
        start = parse_day(from_date) or week_start(day)
        end = parse_day(to_date) or week_end(day)
        tasks = list(
            db.query(models.StudyTask)
            .filter(
                models.StudyTask.user_id == user.id,
                models.StudyTask.planned_date >= start,
                models.StudyTask.planned_date <= end,
            )
            .order_by(models.StudyTask.planned_date, models.StudyTask.display_order)
        )
        titles = {
            topic.id: topic.title
            for topic in db.query(models.Topic).filter(models.Topic.id.in_([t.topic_id for t in tasks if t.topic_id] or [0]))
        }
        return {"tasks": [tasks_service.task_payload(task, topic_title=titles.get(task.topic_id)) for task in tasks]}
    return tasks_service.day_tasks(db, user, day)


@router.get("/tasks/types")
def task_types_registry() -> dict:
    """V3.1 doc 06 — the type list is data, so the UI (and additions) never hard-code it."""
    from ...domain import task_types as registry

    return registry.payload()


@router.post("/tasks")
def create_task(payload: TaskPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    task = tasks_service.create_task(db, user, payload.model_dump(), planner_version="manual" if payload.source == "manual" else None)
    db.commit()
    return tasks_service.task_payload(task)


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int, changes: dict = Body(...), user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    task = tasks_service.update_task(db, user, task_id, changes)
    db.commit()
    return tasks_service.task_payload(task)


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int, reason: Optional[str] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = tasks_service.delete_task(db, user, task_id, reason=reason)
    db.commit()
    return result


@router.post("/tasks/{task_id}/move")
def move_task(
    task_id: int, payload: MovePayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = tasks_service.move_task(db, user, task_id, common.parse_date_if_string(payload.planned_date), reason=payload.reason)
    db.commit()
    return result


@router.post("/tasks/{task_id}/split")
def split_task(
    task_id: int, payload: SplitPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = tasks_service.split_task(db, user, task_id, parts=payload.parts, reason=payload.reason)
    db.commit()
    return result


@router.post("/tasks/merge")
def merge_tasks(payload: MergePayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = tasks_service.merge_tasks(db, user, payload.task_ids, title=payload.title)
    db.commit()
    return result


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: int, payload: CompletePayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    started = common.parse_datetime_if_string(payload.started_at) if payload.started_at else None
    result = tasks_service.complete_task(
        db,
        user,
        task_id,
        actual_minutes=payload.actual_minutes,
        perceived_difficulty=payload.perceived_difficulty,
        blocker=payload.blocker,
        note=payload.note,
        started_at=started,
    )
    db.commit()
    return result


@router.post("/tasks/{task_id}/uncomplete")
def uncomplete_task(task_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = tasks_service.uncomplete_task(db, user, task_id)
    db.commit()
    return result


@router.post("/tasks/{task_id}/skip")
def skip_task(
    task_id: int, reason: Optional[str] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = tasks_service.mark_skipped(db, user, task_id, reason)
    db.commit()
    return result


@router.post("/tasks/recovery")
def recovery(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = tasks_service.recovery_plan(db, user)
    db.commit()
    return result


# ---------------------------------------------------------------------------
# Capacity & activities
# ---------------------------------------------------------------------------


@router.get("/capacity/today")
def capacity_today(date: Optional[str] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return capacity_service.day_capacity(db, user, parse_day(date) or today_local())


@router.get("/capacity/week")
def capacity_week(week: Optional[str] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    reference = parse_day(week) or today_local()
    return capacity_service.week_capacity(db, user, week_start(reference))


@router.get("/capacity/overload")
def overload(date: Optional[str] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return capacity_service.overload_check(db, user, parse_day(date) or today_local())


@router.get("/capacity/habit-advice")
def habit_advice(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return capacity_service.habitual_advice(db, user)


@router.post("/school-day-overrides")
def school_override(
    payload: SchoolOverridePayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = capacity_service.set_school_override(
        db, user, common.parse_date_if_string(payload.date), payload.is_school_day, payload.reason
    )
    db.commit()
    return result


@router.get("/activities")
def list_activities(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = list(
        db.query(models.Activity).filter(models.Activity.user_id == user.id, models.Activity.active.is_(True)).order_by(models.Activity.id)
    )
    return {
        "activities": [
            {
                "id": row.id,
                "title": row.title,
                "category": row.category,
                "category_label": activity_registry.category_label(row.category),
                "scheduling_type": row.scheduling_type,
                "date": common.jdate(row.date),
                "day_of_week": row.day_of_week,
                "day_label": (
                    common.weekday_fa(_weekday_date(row.day_of_week)) if row.day_of_week is not None else None
                ),
                "start_time": row.start_time.strftime("%H:%M") if row.start_time else None,
                "end_time": row.end_time.strftime("%H:%M") if row.end_time else None,
                "duration_minutes": row.duration_minutes,
                "recurring": row.recurring,
                "note": row.note,
            }
            for row in rows
        ],
        "policy": activity_registry.payload()["policy"],
        "categories": activity_registry.list_categories(),
        "scheduling_types": activity_registry.payload()["scheduling_types"],
    }


def _weekday_date(index: int):
    """Translate the Persian weekday index (0=شنبه) into a real date for a label."""
    from ...core.jalali import SATURDAY
    import datetime as _dt

    today = today_local()
    offset = (index - ((today.weekday() - SATURDAY) % 7)) % 7
    return today + _dt.timedelta(days=offset)


@router.post("/activities")
def create_activity(
    payload: ActivityPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    from ...core.errors import ValidationError

    def _time(value):
        if not value:
            return None
        import datetime as _dt

        return _dt.time.fromisoformat(value)

    if not activity_registry.is_valid_scheduling(payload.scheduling_type):
        raise ValidationError(
            "نوع زمان‌بندی نامعتبر است.",
            details={"reason": "unknown_scheduling_type", "choices": sorted(activity_registry.SCHEDULING_TYPES)},
        )
    if not activity_registry.is_valid_category(payload.category):
        raise ValidationError(
            "دستهٔ فعالیت شناخته نشد.",
            details={"reason": "unknown_category", "choices": sorted(activity_registry.categories())},
        )
    if payload.recurring and payload.day_of_week is None:
        raise ValidationError("برای فعالیت تکرارشونده، روز هفته لازم است.")
    activity = models.Activity(
        user_id=user.id,
        title=payload.title,
        category=payload.category,
        scheduling_type=payload.scheduling_type,
        date=common.parse_date_if_string(payload.date),
        day_of_week=payload.day_of_week,
        start_time=_time(payload.start_time),
        end_time=_time(payload.end_time),
        duration_minutes=payload.duration_minutes,
        recurring=payload.recurring,
        is_exceptional=payload.is_exceptional,
        note=payload.note,
    )
    db.add(activity)
    db.flush()
    common.audit(db, "activity_created", user_id=user.id, entity_type="activity", entity_id=activity.id, after={"title": activity.title})
    db.commit()
    return {
        "id": activity.id,
        "title": activity.title,
        "category": activity.category,
        "category_label": activity_registry.category_label(activity.category),
        "scheduling_type": activity.scheduling_type,
        "scheduling_label": activity_registry.SCHEDULING_TYPES[activity.scheduling_type]["label"],
        "policy": activity_registry.payload()["policy"],
    }


@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    activity = db.get(models.Activity, activity_id)
    if not activity or activity.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("فعالیت پیدا نشد.")
    activity.active = False
    db.commit()
    return {"id": activity_id, "active": False}


@router.get("/activities/types")
def activity_types() -> dict:
    """Categories and scheduling types are data, not a hard-coded list in the engine."""
    return activity_registry.payload()


@router.get("/classes")
def list_classes(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    rows = list(db.query(models.ClassSchedule).filter(models.ClassSchedule.user_id == user.id).order_by(models.ClassSchedule.id))
    subjects = {subject.id: subject.name for subject in db.query(models.Subject)}
    return {
        "classes": [
            {
                "id": row.id,
                "title": row.title,
                "subject_id": row.subject_id,
                "subject": subjects.get(row.subject_id),
                "kind": row.kind,
                "day_of_week": row.day_of_week,
                "day_label": common.weekday_fa(_weekday_date(row.day_of_week)) if row.day_of_week is not None else None,
                "start_time": row.start_time.strftime("%H:%M") if row.start_time else None,
                "end_time": row.end_time.strftime("%H:%M") if row.end_time else None,
                "recurring": row.recurring,
                "source": row.source,
                "active": row.active,
                "notes": row.notes,
            }
            for row in rows
        ],
        "note": "سه کلاس تقویتی پیش‌فرض (حسابان/شیمی/فیزیک) ساخته شده‌اند؛ روز و ساعت را خودت تعیین کن.",
    }


@router.post("/classes")
def create_class(payload: ClassPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    import datetime as _dt

    klass = models.ClassSchedule(
        user_id=user.id,
        title=payload.title,
        subject_id=payload.subject_id,
        kind=payload.kind,
        day_of_week=payload.day_of_week,
        start_time=_dt.time.fromisoformat(payload.start_time) if payload.start_time else None,
        end_time=_dt.time.fromisoformat(payload.end_time) if payload.end_time else None,
        recurring=payload.recurring,
        notes=payload.notes,
        source="manual",
    )
    db.add(klass)
    db.commit()
    return {"id": klass.id, "title": klass.title}


@router.patch("/classes/{class_id}")
def update_class(
    class_id: int, changes: dict = Body(...), user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    import datetime as _dt

    klass = db.get(models.ClassSchedule, class_id)
    if not klass or klass.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("کلاس پیدا نشد.")
    for key in ["title", "day_of_week", "kind", "notes", "active", "recurring", "subject_id"]:
        if key in changes:
            setattr(klass, key, changes[key])
    for key in ["start_time", "end_time"]:
        if key in changes:
            setattr(klass, key, _dt.time.fromisoformat(changes[key]) if changes[key] else None)
    db.commit()
    return {"id": klass.id, "updated": True}


# ---------------------------------------------------------------------------
# Weekly planner
# ---------------------------------------------------------------------------


@router.post("/planning/sessions")
def create_planning_session(
    payload: PlanningSessionPayload | None = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = planner.create_session(db, user, (payload or PlanningSessionPayload()).model_dump())
    db.commit()
    return planner.session_payload(db, user, session)


@router.get("/planning/current")
def current_planning_session(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    session = planner.current_session(db, user)
    db.commit()
    return planner.session_payload(db, user, session)


@router.get("/planning/sessions/{session_id}")
def get_planning_session(session_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    session = db.get(models.PlanningSession, session_id)
    if not session or session.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("جلسه برنامه‌ریزی پیدا نشد.")
    return planner.session_payload(db, user, session)


@router.get("/planning/sessions/{session_id}/suggestions")
def priority_suggestions(session_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    session = db.get(models.PlanningSession, session_id)
    if not session or session.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("جلسه برنامه‌ریزی پیدا نشد.")
    context = planner.refresh_context(db, user, session)
    db.commit()
    return {
        "session_id": session_id,
        "week_label": week_label_fa(session.week_start),
        "suggestions": (session.priority_suggestions or {}).get("items", []),
        "question": (session.priority_suggestions or {}).get("question"),
        "exams": [
            {"id": exam.id, "title": exam.title, "date": common.jdate(exam.exam_date), "type": exam.exam_type}
            for exam in context["exams"]
        ],
        "review": context["review"],
        "note": "پیش از تولید برنامه، این فهرست را تأیید/کم/زیاد/رد کن؛ همه به‌عنوان داده ذخیره می‌شود.",
    }


@router.post("/planning/sessions/{session_id}/priorities")
def submit_priorities(
    session_id: int,
    payload: PriorityFeedbackPayload,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(models.PlanningSession, session_id)
    if not session or session.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("جلسه برنامه‌ریزی پیدا نشد.")
    result = planner.record_priority_feedback(db, user, session, payload.items)
    db.commit()
    return {**result, "session": planner.session_payload(db, user, session)}


@router.get("/planning/sessions/{session_id}/questions")
def planning_questions(session_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    session = db.get(models.PlanningSession, session_id)
    if not session or session.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("جلسه برنامه‌ریزی پیدا نشد.")
    questions = planner.adaptive_questions(db, user, session)
    db.commit()
    return {
        "session_id": session_id,
        "questions": [
            {
                "id": question.id,
                "code": question.code,
                "text": question.text,
                "kind": question.kind,
                "options": question.options or [],
                "because": question.because,
                "information_value": question.information_value,
            }
            for question in questions
        ],
        "policy": "فقط سؤال‌هایی پرسیده می‌شود که پاسخشان می‌تواند تصمیم این هفته را تغییر دهد.",
    }


@router.post("/planning/sessions/{session_id}/answers")
def submit_answer(
    session_id: int, payload: AnswerPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    session = db.get(models.PlanningSession, session_id)
    if not session or session.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("جلسه برنامه‌ریزی پیدا نشد.")
    result = planner.answer_question(db, user, session, payload.code, payload.answer, skipped=payload.skipped)
    db.commit()
    return {**result, "session": planner.session_payload(db, user, session)}


@router.post("/planning/sessions/{session_id}/generate")
def generate(session_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    session = db.get(models.PlanningSession, session_id)
    if not session or session.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("جلسه برنامه‌ریزی پیدا نشد.")
    result = planner.generate_plan(db, user, session)
    db.commit()
    return result


@router.post("/planning/sessions/{session_id}/rebuild")
def rebuild(
    session_id: int, payload: RebuildPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    session = db.get(models.PlanningSession, session_id)
    if not session or session.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("جلسه برنامه‌ریزی پیدا نشد.")
    result = planner.rebuild(db, user, session, confirm=payload.confirm)
    db.commit()
    return result


@router.post("/planning/sessions/{session_id}/finalize")
def finalize(session_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    session = db.get(models.PlanningSession, session_id)
    if not session or session.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("جلسه برنامه‌ریزی پیدا نشد.")
    result = planner.finalize(db, user, session)
    db.commit()
    return result


@router.get("/planning/week")
def week_view(week: Optional[str] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    reference = parse_day(week) or today_local()
    start = week_start(reference)
    payload = tasks_service.week_tasks(db, user, start)
    payload["week_label"] = week_label_fa(start)
    payload["capacity"] = capacity_service.week_capacity(db, user, start)
    payload["midweek"] = planner.midweek_check(db, user, reference=reference)
    # V3.1 doc 08: the planner is a *calendar* — Jalali dates, holidays and exams,
    # read from the calendar engine instead of being recomputed in the UI.
    from ...services import calendar_service

    calendar_week = calendar_service.week_view(db, user, start)
    by_date = {row["date"]: row for row in calendar_week["days"]}
    for day in payload.get("days", []):
        info = by_date.get(day["date"]) or {}
        day["calendar"] = {
            "jalali": info.get("jalali"),
            "month_title": info.get("month_title"),
            "is_holiday": info.get("is_holiday"),
            "holiday_titles": info.get("holiday_titles", []),
            "events": info.get("events", []),
            "planned_minutes": info.get("planned_minutes"),
        }
    payload["calendar"] = {
        "from": calendar_week["from"],
        "to": calendar_week["to"],
        "from_long": calendar_week["from_long"],
        "to_long": calendar_week["to_long"],
        "days": [
            {
                "date": row["date"],
                "weekday": row["weekday"],
                "jalali": row["jalali"],
                "is_holiday": row["is_holiday"],
                "holiday_titles": row["holiday_titles"],
                "event_count": len(row["events"]),
                "planned_minutes": row["planned_minutes"],
            }
            for row in calendar_week["days"]
        ],
        "note": "هفته از شنبه تا جمعه؛ تعطیلات و رویدادها از موتور تقویم می‌آیند.",
    }
    db.commit()
    return payload


@router.get("/planning/day")
def day_view(date: Optional[str] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return tasks_service.day_tasks(db, user, parse_day(date) or today_local())
