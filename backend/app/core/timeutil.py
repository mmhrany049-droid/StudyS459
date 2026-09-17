"""Time / calendar helpers bound to the Iranian week and Asia/Tehran timezone."""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from . import jalali

try:  # pragma: no cover - depends on OS tz database availability
    from zoneinfo import ZoneInfo

    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:  # pragma: no cover
    TEHRAN = _dt.timezone(_dt.timedelta(hours=3, minutes=30), name="Asia/Tehran")

DEFAULT_TIMEZONE = "Asia/Tehran"


def now_utc() -> _dt.datetime:
    """Timezone-naive UTC timestamp (storage format for every datetime column)."""
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


def utc_to_local(value: _dt.datetime, tz=TEHRAN) -> _dt.datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=_dt.timezone.utc)
    return value.astimezone(tz)


def local_to_utc(value: _dt.datetime, tz=TEHRAN) -> _dt.datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)
    return value.astimezone(_dt.timezone.utc).replace(tzinfo=None)


def local_now(tz=TEHRAN) -> _dt.datetime:
    return _dt.datetime.now(tz)


def today_local(tz=TEHRAN) -> _dt.date:
    """Today according to the user's Iranian local date."""
    return local_now(tz).date()


def local_time_now(tz=TEHRAN) -> _dt.time:
    return local_now(tz).time()


# ---------------------------------------------------------------------------
# Iranian week: Saturday -> Friday
# ---------------------------------------------------------------------------

def week_start(date_value: _dt.date) -> _dt.date:
    """Return the Saturday that starts the Iranian week containing `date_value`."""
    offset = (date_value.weekday() - jalali.SATURDAY) % 7
    return date_value - _dt.timedelta(days=offset)


def week_end(date_value: _dt.date) -> _dt.date:
    return week_start(date_value) + _dt.timedelta(days=6)


def week_days(start: _dt.date) -> list[_dt.date]:
    return [start + _dt.timedelta(days=i) for i in range(7)]


def week_start_from_jalali(text: str) -> _dt.date:
    return week_start(jalali.parse_jalali(text))


def week_label_fa(date_value: _dt.date) -> str:
    """«شنبه ۲۱ تا جمعه ۲۷ شهریور ۱۴۰۴»"""
    start, end = week_start(date_value), week_end(date_value)
    jy, jm, jd = jalali.date_to_jalali(end)
    return (
        f"{jalali.weekday_name_fa(start)} {jalali.to_persian_digits(str(jalali.date_to_jalali(start)[2]))}"
        f" تا {jalali.weekday_name_fa(end)} {jalali.to_persian_digits(str(jd))}"
        f" {jalali.JALALI_MONTHS[jm - 1]} {jalali.to_persian_digits(str(jy))}"
    )


def is_school_day_default(date_value: _dt.date) -> bool:
    """Saturday..Wednesday are school days, Thursday/Friday are free (V2 spec)."""
    return date_value.weekday() not in (jalali.FRIDAY, 3)  # 3 == Thursday


def season_mode(date_value: _dt.date) -> str:
    """school_term during the Iranian school year, summer during holidays."""
    _, jm, jd = jalali.date_to_jalali(date_value)
    # Iranian school year: roughly 1 Mehr (jm=7) .. end of Khordad (jm=3, day 31)
    if jm == 7 or jm in (8, 9, 10, 11, 12):
        return "school_term"
    if jm in (1, 2, 3):
        return "school_term"
    return "summer"


def parse_iso(value: str) -> _dt.datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = _dt.datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    return parsed


def parse_date(value: str) -> _dt.date:
    """Accept ISO (2026-09-15) or Jalali (1405/06/24) input."""
    text = value.strip()
    if "/" in text:
        return jalali.parse_jalali(text)
    return _dt.date.fromisoformat(text)


def minutes_between(start: _dt.datetime, end: _dt.datetime) -> float:
    return round((end - start).total_seconds() / 60.0, 1)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def round_half(value: float) -> float:
    return float(int(value * 2 + 0.5)) / 2.0


def safe_div(numerator: float, denominator: float) -> Optional[float]:
    if not denominator:
        return None  # missing evidence is not zero (V3 invariant 10)
    return numerator / denominator
