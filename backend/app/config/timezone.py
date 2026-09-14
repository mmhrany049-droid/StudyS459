"""
Centralized timezone/date handling strategy
- Store timestamps consistently in UTC
- Planner week/day calculations timezone-aware
- User is in Iran-oriented academic context (Asia/Tehran) but don't scatter assumptions
"""
from datetime import datetime, timezone, timedelta
import pytz
from .settings import settings
from typing import Optional

DEFAULT_TZ = pytz.timezone(settings.timezone_default)

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def now_local() -> datetime:
    return datetime.now(DEFAULT_TZ)

def utc_to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(DEFAULT_TZ)

def local_to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = DEFAULT_TZ.localize(dt)
    return dt.astimezone(timezone.utc)

def parse_iso_date(date_str: str) -> datetime:
    """Parse YYYY-MM-DD as UTC midnight"""
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)

def get_saturday_of_week(date: Optional[datetime] = None) -> str:
    """Get Saturday (start of week in Iran) for given date, timezone-aware"""
    if date is None:
        date = now_utc()
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    local_date = utc_to_local(date)
    # Python weekday: Monday=0, Saturday=5
    days_since_saturday = (local_date.weekday() - 5) % 7
    saturday = local_date - timedelta(days=days_since_saturday)
    saturday = saturday.replace(hour=0, minute=0, second=0, microsecond=0)
    return saturday.astimezone(timezone.utc).strftime("%Y-%m-%d")

def get_week_range(saturday_str: str) -> tuple[str, str]:
    """Given Saturday, return (start, end) Friday"""
    start = parse_iso_date(saturday_str)
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

def is_catchup_day(day_of_week: str) -> bool:
    """Thursday/Friday are catch-up days"""
    return day_of_week.lower() in ["thursday", "friday", "پنجشنبه", "جمعه"]

def get_persian_weekday_name(day_en: str) -> str:
    mapping = {
        "saturday": "شنبه",
        "sunday": "یکشنبه",
        "monday": "دوشنبه",
        "tuesday": "سه‌شنبه",
        "wednesday": "چهارشنبه",
        "thursday": "پنجشنبه",
        "friday": "جمعه"
    }
    return mapping.get(day_en.lower(), day_en)
