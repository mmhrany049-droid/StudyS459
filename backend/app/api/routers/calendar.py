"""Calendar router: Persian-only month/year/day/week views and occasions (V3.1 doc 05)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.timeutil import today_local
from ...db import models
from ...db.base import get_db
from ...services import calendar_service, common
from ..deps import current_user

router = APIRouter(tags=["calendar"])


class OccasionPayload(BaseModel):
    date: str
    title: str
    kind: str = "personal"
    is_holiday: bool = False
    note: Optional[str] = None


@router.get("/calendar/range")
def calendar_range() -> dict:
    """Supported Jalali years (۱۴۰۵–۱۴۰۸), month lengths and leap years."""
    return calendar_service.range_payload()


@router.get("/calendar/month")
def calendar_month(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    today = today_local()
    jy, jm, _ = calendar_service.jalali.date_to_jalali(today)
    return calendar_service.month_view(db, user, year or jy, month or jm)


@router.get("/calendar/year")
def calendar_year(
    year: Optional[int] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    today = today_local()
    jy, _, _ = calendar_service.jalali.date_to_jalali(today)
    return calendar_service.year_view(db, user, year or jy)


@router.get("/calendar/day")
def calendar_day(
    date: Optional[str] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    return calendar_service.day_view(db, user, date or common.jdate(today_local()))


@router.get("/calendar/week")
def calendar_week(
    date: Optional[str] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    anchor = common.parse_date_if_string(date) if date else None
    return calendar_service.week_view(db, user, anchor)


@router.get("/calendar/occasions")
def list_occasions(
    year: Optional[int] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    today = today_local()
    jy, _, _ = calendar_service.jalali.date_to_jalali(today)
    rows = calendar_service.custom_occasions(db, user, year=year or jy)
    return {
        "occasions": rows,
        "count": len(rows),
        "note": "مناسبت‌های شخصی؛ تعطیلات ثابت شمسی جدا و از منبع داخلی می‌آیند.",
    }


@router.post("/calendar/occasions")
def add_occasion(
    payload: OccasionPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = calendar_service.add_occasion(db, user, payload.model_dump())
    db.commit()
    return result
