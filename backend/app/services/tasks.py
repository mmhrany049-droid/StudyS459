"""Study tasks: creation, manual control, execution, recovery.

Non-negotiable rules implemented here:

* "the user owns the plan": create / edit / delete / move / split / merge /
  change quantity / change priority / set time / complete — all available;
* every manual change is stored with ``source=manual``, ``manual_override`` and
  ``override_reason`` and the planner must never silently undo it;
* activities are constraints, not failed study tasks — so a day with activities
  simply has less capacity;
* recovery redistributes missed work, protects critical work and never dumps
  everything onto tomorrow.
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.errors import NotFoundError, ValidationError
from ..core.timeutil import clamp, now_utc, today_local
from ..db import models
from ..domain import task_types
from ..domain.enums import TaskSource, TaskStatus, TaskType
from . import common

MODEL_VERSION = config.MODEL_VERSION


def task_payload(task: models.StudyTask, *, topic_title: Optional[str] = None) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "task_type": task.task_type,
        "type_label": task_types.label_of(task.task_type),
        "type_family": task_types.family_of(task.task_type),
        "intervention_type": task.intervention_type,
        "book_id": task.book_id,
        "topic_id": task.topic_id,
        "topic_title": topic_title,
        "goal_id": task.goal_id,
        "exam_id": task.exam_id,
        "planned_date": common.jdate(task.planned_date),
        "planned_date_long": common.jdate_long(task.planned_date),
        "planned_start_time": task.planned_start_time.strftime("%H:%M") if task.planned_start_time else None,
        "planned_question_count": task.planned_question_count,
        "planned_minutes": task.planned_minutes,
        "duration_low": task.duration_low,
        "duration_high": task.duration_high,
        "duration_label": (
            f"{task.duration_low} تا {task.duration_high} دقیقه" if task.duration_low and task.duration_high else None
        ),
        "duration_confidence": task.duration_confidence,
        "parity": task.parity,
        "sequence_from": task.sequence_from,
        "sequence_to": task.sequence_to,
        "status": task.status,
        "source": task.source,
        "manual_override": task.manual_override,
        "override_reason": task.override_reason,
        "priority_score": task.priority_score,
        "display_order": task.display_order,
        "planner_version": task.planner_version,
        "evidence": task.evidence or {},
        "recommendation_id": task.recommendation_id,
        "parent_task_id": task.parent_task_id,
        "deferred_from_date": common.jdate(task.deferred_from_date),
        "completed_at": common.jdatetime(task.completed_at),
        "created_by": task.created_by,
    }


def create_task(db: Session, user: models.User, payload: dict, *, planner_version: Optional[str] = None) -> models.StudyTask:
    planned_date = common.parse_date_if_string(payload.get("planned_date")) or today_local()
    raw_type = payload.get("task_type")
    if not task_types.is_valid(raw_type):
        raise ValidationError(
            "نوع کار مطالعه شناخته نشد.",
            details={
                "reason": "unknown_task_type",
                "choices": [item["code"] for item in task_types.payload()["types"]],
            },
        )
    payload = dict(payload)
    payload["task_type"] = raw_type
    if not payload.get("intervention_type"):
        payload["intervention_type"] = task_types.default_intervention(raw_type)
    source = payload.get("source", TaskSource.MANUAL.value)
    question_count = common.to_int(payload.get("planned_question_count"))
    planned_minutes = common.to_int(payload.get("planned_minutes"))
    duration_low = common.to_int(payload.get("duration_low"))
    duration_high = common.to_int(payload.get("duration_high"))
    duration_confidence = common.to_float(payload.get("duration_confidence"))
    if planned_minutes is None and not (duration_low and duration_high):
        from . import duration as duration_service

        estimate = duration_service.estimate_for_task(
            db,
            user,
            task_type=payload.get("task_type", TaskType.OTHER.value),
            question_count=question_count,
            topic_id=common.to_int(payload.get("topic_id")),
            book_id=common.to_int(payload.get("book_id")),
            intervention=payload.get("intervention_type"),
        )
        duration_low = estimate["low_minutes"]
        duration_high = estimate["high_minutes"]
        duration_confidence = estimate["confidence"]
        planned_minutes = estimate["point_minutes"]
    task = models.StudyTask(
        user_id=user.id,
        title=payload.get("title") or "کار مطالعه",
        task_type=payload.get("task_type", TaskType.OTHER.value),
        intervention_type=payload.get("intervention_type"),
        book_id=common.to_int(payload.get("book_id")),
        topic_id=common.to_int(payload.get("topic_id")),
        goal_id=common.to_int(payload.get("goal_id")),
        milestone_id=common.to_int(payload.get("milestone_id")),
        objective_id=common.to_int(payload.get("objective_id")),
        exam_id=common.to_int(payload.get("exam_id")),
        recommendation_id=common.to_int(payload.get("recommendation_id")),
        parent_task_id=common.to_int(payload.get("parent_task_id")),
        planned_date=planned_date,
        planned_start_time=common.parse_time_clock(payload.get("planned_start_time")),
        planned_question_count=question_count,
        planned_minutes=planned_minutes,
        duration_low=duration_low,
        duration_high=duration_high,
        duration_confidence=duration_confidence,
        parity=payload.get("parity"),
        sequence_from=common.to_int(payload.get("sequence_from")),
        sequence_to=common.to_int(payload.get("sequence_to")),
        status=payload.get("status", TaskStatus.PLANNED.value),
        source=source,
        manual_override=bool(payload.get("manual_override", source == TaskSource.MANUAL.value)),
        override_reason=payload.get("override_reason"),
        priority_score=common.to_float(payload.get("priority_score")),
        display_order=common.to_int(payload.get("display_order"), 0) or 0,
        planner_version=planner_version or MODEL_VERSION,
        evidence=payload.get("evidence") or {},
        created_by=payload.get("created_by", "user" if source == TaskSource.MANUAL.value else "planner"),
        updated_by=payload.get("updated_by", payload.get("created_by", "user" if source == "manual" else "planner")),
    )
    db.add(task)
    db.flush()
    common.audit(
        db, "task_created", user_id=user.id, entity_type="task", entity_id=task.id,
        actor=task.created_by or "user", after={"title": task.title, "source": task.source, "date": str(planned_date)},
    )
    return task


def update_task(db: Session, user: models.User, task_id: int, changes: dict, *, actor: str = "user") -> models.StudyTask:
    task = db.get(models.StudyTask, task_id)
    if not task or task.user_id != user.id:
        raise NotFoundError("کار پیدا نشد.")
    before = task_payload(task)
    editable = {
        "title": "title",
        "task_type": "task_type",
        "intervention_type": "intervention_type",
        "planned_question_count": "planned_question_count",
        "planned_minutes": "planned_minutes",
        "duration_low": "duration_low",
        "duration_high": "duration_high",
        "priority_score": "priority_score",
        "planned_start_time": "planned_start_time",
        "display_order": "display_order",
        "status": "status",
        "notes": None,
    }
    for key, attribute in editable.items():
        if key in changes and attribute:
            value = changes[key]
            if attribute in {"planned_question_count", "planned_minutes", "duration_low", "duration_high", "display_order"}:
                value = common.to_int(value)
            elif attribute == "priority_score":
                value = common.to_float(value)
            elif attribute == "planned_start_time":
                value = common.parse_time_clock(value)
                if value is None:
                    task.planned_start_time = None
                    continue
            setattr(task, attribute, value)
    if "planned_date" in changes and changes["planned_date"]:
        task.planned_date = common.parse_date_if_string(changes["planned_date"])
    if changes.get("planned_start_time") == "":
        task.planned_start_time = None
    task.manual_override = True
    task.updated_by = actor
    task.override_reason = changes.get("override_reason") or task.override_reason or "ویرایش دستی"
    db.flush()
    common.audit(
        db, "task_edited", user_id=user.id, entity_type="task", entity_id=task_id, actor=actor,
        reason=task.override_reason, before=before, after=task_payload(task),
    )
    common.observe(db, user.id, "task_edited", payload={"task_id": task_id, "changes": list(changes)}, source="user", task_id=task_id)
    return task


def delete_task(db: Session, user: models.User, task_id: int, *, reason: Optional[str] = None) -> dict:
    task = db.get(models.StudyTask, task_id)
    if not task or task.user_id != user.id:
        raise NotFoundError("کار پیدا نشد.")
    executions = db.scalar(select(func.count(models.TaskExecution.id)).where(models.TaskExecution.task_id == task_id)) or 0
    if executions:
        task.status = TaskStatus.CANCELLED.value
        task.cancelled_reason = reason or "حذف نرم (نمونه اجرا دارد)"
        db.flush()
        common.audit(db, "task_cancelled", user_id=user.id, entity_type="task", entity_id=task_id, reason=task.cancelled_reason)
        return {"task_id": task_id, "deleted": False, "cancelled": True, "had_execution": True}
    payload = task_payload(task)
    db.delete(task)
    db.flush()
    common.audit(db, "task_deleted", user_id=user.id, entity_type="task", entity_id=task_id, before=payload)
    return {"task_id": task_id, "deleted": True, "cancelled": False, "had_execution": False}


def move_task(db: Session, user: models.User, task_id: int, new_day: _dt.date, *, reason: Optional[str] = None) -> dict:
    task = db.get(models.StudyTask, task_id)
    if not task or task.user_id != user.id:
        raise NotFoundError("کار پیدا نشد.")
    before_day = task.planned_date
    task.planned_date = new_day
    task.status = TaskStatus.PLANNED.value if task.status in {TaskStatus.MISSED.value, TaskStatus.DEFERRED.value} else task.status
    task.manual_override = True
    task.updated_by = "user"
    task.deferred_from_date = before_day if before_day and before_day > new_day else task.deferred_from_date
    task.override_reason = reason or "جابه‌جایی دستی"
    db.flush()
    common.audit(
        db, "task_moved", user_id=user.id, entity_type="task", entity_id=task_id, reason=task.override_reason,
        before={"planned_date": str(before_day)}, after={"planned_date": str(new_day)},
    )
    common.observe(db, user.id, "task_moved", payload={"task_id": task_id, "to": str(new_day)}, source="user", task_id=task_id)
    return {"task_id": task_id, "planned_date": common.jdate(new_day), "manual_override": True}


def split_task(db: Session, user: models.User, task_id: int, *, parts: int = 2, reason: Optional[str] = None) -> dict:
    task = db.get(models.StudyTask, task_id)
    if not task or task.user_id != user.id:
        raise NotFoundError("کار پیدا نشد.")
    if parts < 2 or parts > 6:
        raise ValidationError("تعداد قطعات باید بین ۲ و ۶ باشد.")
    total_questions = task.planned_question_count or 0
    total_minutes = task.planned_minutes or 0
    per_questions = max(1, round(total_questions / parts)) if total_questions else None
    per_minutes = max(5, round(total_minutes / parts)) if total_minutes else None
    created = []
    for index in range(parts):
        piece = create_task(
            db,
            user,
            {
                "title": f"{task.title} (بخش {index + 1}/{parts})",
                "task_type": task.task_type,
                "intervention_type": task.intervention_type,
                "book_id": task.book_id,
                "topic_id": task.topic_id,
                "goal_id": task.goal_id,
                "exam_id": task.exam_id,
                "planned_date": (task.planned_date or today_local()) + _dt.timedelta(days=index if index else 0),
                "planned_question_count": per_questions,
                "planned_minutes": per_minutes,
                "duration_low": (task.duration_low // parts) if task.duration_low else None,
                "duration_high": (task.duration_high // parts) if task.duration_high else None,
                "source": TaskSource.MANUAL.value,
                "manual_override": True,
                "override_reason": reason or "تقسیم کار بزرگ به قطعات کوچک‌تر",
                "parent_task_id": task.id,
            },
        )
        created.append(piece.id)
    task.status = TaskStatus.CANCELLED.value
    task.cancelled_reason = "به قطعات کوچک‌تر تقسیم شد"
    db.flush()
    common.audit(
        db, "task_split", user_id=user.id, entity_type="task", entity_id=task_id,
        reason=reason or "split", after={"parts": created},
    )
    return {"task_id": task_id, "parts": created, "count": len(created)}


def merge_tasks(db: Session, user: models.User, task_ids: Iterable[int], *, title: Optional[str] = None) -> dict:
    tasks = [db.get(models.StudyTask, task_id) for task_id in task_ids]
    tasks = [task for task in tasks if task and task.user_id == user.id]
    if len(tasks) < 2:
        raise ValidationError("برای ادغام حداقل دو کار لازم است.")
    first = tasks[0]
    merged = create_task(
        db,
        user,
        {
            "title": title or " + ".join(task.title for task in tasks[:3]),
            "task_type": first.task_type,
            "intervention_type": first.intervention_type,
            "book_id": first.book_id,
            "topic_id": first.topic_id,
            "planned_date": first.planned_date,
            "planned_question_count": sum(task.planned_question_count or 0 for task in tasks) or None,
            "planned_minutes": sum(task.planned_minutes or 0 for task in tasks) or None,
            "source": TaskSource.MANUAL.value,
            "manual_override": True,
            "override_reason": "ادغام کارهای هم‌هدف",
        },
    )
    for task in tasks:
        task.status = TaskStatus.CANCELLED.value
        task.cancelled_reason = f"در کار {merged.id} ادغام شد"
    db.flush()
    common.audit(
        db, "tasks_merged", user_id=user.id, entity_type="task", entity_id=merged.id,
        after={"merged_from": [task.id for task in tasks]},
    )
    return {"merged_task_id": merged.id, "merged_from": [task.id for task in tasks]}


def complete_task(
    db: Session,
    user: models.User,
    task_id: int,
    *,
    actual_minutes: Optional[int] = None,
    perceived_difficulty: Optional[int] = None,
    blocker: Optional[str] = None,
    note: Optional[str] = None,
    started_at: Optional[_dt.datetime] = None,
) -> dict:
    """Completion always records a :class:`TaskExecution`; the actual duration is
    asked *after* completion (never predicted by the user)."""
    task = db.get(models.StudyTask, task_id)
    if not task or task.user_id != user.id:
        raise NotFoundError("کار پیدا نشد.")
    if task.status == TaskStatus.COMPLETED.value:
        return {"task_id": task_id, "status": task.status, "idempotent": True}
    task.status = TaskStatus.COMPLETED.value
    task.completed_at = now_utc()
    execution = models.TaskExecution(
        task_id=task.id,
        user_id=user.id,
        started_at=started_at,
        ended_at=now_utc(),
        actual_minutes=common.to_int(actual_minutes),
        outcome="completed",
        perceived_difficulty=common.to_int(perceived_difficulty),
        blocker=blocker,
        note=note,
        state_snapshot=_state_snapshot(db, user),
    )
    db.add(execution)
    db.flush()
    if actual_minutes:
        from . import duration as duration_service

        duration_service.record_observation(
            db,
            user,
            actual_minutes=int(actual_minutes),
            task_type=task.task_type,
            question_count=task.planned_question_count,
            topic_id=task.topic_id,
            book_id=task.book_id,
            task_id=task.id,
            difficulty=perceived_difficulty,
            predicted_low=task.duration_low,
            predicted_high=task.duration_high,
        )
    from . import goals as goal_service, rewards

    reward = rewards.award_task_completion(db, user, task)
    goal_updates = goal_service.on_task_completed(db, user, task)
    db.flush()
    common.observe(
        db, user.id, "task_completed",
        payload={"task_id": task.id, "actual_minutes": actual_minutes, "task_type": task.task_type},
        source="observed", task_id=task.id,
    )
    return {
        "task_id": task_id,
        "status": task.status,
        "actual_minutes": execution.actual_minutes,
        "rewards": reward,
        "goal_updates": goal_updates,
        "idempotent": False,
    }


def uncomplete_task(db: Session, user: models.User, task_id: int) -> dict:
    task = db.get(models.StudyTask, task_id)
    if not task or task.user_id != user.id:
        raise NotFoundError("کار پیدا نشد.")
    task.status = TaskStatus.PLANNED.value
    task.completed_at = None
    executions = list(db.scalars(select(models.TaskExecution).where(models.TaskExecution.task_id == task_id)))
    for execution in executions:
        execution.outcome = "reverted"
    db.flush()
    common.audit(db, "task_uncompleted", user_id=user.id, entity_type="task", entity_id=task_id)
    return {"task_id": task_id, "status": task.status, "reverted_executions": len(executions)}


def mark_skipped(db: Session, user: models.User, task_id: int, reason: Optional[str] = None) -> dict:
    task = db.get(models.StudyTask, task_id)
    if not task or task.user_id != user.id:
        raise NotFoundError("کار پیدا نشد.")
    task.status = TaskStatus.SKIPPED.value
    db.add(
        models.TaskExecution(
            task_id=task.id, user_id=user.id, outcome="skipped", blocker=reason,
            state_snapshot=_state_snapshot(db, user),
        )
    )
    db.flush()
    common.observe(db, user.id, "task_skipped", payload={"task_id": task.id, "reason": reason}, task_id=task.id)
    return {"task_id": task_id, "status": task.status}


def _state_snapshot(db: Session, user: models.User) -> dict:
    state = db.scalars(
        select(models.UserState).where(models.UserState.user_id == user.id).order_by(models.UserState.captured_at.desc())
    ).first()
    if not state:
        return {}
    return {
        "energy": state.energy,
        "focus": state.focus,
        "motivation": state.motivation,
        "stress": state.stress,
        "fatigue": state.fatigue,
        "captured_at": common.jdatetime(state.captured_at),
    }


def day_tasks(db: Session, user: models.User, day: Optional[_dt.date] = None) -> dict:
    day = day or today_local()
    tasks = list(
        db.scalars(
            select(models.StudyTask)
            .where(models.StudyTask.user_id == user.id, models.StudyTask.planned_date == day)
            .order_by(models.StudyTask.display_order, models.StudyTask.priority_score.desc())
        )
    )
    topic_ids = [task.topic_id for task in tasks if task.topic_id]
    titles = {
        topic.id: topic.title
        for topic in db.scalars(select(models.Topic).where(models.Topic.id.in_(topic_ids or [0])))
    }
    from . import capacity as capacity_service

    capacity_payload = capacity_service.day_capacity(db, user, day)
    return {
        "date": common.jdate(day),
        "date_long": common.jdate_long(day),
        "weekday": common.weekday_fa(day),
        "tasks": [task_payload(task, topic_title=titles.get(task.topic_id)) for task in tasks],
        "capacity": capacity_payload,
        "over_capacity": capacity_payload["overloaded"],
    }


def mark_missed_tasks(db: Session, user: models.User, *, as_of: Optional[_dt.date] = None) -> list[models.StudyTask]:
    """Past planned tasks that were never completed become MISSED (not failures)."""
    as_of = as_of or today_local()
    tasks = list(
        db.scalars(
            select(models.StudyTask).where(
                models.StudyTask.user_id == user.id,
                models.StudyTask.planned_date < as_of,
                models.StudyTask.status.in_([TaskStatus.PLANNED.value, TaskStatus.IN_PROGRESS.value]),
            )
        )
    )
    for task in tasks:
        task.status = TaskStatus.MISSED.value
    db.flush()
    return tasks


def recovery_plan(db: Session, user: models.User, *, as_of: Optional[_dt.date] = None) -> dict:
    """Redistribute missed work: protect critical work, spread the rest, never
    dump everything on tomorrow, and respect new constraints."""
    as_of = as_of or today_local()
    missed = mark_missed_tasks(db, user, as_of=as_of)
    if not missed:
        return {"missed": 0, "moves": [], "message": "کار عقب‌افتاده‌ای ثبت نشده است."}
    from . import capacity as capacity_service

    horizon_days = config.value("planning.recovery_horizon_days")
    max_shift = config.value("planning.recovery_max_shift_days")
    protected_minutes = config.value("planning.protected_task_minutes")
    capacities = {}
    for offset in range(horizon_days):
        day = as_of + _dt.timedelta(days=offset)
        payload = capacity_service.day_capacity(db, user, day)
        capacities[day] = {
            "remaining": max(0, payload["realistic_minutes"] - payload["planned_minutes"]),
            "is_school_day": payload["is_school_day"],
        }
    missed.sort(key=lambda task: (task.priority_score or 0), reverse=True)
    moves = []
    deferred = []
    for task in missed:
        minutes = task.planned_minutes or ((task.duration_low or 0) + task.duration_high or 0) // 2 or 30
        is_critical = (task.priority_score or 0) >= 0.6 or minutes >= protected_minutes
        placed = None
        for offset in range(horizon_days):
            day = as_of + _dt.timedelta(days=offset)
            capacity = capacities[day]
            if offset == 0 and not is_critical and capacity["is_school_day"]:
                continue  # do not dump everything on the very next day
            if capacity["remaining"] >= minutes * (0.6 if is_critical else 1.0):
                placed = day
                capacity["remaining"] -= minutes
                break
        if placed is None:
            if is_critical:
                # critical work is protected: place it, explicitly accepting overload
                placed = as_of if not capacities[as_of]["is_school_day"] else as_of + _dt.timedelta(days=1)
                capacities[placed]["remaining"] = max(0, capacities[placed]["remaining"] - minutes)
            else:
                deferred.append(task)
                continue
        task.planned_date = placed
        task.status = TaskStatus.PLANNED.value
        task.deferred_from_date = task.deferred_from_date or as_of - _dt.timedelta(days=1)
        task.evidence = {**(task.evidence or {}), "recovery": {"moved_from": str(as_of), "critical": is_critical}}
        moves.append(
            {
                "task_id": task.id,
                "title": task.title,
                "to": common.jdate(placed),
                "critical": is_critical,
                "minutes": minutes,
                "why": "کار حساس (نزدیک امتحان/هدف) محافظت شد." if is_critical else "به روزی با ظرفیت آزاد منتقل شد.",
            }
        )
    if deferred:
        keep_day = as_of + _dt.timedelta(days=max_shift)
        for task in deferred:
            task.status = TaskStatus.DEFERRED.value
            task.evidence = {**(task.evidence or {}), "recovery": {"deferred": True, "review_on": str(keep_day)}}
        moves.append(
            {
                "task_id": None,
                "title": f"{len(deferred)} کار کم‌اولویت",
                "to": common.jdate(keep_day),
                "critical": False,
                "why": "کارهای کم‌ارزش عقب افتاده‌اند؛ به‌جای انبوه‌کردن روز بعد، برای بازبینی کنار گذاشته شدند.",
            }
        )
    db.flush()
    common.audit(
        db, "recovery_planned", user_id=user.id, after={"moves": moves, "deferred": len(deferred)},
        reason="پخش کارهای عقب‌افتاده",
    )
    return {
        "missed": len(missed),
        "moves": moves,
        "deferred": len(deferred),
        "policy": "هیچ‌وقت همه کارهای عقب‌افتاده روی فردا ریخته نمی‌شود.",
        "message": f"{len(missed)} کار عقب‌افتاده بازتوزیع شد.",
    }


def week_tasks(db: Session, user: models.User, week_start: _dt.date) -> dict:
    days = []
    total_minutes = 0
    completed = 0
    for offset in range(7):
        day = week_start + _dt.timedelta(days=offset)
        payload = day_tasks(db, user, day)
        days.append(payload)
        total_minutes += payload["capacity"]["planned_minutes"]
        completed += payload["capacity"]["completed_task_count"]
    return {
        "week_start": common.jdate(week_start),
        "week_end": common.jdate(week_start + _dt.timedelta(days=6)),
        "days": days,
        "total_planned_minutes": total_minutes,
        "completed_tasks": completed,
    }
