"""Jalali calendar ۱۴۰۵–۱۴۰۸ (V3.1 doc 05).

Everything the student plans lives on a Persian-only calendar: exams, study tasks,
activities and goals. This service builds the month/year/day views, knows about
holidays and lets the student add their own occasions — all additive.

Honesty rules for holidays: only **solar, fixed** religious/national days are shipped
as data (they never move), each one carrying its `source`. Lunar occasions shift every
year; they are *not* invented here — the table is extensible
(``POST /calendar/occasions``) and every entry keeps the source it came from.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..core import jalali
from ..core.errors import NotFoundError, ValidationError
from ..core.timeutil import today_local, week_end, week_start
from ..db import models
from . import common

WEEKDAYS_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
MONTHS_FA = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]

# Fixed solar holidays (Jalali month, day) — these do not move year to year.
FIXED_HOLIDAYS = [
    ((1, 1), "نوروز", "تعطیل رسمی"),
    ((1, 2), "نوروز", "تعطیل رسمی"),
    ((1, 3), "نوروز", "تعطیل رسمی"),
    ((1, 4), "نوروز", "تعطیل رسمی"),
    ((1, 12), "روز جمهوری اسلامی ایران", "تعطیل رسمی"),
    ((1, 13), "سیزده‌بدر", "تعطیل رسمی"),
    ((3, 14), "رحلت امام خمینی", "تعطیل رسمی"),
    ((3, 15), "قیام ۱۵ خرداد", "تعطیل رسمی"),
    ((11, 22), "پیروزی انقلاب اسلامی", "تعطیل رسمی"),
    ((12, 29), "روز ملی شدن صنعت نفت", "تعطیل رسمی"),
]

MIN_YEAR = 1405
MAX_YEAR = 1408


def supported_years() -> list[int]:
    return [year for year in range(config.value("calendar.min_year"), config.value("calendar.max_year") + 1)]


def _check_year(year: int) -> int:
    if year < config.value("calendar.min_year") or year > config.value("calendar.max_year"):
        raise ValidationError(
            f"سال {year} خارج از بازهٔ پشتیبانی‌شده ({config.value('calendar.min_year')} تا "
            f"{config.value('calendar.max_year')}) است."
        )
    return year


def holidays_for(year: int) -> list[dict]:
    rows = []
    for (month, day), title, kind in FIXED_HOLIDAYS:
        if month == 12 and day == 30:
            continue
        if day > jalali.jalali_month_length(year, month):
            continue
        rows.append(
            {
                "date": f"{year}/{month:02d}/{day:02d}",
                "jalali": {"year": year, "month": month, "day": day},
                "title": title,
                "kind": kind,
                "source": "fixed_solar_holidays",
            }
        )
    return rows


def custom_occasions(db: Session, user: models.User, year: Optional[int] = None) -> list[dict]:
    rows = list(
        db.scalars(
            select(models.CalendarOccasion).where(
                models.CalendarOccasion.user_id == user.id,
                *([models.CalendarOccasion.jalali_year == year] if year else []),
            )
        )
    )
    return [
        {
            "id": row.id,
            "date": common.jdate(row.occurs_on),
            "title": row.title,
            "kind": row.kind,
            "is_holiday": bool(row.is_holiday),
            "source": "user",
            "note": row.note,
        }
        for row in rows
    ]


def add_occasion(db: Session, user: models.User, payload: dict) -> dict:
    occurs_on = common.parse_date_if_string(payload.get("date") or payload.get("occurs_on"))
    if not occurs_on:
        raise ValidationError("تاریخ مناسبت لازم است (مثلاً ۱۴۰۵/۰۷/۱۲).")
    _check_year(jalali.date_to_jalali(occurs_on)[0])
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValidationError("عنوان مناسبت لازم است.")
    row = models.CalendarOccasion(
        user_id=user.id,
        occurs_on=occurs_on,
        jalali_year=jalali.date_to_jalali(occurs_on)[0],
        title=title,
        kind=payload.get("kind") or "personal",
        is_holiday=bool(payload.get("is_holiday")),
        note=payload.get("note"),
    )
    db.add(row)
    db.flush()
    common.audit(db, "calendar_occasion_added", user_id=user.id, entity_type="calendar_occasion", entity_id=row.id, after={"title": title})
    return {"id": row.id, "date": common.jdate(occurs_on), "title": title, "kind": row.kind, "source": "user"}


def events_for_day(db: Session, user: models.User, day: _dt.date) -> list[dict]:
    events: list[dict] = []
    for exam in db.scalars(
        select(models.Exam).where(models.Exam.user_id == user.id, models.Exam.exam_date == day)
    ):
        events.append(
            {
                "kind": "exam",
                "id": exam.id,
                "title": exam.title,
                "exam_type": exam.exam_type,
                "start_time": exam.start_time.strftime("%H:%M") if exam.start_time else None,
                "is_holiday_relevant": True,
            }
        )
    for task in db.scalars(
        select(models.StudyTask).where(
            models.StudyTask.user_id == user.id,
            models.StudyTask.planned_date == day,
            models.StudyTask.status.not_in(["cancelled"]),
        )
    ):
        events.append(
            {
                "kind": "task",
                "id": task.id,
                "title": task.title,
                "task_type": task.task_type,
                "status": task.status,
                "planned_minutes": task.planned_minutes,
                "manual_override": bool(task.manual_override),
            }
        )
    for activity in db.scalars(
        select(models.Activity).where(models.Activity.user_id == user.id, models.Activity.date == day)
    ):
        events.append(
            {
                "kind": "activity",
                "id": activity.id,
                "title": activity.title,
                "category": activity.category,
                "minutes": activity.duration_minutes,
            }
        )
    for goal in db.scalars(
        select(models.Goal).where(models.Goal.user_id == user.id, models.Goal.target_date == day)
    ):
        events.append({"kind": "goal", "id": goal.id, "title": goal.title, "goal_type": goal.goal_type})
    return events


def _day_payload(db: Session, user: models.User, day: _dt.date, holiday_map: dict, occasion_map: dict) -> dict:
    jy, jm, jd = jalali.date_to_jalali(day)
    key = (jy, jm, jd)
    holidays = holiday_map.get(key, []) + occasion_map.get(key, [])
    tasks = db.scalars(
        select(models.StudyTask).where(
            models.StudyTask.user_id == user.id,
            models.StudyTask.planned_date == day,
            models.StudyTask.status.not_in(["cancelled"]),
        )
    ).all()
    planned_minutes = sum(task.planned_minutes or ((task.duration_low or 0) + (task.duration_high or 0)) // 2 or 0 for task in tasks)
    return {
        "date": common.jdate(day),
        "date_long": common.jdate_long(day),
        "iso": day.isoformat(),
        "jalali": {"year": jy, "month": jm, "day": jd},
        "month_title": f"{MONTHS_FA[jm - 1]} {jy}",
        "weekday": jalali.weekday_name_fa(day),
        "weekday_index": jalali.weekday_index_fa(day),  # 0 = شنبه
        "is_holiday": bool(holidays),
        "holiday_titles": [item["title"] for item in holidays],
        "events": events_for_day(db, user, day),
        "planned_minutes": planned_minutes,
    }


def month_view(db: Session, user: models.User, year: int, month: int) -> dict:
    _check_year(year)
    if month < 1 or month > 12:
        raise ValidationError("ماه باید بین ۱ و ۱۲ باشد.")
    length = jalali.jalali_month_length(year, month)
    days = [jalali.jalali_to_date(year, month, day) for day in range(1, length + 1)]
    holiday_map = _holiday_map(year)
    occasion_map, occasions = _occasion_map(db, user, year)
    payload = [_day_payload(db, user, day, holiday_map, occasion_map) for day in days]
    first = days[0]
    return {
        "year": year,
        "month": month,
        "month_title": f"{MONTHS_FA[month - 1]} {year}",
        "month_length": length,
        "is_leap_year": jalali.is_leap_jalali(year),
        "year_days": 366 if jalali.is_leap_jalali(year) else 365,
        "weekday_of_first": jalali.weekday_name_fa(first),
        "weekday_index_of_first": jalali.weekday_index_fa(first),
        "weekdays": WEEKDAYS_FA,
        "days": payload,
        "holidays": [item for item in holidays_for(year) if item["jalali"]["month"] == month],
        "occasions": [item for item in occasions if item["date"].startswith(f"{year}/{month:02d}")],
        "events_count": sum(len(day["events"]) for day in payload),
        "note": "همه تاریخ‌ها شمسی‌اند؛ هفته از شنبه شروع می‌شود.",
    }


def year_view(db: Session, user: models.User, year: int) -> dict:
    _check_year(year)
    months = []
    for month in range(1, 13):
        length = jalali.jalali_month_length(year, month)
        holiday_map = _holiday_map(year)
        occasion_map, _ = _occasion_map(db, user, year)
        days = [jalali.jalali_to_date(year, month, day) for day in range(1, length + 1)]
        payloads = [_day_payload(db, user, day, holiday_map, occasion_map) for day in days]
        months.append(
            {
                "month": month,
                "title": MONTHS_FA[month - 1],
                "month_length": length,
                "is_leap_month": month == 12 and length == 30,
                "holiday_count": sum(1 for day in payloads if day["is_holiday"]),
                "event_count": sum(len(day["events"]) for day in payloads),
                "busiest_day": max(payloads, key=lambda day: day["planned_minutes"])["date"] if payloads else None,
            }
        )
    return {
        "year": year,
        "is_leap_year": jalali.is_leap_jalali(year),
        "day_count": sum(month["month_length"] for month in months),
        "months": months,
        "holidays": holidays_for(year),
        "supported_years": supported_years(),
        "note": "تعطیلات قمری جابه‌جا می‌شوند و در این جدول حدس زده نمی‌شوند؛ می‌توانی خودت اضافه کنی.",
    }


def day_view(db: Session, user: models.User, date_text: str) -> dict:
    day = common.parse_date_if_string(date_text)
    if not day:
        raise ValidationError("تاریخ نامعتبر است.")
    _check_year(jalali.date_to_jalali(day)[0])
    holiday_map = _holiday_map(jalali.date_to_jalali(day)[0])
    occasion_map, _ = _occasion_map(db, user, jalali.date_to_jalali(day)[0])
    payload = _day_payload(db, user, day, holiday_map, occasion_map)
    payload["week"] = week_view(db, user, day)
    return payload


def week_view(db: Session, user: models.User, day: Optional[_dt.date] = None) -> dict:
    anchor = day or today_local()
    start = week_start(anchor)
    end = week_end(anchor)
    holiday_map = _holiday_map(jalali.date_to_jalali(start)[0])
    occasion_map, _ = _occasion_map(db, user, jalali.date_to_jalali(start)[0])
    days = [_day_payload(db, user, start + _dt.timedelta(days=offset), holiday_map, occasion_map) for offset in range(7)]
    return {
        "from": common.jdate(start),
        "to": common.jdate(end),
        "from_long": common.jdate_long(start),
        "to_long": common.jdate_long(end),
        "days": days,
        "note": "هفته از شنبه تا جمعه.",
    }


def range_payload() -> dict:
    return {
        "supported_years": supported_years(),
        "min_year": config.value("calendar.min_year"),
        "max_year": config.value("calendar.max_year"),
        "week_start": "شنبه",
        "timezone": config.value("calendar.coins_timezone"),
        "month_lengths": {
            year: [jalali.jalali_month_length(year, month) for month in range(1, 13)] for year in supported_years()
        },
        "leap_years": [year for year in supported_years() if jalali.is_leap_jalali(year)],
        "note": "همه محاسبات از موتور شمسی می‌آید؛ تاریخ میلادی هیچ‌جا نمایش داده نمی‌شود.",
    }


def _holiday_map(year: int) -> dict[tuple[int, int, int], list[dict]]:
    mapping: dict[tuple[int, int, int], list[dict]] = {}
    for item in holidays_for(year):
        mapping.setdefault((item["jalali"]["year"], item["jalali"]["month"], item["jalali"]["day"]), []).append(item)
    return mapping


def _occasion_map(db: Session, user: models.User, year: int) -> tuple[dict, list[dict]]:
    rows = custom_occasions(db, user, year=year)
    mapping: dict[tuple[int, int, int], list[dict]] = {}
    for item in rows:
        parsed = jalali.date_to_jalali(jalali.parse_jalali(item["date"]))
        mapping.setdefault(parsed, []).append(item)
    return mapping, rows
