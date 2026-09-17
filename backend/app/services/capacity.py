"""Capacity engine.

V3: "Capacity is realistic completion capability, not theoretical free hours."

So we compute two different numbers and never mix them up:

* ``theoretical_minutes`` - clock arithmetic (school end, classes, activities,
  sleep, personal fixed time). It is an upper bound, nothing more.
* ``realistic_minutes`` - what the user actually completes, learned from history
  (completed tasks, actual durations, day type), conservative during the first
  month, adapted gradually afterwards.

Anti over-planning: the planner gets a warning plus a *suggestion list*, never an
automatic deletion of the user's tasks.
"""

from __future__ import annotations

import datetime as _dt
import statistics
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import is_school_day_default, now_utc, safe_div, season_mode, today_local
from ..db import models
from ..domain.enums import TaskStatus
from . import common


def _minutes(value: _dt.time) -> int:
    return value.hour * 60 + value.minute


def parse_clock(text: Optional[str], default: str) -> _dt.time:
    raw = (text or default).strip()
    if ":" not in raw:
        return _dt.time.fromisoformat(default)
    hour, minute = raw.split(":", 1)
    return _dt.time(int(hour), int(minute))


def school_day_status(db: Session, user: models.User, day: _dt.date) -> dict:
    override = db.scalars(
        select(models.SchoolDayOverride).where(
            models.SchoolDayOverride.user_id == user.id, models.SchoolDayOverride.date == day
        )
    ).first()
    if override:
        multiplier = override.capacity_multiplier
        if multiplier is None:
            multiplier = config.value("capacity.no_school_multiplier") if not override.is_school_day else 1.0
        return {
            "is_school_day": override.is_school_day,
            "source": "override",
            "reason": override.reason,
            "multiplier": multiplier,
        }
    default = is_school_day_default(day)
    if season_mode(day) == "summer":
        default = False
    return {
        "is_school_day": default,
        "source": "default",
        "reason": None,
        "multiplier": 1.0 if default else config.value("capacity.no_school_multiplier"),
    }


def activities_for_day(db: Session, user: models.User, day: _dt.date) -> list[models.Activity]:
    weekday = (day.weekday() + 2) % 7  # 0 = شنبه
    rows = list(
        db.scalars(
            select(models.Activity).where(models.Activity.user_id == user.id, models.Activity.active.is_(True))
        )
    )
    result = []
    for activity in rows:
        if activity.recurring and activity.day_of_week == weekday:
            result.append(activity)
        elif activity.date == day:
            result.append(activity)
    return result


def classes_for_day(db: Session, user: models.User, day: _dt.date) -> list[models.ClassSchedule]:
    weekday = (day.weekday() + 2) % 7
    return list(
        db.scalars(
            select(models.ClassSchedule).where(
                models.ClassSchedule.user_id == user.id,
                models.ClassSchedule.active.is_(True),
                models.ClassSchedule.day_of_week == weekday,
            )
        )
    )


def _blocked_minutes(db: Session, user: models.User, day: _dt.date) -> tuple[int, list[dict]]:
    blocks: list[dict] = []
    total = 0
    for activity in activities_for_day(db, user, day):
        if activity.start_time and activity.end_time:
            minutes = max(0, _minutes(activity.end_time) - _minutes(activity.start_time))
        else:
            minutes = activity.duration_minutes or 0
        if minutes:
            blocks.append({"kind": "activity", "title": activity.title, "minutes": minutes, "category": activity.category})
            total += minutes
    for klass in classes_for_day(db, user, day):
        if klass.start_time and klass.end_time:
            minutes = max(0, _minutes(klass.end_time) - _minutes(klass.start_time))
            blocks.append({"kind": "class", "title": klass.title, "minutes": minutes, "subject_id": klass.subject_id})
            total += minutes
    return total, blocks


def theoretical_minutes(db: Session, user: models.User, day: _dt.date) -> dict:
    sleep_time = parse_clock(user.timezone and None, config.value("capacity.default_sleep_time"))
    personal_fixed = config.value("capacity.default_personal_fixed_minutes")
    school_status = school_day_status(db, user, day)
    school_end = parse_clock(None, config.value("capacity.default_school_end_time"))
    start_minutes = _minutes(school_end) if school_status["is_school_day"] else 8 * 60
    available = max(0, _minutes(sleep_time) - start_minutes - personal_fixed)
    blocked, blocks = _blocked_minutes(db, user, day)
    available = max(0, available - blocked)
    multiplier = school_status.get("multiplier") or 1.0
    if not school_status["is_school_day"] and not blocks:
        available = int(round(available * multiplier))
    if not school_status["is_school_day"]:
        available = max(available, config.value("capacity.no_school_min_minutes"))
    ceiling = config.value("capacity.max_daily_minutes")
    return {
        "minutes": min(available, ceiling),
        "raw_minutes": available,
        "school": school_status,
        "blocked_minutes": blocked,
        "blocks": blocks,
        "sleep_time": config.value("capacity.default_sleep_time"),
        "personal_fixed_minutes": personal_fixed,
        "school_end_time": str(school_end)[:5],
        "ceiling_applied": available > ceiling,
    }


# ---------------------------------------------------------------------------
# Realistic capacity (learned from behaviour)
# ---------------------------------------------------------------------------


def active_days_count(db: Session, user: models.User) -> int:
    return (
        db.scalar(
            select(func.count(func.distinct(models.TaskExecution.created_at)))
            .where(models.TaskExecution.user_id == user.id)
        )
        or 0
    ) or (
        db.scalar(
            select(func.count(func.distinct(models.StudyTask.planned_date))).where(
                models.StudyTask.user_id == user.id, models.StudyTask.status == TaskStatus.COMPLETED.value
            )
        )
        or 0
    )


def completion_history(db: Session, user: models.User, days: int) -> list[dict]:
    window = config.value("capacity.history_window_days") if not days else days
    since = today_local() - _dt.timedelta(days=window)
    rows = list(
        db.scalars(
            select(models.StudyTask).where(
                models.StudyTask.user_id == user.id,
                models.StudyTask.planned_date.is_not(None),
                models.StudyTask.planned_date >= since,
            )
        )
    )
    by_day: dict[_dt.date, dict] = {}
    for task in rows:
        bucket = by_day.setdefault(
            task.planned_date, {"planned_count": 0, "completed_count": 0, "planned_minutes": 0, "actual_minutes": 0}
        )
        bucket["planned_count"] += 1
        minutes = task.planned_minutes or ((task.duration_low or 0) + (task.duration_high or 0)) // 2 or 0
        bucket["planned_minutes"] += minutes
        if task.status == TaskStatus.COMPLETED.value:
            bucket["completed_count"] += 1
            bucket["actual_minutes"] += minutes
    history = []
    for day, bucket in sorted(by_day.items()):
        history.append({"date": common.jdate(day), "_date": day, **bucket})
    return history


def realistic_capacity(db: Session, user: models.User, day: _dt.date) -> dict:
    history = completion_history(db, user, config.value("capacity.history_window_days"))
    school_status = school_day_status(db, user, day)
    active_days = len({
        row[0] for row in db.execute(
            select(models.StudyTask.planned_date).where(
                models.StudyTask.user_id == user.id, models.StudyTask.status == TaskStatus.COMPLETED.value
            )
        ).all() if row[0]
    })
    min_days = config.value("capacity.min_days_before_habitual_estimate")
    ceiling = config.value("capacity.max_daily_minutes")

    if active_days < min_days or not history:
        # Conservative phase: promise only a fraction of the clock time.
        upper = theoretical_minutes(db, user, day)["minutes"]
        conservative = int(round(upper * 0.55))
        return {
            "minutes": max(30, min(conservative, ceiling)),
            "confidence": round(common.confidence_from_evidence(active_days) * 0.6, 3),
            "method": "conservative_first_month",
            "evidence_days": active_days,
            "why": f"کمتر از {min_days} روز داده داریم؛ ظرفیت واقع‌بینانه محافظه‌کارانه تخمین زده می‌شود.",
        }

    same_type = [row for row in history if (row["_date"].weekday() not in (3, 4)) == school_status["is_school_day"]]
    sample = same_type or history
    completed_minutes = [row["actual_minutes"] for row in sample if row["completed_count"] > 0]
    if not completed_minutes:
        completed_minutes = [row["actual_minutes"] for row in history]
    median_minutes = statistics.median(completed_minutes) if completed_minutes else 0
    recent = completed_minutes[-5:] if len(completed_minutes) >= 5 else completed_minutes
    recent_mean = statistics.fmean(recent) if recent else median_minutes
    step = config.value("capacity.gradual_change_step")
    blended = median_minutes * (1 - step) + recent_mean * step
    minutes = max(30, min(int(round(blended)), ceiling))
    confidence = common.confidence_from_evidence(len(completed_minutes))
    return {
        "minutes": minutes,
        "confidence": round(confidence, 3),
        "method": "historical_completion",
        "evidence_days": len(sample),
        "median_completed_minutes": median_minutes,
        "recent_mean_minutes": round(recent_mean, 1),
        "why": (
            f"بر پایه {len(sample)} روز گذشته: میانه کار انجام‌شده {int(median_minutes)} دقیقه بوده و "
            f"روند چند روز اخیر {int(recent_mean)} دقیقه است."
        ),
    }


def day_capacity(db: Session, user: models.User, day: Optional[_dt.date] = None) -> dict:
    day = day or today_local()
    theoretical = theoretical_minutes(db, user, day)
    realistic = realistic_capacity(db, user, day)
    tasks = list(
        db.scalars(
            select(models.StudyTask).where(
                models.StudyTask.user_id == user.id,
                models.StudyTask.planned_date == day,
                models.StudyTask.status.not_in([TaskStatus.CANCELLED.value]),
            )
        )
    )
    planned_minutes = 0
    for task in tasks:
        planned_minutes += task.planned_minutes or ((task.duration_low or 0) + (task.duration_high or 0)) // 2 or 0
    completed_minutes = 0
    for task in tasks:
        if task.status == TaskStatus.COMPLETED.value:
            completed_minutes += task.planned_minutes or ((task.duration_low or 0) + (task.duration_high or 0)) // 2 or 0
    ratio = safe_div(planned_minutes, realistic["minutes"]) if realistic["minutes"] else None
    return {
        "date": common.jdate(day),
        "date_long": common.jdate_long(day),
        "weekday": common.weekday_fa(day),
        "is_school_day": theoretical["school"]["is_school_day"],
        "school_source": theoretical["school"]["source"],
        "theoretical_minutes": theoretical["minutes"],
        "realistic_minutes": realistic["minutes"],
        "planned_minutes": planned_minutes,
        "completed_minutes": completed_minutes,
        "planned_task_count": len([t for t in tasks if t.status != TaskStatus.CANCELLED.value]),
        "completed_task_count": len([t for t in tasks if t.status == TaskStatus.COMPLETED.value]),
        "overload_ratio": round(ratio, 3) if ratio is not None else None,
        "overloaded": bool(ratio is not None and ratio > config.value("capacity.overload_tolerance")),
        "confidence": realistic["confidence"],
        "method": realistic["method"],
        "factors": {
            "blocks": theoretical["blocks"],
            "blocked_minutes": theoretical["blocked_minutes"],
            "school": theoretical["school"],
            "ceiling_applied": theoretical["ceiling_applied"],
            "note": "ظرفیت واقعی ≠ وقت آزاد. ساعتی که آزاد است لزوماً قابل استفاده نیست.",
        },
        "explanation": realistic["why"],
        "overload_policy": "هیچ کاری خودکار حذف نمی‌شود؛ فقط هشدار و پیشنهاد جابه‌جایی داده می‌شود.",
    }


def week_capacity(db: Session, user: models.User, week_start: _dt.date) -> dict:
    days = []
    for offset in range(7):
        day = week_start + _dt.timedelta(days=offset)
        days.append(day_capacity(db, user, day))
    return {
        "week_start": common.jdate(week_start),
        "week_end": common.jdate(week_start + _dt.timedelta(days=6)),
        "theoretical_minutes": sum(d["theoretical_minutes"] for d in days),
        "realistic_minutes": sum(d["realistic_minutes"] for d in days),
        "planned_minutes": sum(d["planned_minutes"] for d in days),
        "days": days,
        "overloaded_days": [d["date"] for d in days if d["overloaded"]],
    }


def refresh_snapshot(db: Session, user: models.User, day: Optional[_dt.date] = None, source: str = "estimate") -> models.CapacitySnapshot:
    day = day or today_local()
    payload = day_capacity(db, user, day)
    row = db.scalars(
        select(models.CapacitySnapshot).where(
            models.CapacitySnapshot.user_id == user.id,
            models.CapacitySnapshot.date == day,
            models.CapacitySnapshot.source == source,
        )
    ).first()
    if row is None:
        row = models.CapacitySnapshot(user_id=user.id, date=day, source=source)
        db.add(row)
    row.theoretical_minutes = payload["theoretical_minutes"]
    row.realistic_minutes = payload["realistic_minutes"]
    row.planned_minutes = payload["planned_minutes"]
    row.completed_minutes = payload["completed_minutes"]
    row.planned_task_count = payload["planned_task_count"]
    row.completed_task_count = payload["completed_task_count"]
    row.confidence = payload["confidence"]
    row.factors = payload["factors"]
    row.evidence = {"method": payload["method"], "explanation": payload["explanation"]}
    row.model_version = config.MODEL_VERSION
    db.flush()
    return row


def overload_check(db: Session, user: models.User, day: _dt.date) -> dict:
    payload = day_capacity(db, user, day)
    if not payload["overloaded"]:
        return {**payload, "suggestions": [], "message": "بار برنامه با ظرفیت واقع‌بینانه هم‌خوان است."}
    tasks = list(
        db.scalars(
            select(models.StudyTask)
            .where(
                models.StudyTask.user_id == user.id,
                models.StudyTask.planned_date == day,
                models.StudyTask.status.in_([TaskStatus.PLANNED.value, TaskStatus.IN_PROGRESS.value, TaskStatus.DEFERRED.value]),
            )
            .order_by(models.StudyTask.priority_score)
        )
    )
    excess = payload["planned_minutes"] - payload["realistic_minutes"]
    suggestions = []
    freed = 0
    for task in tasks:
        minutes = task.planned_minutes or ((task.duration_low or 0) + task.duration_high or 0) // 2 or 0
        suggestions.append(
            {
                "task_id": task.id,
                "title": task.title,
                "minutes": minutes,
                "priority_score": task.priority_score,
                "why": "کم‌اولویت‌ترین کار روز است؛ جابه‌جایی آن کمترین آسیب را دارد.",
            }
        )
        freed += minutes
        if freed >= excess:
            break
    return {
        **payload,
        "excess_minutes": excess,
        "suggestions": suggestions,
        "message": (
            f"جمع کارهای امروز حدود {excess} دقیقه بیشتر از ظرفیت واقع‌بینانه است. "
            "هیچ کاری خودکار حذف نشد؛ این‌ها گزینه‌های جابه‌جایی هستند."
        ),
    }


def set_school_override(
    db: Session, user: models.User, day: _dt.date, is_school_day: bool, reason: Optional[str] = None
) -> dict:
    row = db.scalars(
        select(models.SchoolDayOverride).where(
            models.SchoolDayOverride.user_id == user.id, models.SchoolDayOverride.date == day
        )
    ).first()
    multiplier = 1.0 if is_school_day else config.value("capacity.no_school_multiplier")
    if row is None:
        row = models.SchoolDayOverride(
            user_id=user.id, date=day, is_school_day=is_school_day, reason=reason, capacity_multiplier=multiplier
        )
        db.add(row)
    else:
        row.is_school_day = is_school_day
        row.reason = reason
        row.capacity_multiplier = multiplier
    db.flush()
    refresh_snapshot(db, user, day, source="school_override")
    return {
        "date": common.jdate(day),
        "is_school_day": is_school_day,
        "multiplier": multiplier,
        "capacity": day_capacity(db, user, day),
    }


def habitual_advice(db: Session, user: models.User) -> dict:
    """The V2 'after 30 days' advice: comment on task *count*, never on a rigid clock."""
    min_days = config.value("behavior.min_days_for_capacity_advice")
    history = completion_history(db, user, 45)
    active_days = len([row for row in history if row["completed_count"] > 0])
    if active_days < min_days:
        return {
            "available": False,
            "active_days": active_days,
            "needed_days": min_days,
            "message": f"بعد از {min_days} روز فعالیت، این تحلیل فعال می‌شود ({active_days} روز ثبت شده).",
        }
    school_days = [row["completed_count"] for row in history if row["_date"].weekday() not in (3, 4)]
    free_days = [row["completed_count"] for row in history if row["_date"].weekday() in (3, 4)]
    school_avg = statistics.fmean(school_days) if school_days else 0
    free_avg = statistics.fmean(free_days) if free_days else 0
    today = today_local()
    today_school = school_day_status(db, user, today)["is_school_day"]
    typical = school_avg if today_school else free_avg
    planned_today = db.scalar(
        select(func.count(models.StudyTask.id)).where(
            models.StudyTask.user_id == user.id,
            models.StudyTask.planned_date == today,
            models.StudyTask.status != TaskStatus.CANCELLED.value,
        )
    ) or 0
    comment = None
    if typical >= 1:
        if planned_today > typical + 1:
            comment = f"عادت تو در {'روز کلاس' if today_school else 'روز آزاد'} حدود {typical:.0f} کار است؛ {planned_today} کار امروز پرریسک است."
        elif planned_today < typical - 1:
            comment = f"روزهای مشابه معمولاً {typical:.0f} کار انجام می‌دهی؛ {planned_today} کار سبک است."
        else:
            comment = f"تعداد کار امروز با عادت واقعی‌ات ({typical:.0f} کار) هم‌خوان است."
    return {
        "available": True,
        "active_days": active_days,
        "school_day_average_tasks": round(school_avg, 2),
        "free_day_average_tasks": round(free_avg, 2),
        "planned_today": planned_today,
        "comment": comment,
        "policy": "برنامه ساعت اجباری تحمیل نمی‌کند؛ فقط تعداد کار/وعده را با عادت واقعی مقایسه می‌کند.",
    }
