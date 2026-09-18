"""Day timeline (V3.1 doc 08 — «Planner: تقویم شمسی + timeline روزانه»).

The timeline is a *view*, never a new plan:

* fixed things (activities, classes, exams with a clock, tasks the student gave a
  start time to) are shown where they really are;
* tasks with **no** start time get a *suggested* slot so the day is readable —
  those entries are marked ``suggested`` and nothing is written to the database;
* overlaps between fixed entries are *reported*, never silently resolved
  (V3 rule: no silent data corruption, never undo a manual choice).

Everything is computed from the same capacity engine the planner uses, so the
timeline can never disagree with the week plan.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..core.errors import ValidationError
from ..core.timeutil import today_local, week_start
from ..db import models
from . import capacity as capacity_service
from . import calendar_service, common

TASK_STATUS_LABEL_FA = {
    "planned": "برنامه‌ریزی‌شده",
    "in_progress": "در جریان",
    "completed": "انجام‌شده",
    "skipped": "رد‌شده",
    "cancelled": "لغو‌شده",
    "deferred": "جابه‌جاشده",
}


def _to_minutes(value: Optional[_dt.time]) -> Optional[int]:
    if value is None:
        return None
    return value.hour * 60 + value.minute


def _clock(minutes: int) -> str:
    minutes = max(0, min(24 * 60, int(minutes)))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_clock(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    raw = common.normalize_digits(str(text)).replace(":", ".").strip()
    if "." in raw:
        head, _, tail = raw.partition(".")
        if not head.isdigit() or (tail and not tail.isdigit()):
            return None
        hour, minute = int(head), int(tail or 0)
    elif raw.isdigit():
        hour, minute = int(raw), 0
    else:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def _task_minutes(task: models.StudyTask) -> int:
    if task.planned_minutes:
        return int(task.planned_minutes)
    if task.duration_low and task.duration_high:
        return int(round((task.duration_low + task.duration_high) / 2))
    return int(task.duration_low or task.duration_high or 25)


def _overlaps(rows: list[dict]) -> list[dict]:
    conflicts: list[dict] = []
    fixed = [row for row in rows if row["fixed"] and row["start_minutes"] is not None]
    fixed.sort(key=lambda row: row["start_minutes"])
    for index, row in enumerate(fixed):
        for other in fixed[index + 1:]:
            if other["start_minutes"] >= row["end_minutes"]:
                break
            conflicts.append(
                {
                    "a": {"kind": row["kind"], "title": row["title"], "start": row["start"], "end": row["end"]},
                    "b": {"kind": other["kind"], "title": other["title"], "start": other["start"], "end": other["end"]},
                    "note": "هم‌پوشانی گزارش می‌شود و خودکار جابه‌جا نمی‌شود؛ تصمیم با خودت است.",
                }
            )
    return conflicts


def _first_free_slot(busy: list[tuple[int, int]], start: int, minutes: int, limit: int) -> Optional[int]:
    """Earliest place at or after ``start`` that fits without touching a fixed block."""
    cursor = start
    for begin, end in sorted(busy):
        if cursor + minutes <= begin:
            return cursor
        if cursor < end:
            cursor = end
    if cursor + minutes <= limit:
        return cursor
    return None


def day_timeline(db: Session, user: models.User, day: _dt.date, *, include_suggested: bool = True) -> dict:
    wake = parse_clock(config.value("capacity.default_school_end_time")) or 7 * 60
    sleep = parse_clock(config.value("capacity.default_sleep_time")) or 23 * 60
    start_hour = parse_clock(config.value("capacity.timeline_start_time")) or min(wake, 8 * 60)

    rows: list[dict] = []
    busy: list[tuple[int, int]] = []

    # 1) activities — they occupy time and are never study work
    for activity in capacity_service.activities_for_day(db, user, day):
        start_minutes = _to_minutes(activity.start_time)
        end_minutes = _to_minutes(activity.end_time)
        if start_minutes is None and activity.duration_minutes:
            start_minutes = None
        minutes = (
            max(0, end_minutes - start_minutes)
            if start_minutes is not None and end_minutes is not None
            else int(activity.duration_minutes or 0)
        )
        if start_minutes is not None:
            end_minutes = end_minutes if end_minutes is not None else start_minutes + minutes
            busy.append((start_minutes, end_minutes))
        rows.append(
            {
                "kind": "activity",
                "title": activity.title,
                "category": activity.category,
                "scheduling_type": activity.scheduling_type,
                "start_minutes": start_minutes,
                "end_minutes": (start_minutes + minutes) if start_minutes is not None else None,
                "start": _clock(start_minutes) if start_minutes is not None else None,
                "end": _clock((start_minutes + minutes)) if start_minutes is not None else None,
                "minutes": minutes,
                "fixed": start_minutes is not None,
                "suggested": False,
                "why": "فعالیت زمان می‌گیرد و هیچ‌وقت «کار مطالعهٔ انجام‌نشده» حساب نمی‌شود.",
            }
        )

    # 2) classes
    for klass in capacity_service.classes_for_day(db, user, day):
        start_minutes = _to_minutes(klass.start_time)
        end_minutes = _to_minutes(klass.end_time)
        if start_minutes is None:
            continue
        if end_minutes is None:
            end_minutes = start_minutes + 60
        busy.append((start_minutes, end_minutes))
        rows.append(
            {
                "kind": "class",
                "title": klass.title,
                "start_minutes": start_minutes,
                "end_minutes": end_minutes,
                "start": _clock(start_minutes),
                "end": _clock(end_minutes),
                "minutes": max(0, end_minutes - start_minutes),
                "fixed": True,
                "suggested": False,
                "why": "کلاس، زمان ثابت هفته است.",
            }
        )

    # 3) exams with a clock
    for exam in db.scalars(
        select(models.Exam).where(
            models.Exam.user_id == user.id,
            models.Exam.exam_date == day,
            models.Exam.status != "cancelled",
        )
    ).all():
        start_minutes = _to_minutes(exam.start_time)
        minutes = int(exam.planned_duration_minutes or exam.actual_duration_minutes or 120)
        end_minutes = (start_minutes + minutes) if start_minutes is not None else None
        if start_minutes is not None:
            busy.append((start_minutes, end_minutes))
        rows.append(
            {
                "kind": "exam",
                "title": exam.title,
                "exam_id": exam.id,
                "exam_type": exam.exam_type,
                "start_minutes": start_minutes,
                "end_minutes": end_minutes,
                "start": _clock(start_minutes) if start_minutes is not None else None,
                "end": _clock(end_minutes) if end_minutes is not None else None,
                "minutes": minutes,
                "fixed": start_minutes is not None,
                "suggested": False,
                "why": "روز آزمون، بار روز را تعیین می‌کند.",
            }
        )

    # 4) study tasks — with a clock they are fixed, without one they get a suggestion
    tasks = list(
        db.scalars(
            select(models.StudyTask)
            .where(
                models.StudyTask.user_id == user.id,
                models.StudyTask.planned_date == day,
                models.StudyTask.status.not_in(["cancelled"]),
            )
            .order_by(models.StudyTask.display_order, models.StudyTask.id)
        )
    )
    pending: list[dict] = []
    for task in tasks:
        minutes = _task_minutes(task)
        start_minutes = _to_minutes(task.planned_start_time)
        topic_title = None
        if task.topic_id:
            topic = db.get(models.Topic, task.topic_id)
            topic_title = topic.title if topic else None
        row = {
            "kind": "task",
            "task_id": task.id,
            "title": task.title,
            "task_type": task.task_type,
            "topic_id": task.topic_id,
            "topic_title": topic_title,
            "status": task.status,
            "status_label": TASK_STATUS_LABEL_FA.get(task.status, task.status),
            "manual": bool(task.manual_override),
            "minutes": minutes,
            "start_minutes": start_minutes,
            "end_minutes": (start_minutes + minutes) if start_minutes is not None else None,
            "start": _clock(start_minutes) if start_minutes is not None else None,
            "end": _clock((start_minutes + minutes)) if start_minutes is not None else None,
            "fixed": start_minutes is not None,
            "suggested": False,
            "why": (
                "ساعت این کار را خودت تعیین کرده‌ای."
                if start_minutes is not None
                else "بدون ساعت ثبت شده؛ جای پیشنهادی نمایش داده می‌شود و چیزی در داده تغییر نمی‌کند."
            ),
        }
        if start_minutes is not None:
            busy.append((start_minutes, row["end_minutes"]))
            rows.append(row)
        else:
            pending.append(row)

    unplaced: list[dict] = []
    if include_suggested:
        cursor = start_hour
        for row in pending:
            slot = _first_free_slot(busy, cursor, row["minutes"], sleep)
            if slot is None:
                unplaced.append({**row, "reason": "تا ساعت خواب جای خالی به این اندازه پیدا نشد."})
                continue
            end = slot + row["minutes"]
            busy.append((slot, end))
            cursor = end
            rows.append(
                {
                    **row,
                    "start_minutes": slot,
                    "end_minutes": end,
                    "start": _clock(slot),
                    "end": _clock(end),
                    "suggested": True,
                }
            )
    else:
        unplaced = [{**row, "reason": "نمایش بدون چیدمان پیشنهادی خواسته شده است."} for row in pending]

    rows.sort(key=lambda row: (row["start_minutes"] is None, row["start_minutes"] or 0, row["title"] or ""))

    day_info = calendar_service.day_view(db, user, common.jdate(day))
    capacity = capacity_service.day_capacity(db, user, day)
    planned = sum(row["minutes"] for row in rows if row["kind"] == "task")
    fixed_minutes = sum(row["minutes"] for row in rows if row["fixed"])
    busy_sorted = sorted(busy)
    free_windows: list[dict] = []
    cursor = start_hour
    for begin, end in busy_sorted:
        if begin - cursor >= 20:
            free_windows.append({"from": _clock(cursor), "to": _clock(begin), "minutes": begin - cursor})
        cursor = max(cursor, end)
    if sleep - cursor >= 20:
        free_windows.append({"from": _clock(cursor), "to": _clock(sleep), "minutes": sleep - cursor})

    return {
        "date": common.jdate(day),
        "date_long": common.jdate_long(day),
        "weekday": common.weekday_fa(day),
        "jalali": day_info["jalali"],
        "is_holiday": day_info["is_holiday"],
        "holiday_titles": day_info["holiday_titles"],
        "window": {"from": _clock(start_hour), "to": _clock(sleep), "from_minutes": start_hour, "to_minutes": sleep},
        "entries": rows,
        "unplaced": unplaced,
        "conflicts": _overlaps(rows),
        "free_windows": free_windows,
        "totals": {
            "entries": len(rows),
            "task_count": len([row for row in rows if row["kind"] == "task"]),
            "suggested_count": len([row for row in rows if row["suggested"]]),
            "planned_task_minutes": planned,
            "fixed_minutes": fixed_minutes,
            "realistic_capacity_minutes": capacity["realistic_minutes"],
            "theoretical_minutes": capacity["theoretical_minutes"],
            "remaining_minutes": max(0, capacity["realistic_minutes"] - planned),
        },
        "notes": {
            "view_only": "این تایم‌لاین فقط نمایش است؛ هیچ ساعتی روی کارها ذخیره نمی‌شود.",
            "suggested": "کارهای بدون ساعت با علامت «پیشنهادی» دیده می‌شوند و با جابه‌جایی، خودت تعیین می‌کنی.",
            "conflict": "هم‌پوشانی‌ها گزارش می‌شوند؛ برنامه خودکار چیزی را پاک یا جابه‌جا نمی‌کند.",
            "capacity": "ظرفیت واقع‌بینانه از عملکرد خودت می‌آید، نه از ساعت‌های آزاد تقویم.",
        },
    }


def week_timeline(db: Session, user: models.User, day: Optional[_dt.date] = None) -> dict:
    anchor = day or today_local()
    start = week_start(anchor)
    days = [day_timeline(db, user, start + _dt.timedelta(days=offset)) for offset in range(7)]
    return {
        "from": days[0]["date"],
        "to": days[-1]["date"],
        "days": days,
        "busiest": max(days, key=lambda item: item["totals"]["planned_task_minutes"])["date_long"],
        "note": "هفته از شنبه تا جمعه؛ هر روز تایم‌لاین مستقل دارد.",
    }


def payload_or_422(db: Session, user: models.User, date_text: Optional[str], *, week: bool = False) -> dict:
    if week:
        return week_timeline(db, user)
    day = common.parse_date_if_string(date_text) if date_text else today_local()
    if not day:
        raise ValidationError("تاریخ نامعتبر است.")
    return day_timeline(db, user, day)
