"""ظرفیت روزانه — فرمول V2 + تخمین‌گر V2.1 از داده واقعی + عادت ۳۰ روزه.

فرمول پایه (14_NUMERIC):
ظرفیت_دقیقه = (ساعت_خواب - ساعت_پایان_مدرسه_یا_کلاس) × ۶۰ - زمان_ثابت_شخصی
- خواب پیش‌فرض ۲۳:۳۰، زمان ثابت ۴۵ دقیقه، پایان مدرسه فرض ۱۳:۳۰
- روز آزاد/override «مدرسه نمی‌روم»: ×۱٫۳۵ و حداقل ۱۸۰ دقیقه
- کلاس‌های آن روز ظرفیت را به اندازهٔ مدتشان کم می‌کنند.

V2.1 — Capacity Estimator:
- completed tasks/day (مدرسه vs آزاد)، میانگین جلسات، روند اخیر
- قبل از ۳۰ روز داده: محافظه‌کارانه (پیش‌فرض ۳ کار، confidence کم)
- ظرفیت عددی (تعداد کار) با حرکت تدریجی تنظیم می‌شود.
"""

from __future__ import annotations

import datetime as dt
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.config as cfg
from app.jalali import is_school_day, today_tehran, weekday_name_fa
from app.models import (CapacityEstimate, DailyTaskPlacement, Schedule, SchoolDayOverride,
                        Task, TestSession, User)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def day_classes(db: Session, user_id: int, d: date) -> list[Schedule]:
    """کلاس‌های فعال آن روز از هفته (شنبه=0 ... جمعه=6)."""
    iran_dow = (d.weekday() - 5) % 7
    return list(db.scalars(
        select(Schedule).where(
            Schedule.user_id == user_id,
            Schedule.day_of_week == iran_dow,
        )))


def day_info(db: Session, user_id: int, d: date) -> dict:
    """اطلاعات روز: مدرسه/آزاد، override، کلاس‌ها، ظرفیت دقیقه‌ای."""
    user = db.get(User, user_id)
    season_override = (user.settings_json or {}).get("season_override")
    ov = db.execute(
        select(SchoolDayOverride).where(SchoolDayOverride.user_id == user_id,
                                        SchoolDayOverride.date == d)
    ).scalar_one_or_none()
    if ov is not None:
        is_school = ov.is_school_day
        overridden = True
    else:
        is_school = is_school_day(d, season_override)
        overridden = False

    classes = day_classes(db, user_id, d)
    sleep_min = cfg.DEFAULT_SLEEP_HOUR * 60 + cfg.DEFAULT_SLEEP_MINUTE
    class_minutes = 0
    for c in classes:
        if c.start_time and c.end_time:
            class_minutes += max(0, _minutes(c.end_time) - _minutes(c.start_time))

    end_min = cfg.DEFAULT_SCHOOL_END_HOUR * 60 + cfg.DEFAULT_SCHOOL_END_MINUTE
    base_capacity = (sleep_min - end_min) - cfg.DEFAULT_PERSONAL_TIME_MINUTES

    if is_school:
        capacity = base_capacity - class_minutes
        day_type = "school"
    else:
        # روز آزاد (پنج‌شنبه/جمعه/تابستان یا override «مدرسه نمی‌روم»)
        capacity = max(int(base_capacity * cfg.NO_SCHOOL_CAPACITY_MULTIPLIER),
                       cfg.NO_SCHOOL_MIN_CAPACITY_MINUTES)
        capacity -= class_minutes
        day_type = "free"

    capacity = max(capacity, 0)
    return {
        "date": d.isoformat(),
        "weekday": weekday_name_fa(d),
        "day_type": day_type,
        "is_school": is_school,
        "overridden": overridden,
        "classes": [{
            "id": c.id, "title": c.title,
            "subject_id": c.subject_id,
            "start": c.start_time, "end": c.end_time,
        } for c in classes],
        "class_minutes": class_minutes,
        "capacity_minutes": capacity,
    }


def get_capacity_estimate(db: Session, user_id: int, scope: str) -> CapacityEstimate:
    est = db.execute(
        select(CapacityEstimate).where(CapacityEstimate.user_id == user_id,
                                       CapacityEstimate.scope == scope)
    ).scalar_one_or_none()
    if est is None:
        est = CapacityEstimate(user_id=user_id, scope=scope,
                               tasks_per_day=cfg.DEFAULT_DAILY_TASK_CAPACITY,
                               confidence=0.2, evidence_count=0)
        db.add(est)
        db.flush()
    return est


def active_study_days(db: Session, user_id: int) -> int:
    """تعداد روزهای دارای Task تکمیل‌شده (active_days_with_completed_tasks)."""
    return db.scalar(
        select(func.count(func.distinct(DailyTaskPlacement.date))).select_from(Task)
        .join(DailyTaskPlacement, DailyTaskPlacement.task_id == Task.id)
        .where(Task.user_id == user_id, Task.status == "completed")
    ) or 0


def _completed_tasks_per_day(db: Session, user_id: int, school_days: bool,
                             window: int = 28) -> dict:
    """میانگین کارهای تکمیل‌شده در روزهای مدرسه/آزاد + تعداد روز."""
    today = today_tehran()
    rows = db.execute(
        select(DailyTaskPlacement.date, func.count(Task.id))
        .join(Task, Task.id == DailyTaskPlacement.task_id)
        .where(Task.user_id == user_id, Task.status == "completed",
               DailyTaskPlacement.date >= today - timedelta(days=window))
        .group_by(DailyTaskPlacement.date)
    ).all()
    vals = []
    for d, cnt in rows:
        if is_school_day(d) == school_days:
            vals.append(cnt)
    return {"avg": sum(vals) / len(vals) if vals else 0.0, "days": len(vals)}


def habits_summary(db: Session, user_id: int) -> dict:
    """خلاصه عادت (GET /habits/summary در API Delta V2)."""
    days = active_study_days(db, user_id)
    school = _completed_tasks_per_day(db, user_id, school_days=True)
    free = _completed_tasks_per_day(db, user_id, school_days=False)
    avg_duration = db.scalar(
        select(func.avg(TestSession.actual_duration_minutes)).where(
            TestSession.user_id == user_id,
            TestSession.actual_duration_minutes.isnot(None),
        )
    )
    past_threshold = days >= cfg.HABIT_LEARNING_DAYS

    advice = None
    if past_threshold:
        # نظر روی «تعداد کار» روز — بدون ساعت‌بندی خشک
        advice = {
            "school_day_avg": round(school["avg"], 2),
            "free_day_avg": round(free["avg"], 2),
            "message": (
                f"عادت تو در روز کلاس حدود {round(school['avg']) or '—'} کار است؛ "
                f"در روز آزاد حدود {round(free['avg']) or '—'} کار. "
                "برنامهٔ سنگین‌تر از این حدود پرریسک است."
            ),
        }

    return {
        "active_days": days,
        "threshold_days": cfg.HABIT_LEARNING_DAYS,
        "past_threshold": past_threshold,
        "school_day_avg_tasks": round(school["avg"], 2),
        "free_day_avg_tasks": round(free["avg"], 2),
        "avg_session_minutes": round(avg_duration, 1) if avg_duration else None,
        "advice": advice,
    }


def recommended_task_count(db: Session, user_id: int, day_type: str,
                           state_energy: float | None = None) -> dict:
    """توصیهٔ تعداد کار برای یک روز — خروجی دارای confidence و evidence (V2.1).

    ظرفیت از عملکرد گذشته برآورد می‌شود؛ قبل از ۳۰ روز داده محافظه‌کارانه است.
    """
    est = get_capacity_estimate(db, user_id, day_type)
    days = active_study_days(db, user_id)
    habit = _completed_tasks_per_day(db, user_id, school_days=(day_type == "school"))

    base = est.tasks_per_day
    # لایهٔ رفتاری V2.1: انرژی فعلی تعداد را تعدیل می‌کند (نه وزنهای هسته را)
    energy_factor = 1.0
    if state_energy is not None:
        energy_factor = 0.7 + 0.6 * state_energy  # 0.7..1.3
    recommended = max(cfg.CAPACITY_MIN_TASKS,
                      min(cfg.CAPACITY_MAX_TASKS, round(base * energy_factor)))
    return {
        "recommended_tasks": recommended,
        "estimated_capacity": round(base, 2),
        "confidence": est.confidence,
        "evidence_count": est.evidence_count,
        "active_days": days,
        "conservative": days < cfg.HABIT_LEARNING_DAYS,
        "recent_avg": round(habit["avg"], 2),
    }


def update_capacity_from_observation(db: Session, user_id: int, day_type: str,
                                     completed: int) -> None:
    """حلقهٔ تطبیق: Update — تغییر ظرفیت gradual (±۱۰٪ در هر به‌روزرسانی)."""
    est = get_capacity_estimate(db, user_id, day_type)
    old = est.tasks_per_day
    target = completed
    delta = max(-old * cfg.CAPACITY_ADJUST_STEP, min(old * cfg.CAPACITY_ADJUST_STEP,
                                                     (target - old) * 0.5))
    new = max(cfg.CAPACITY_MIN_TASKS, min(cfg.CAPACITY_MAX_TASKS, old + delta))
    est.tasks_per_day = round(new, 3)
    est.evidence_count += 1
    est.confidence = min(cfg.PERSONALITY_CONFIDENCE_MAX,
                         est.confidence + cfg.PERSONALITY_CONFIDENCE_STEP)
    est.updated_at = dt.datetime.utcnow()
