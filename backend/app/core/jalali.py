"""Jalali (Solar Hijri) calendar utilities.

Pure-python port of the well tested JDN based algorithm (Borkowski / jalaali-js).
No third party dependency, deterministic and unit tested.

V3 rule (study_system_v2_2_docs/07_JALALI_ONLY.md):
    - internal storage stays Gregorian/UTC,
    - every user facing date is Jalali,
    - the week starts on Saturday (شنبه) and ends on Friday (جمعه).
"""

from __future__ import annotations

import datetime as _dt
from typing import Tuple

# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# Python weekday(): Monday == 0 ... Sunday == 6
WEEKDAY_NAMES_FA = {
    0: "دوشنبه",
    1: "سه‌شنبه",
    2: "چهارشنبه",
    3: "پنج‌شنبه",
    4: "جمعه",
    5: "شنبه",
    6: "یکشنبه",
}

# Week order used everywhere in the product: Saturday -> Friday
WEEK_ORDER = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]

# python weekday() index for Saturday (week start) and Friday (week end)
SATURDAY = 5
FRIDAY = 4

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
LATIN_DIGITS = "0123456789"

_BREAKS = [
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
]


class JalaliError(ValueError):
    """Raised for out of range Jalali dates."""


def _div(a: int, b: int) -> int:
    """Truncated integer division (mirrors JS ``~~(a / b)``).

    The calendar algorithm is only correct with truncation toward zero, not
    Python's floor division: ``div(-5, 6)`` must be ``0`` here (floor ``-1``
    shifts a whole Gregorian year and broke every conversion).
    """
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _mod(a: int, b: int) -> int:
    """Truncated remainder (mirrors JS ``a % b``: sign follows the dividend)."""
    return a - _div(a, b) * b


# ---------------------------------------------------------------------------
# Core conversion (JDN based)
# ---------------------------------------------------------------------------

def jal_cal(jy: int) -> dict:
    bl = len(_BREAKS)
    gy = jy + 621
    leap_j = -14
    jp = _BREAKS[0]
    jump = 0
    if jy < jp or jy >= _BREAKS[bl - 1]:
        raise JalaliError(f"Invalid Jalali year {jy}")
    for i in range(1, bl):
        jm = _BREAKS[i]
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    raw_leap = _mod(_mod(n + 1, 33) - 1, 4)
    if raw_leap == -1:
        raw_leap = 4
    if jump - n < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    return {"leap": raw_leap, "gy": gy, "march": march}


def is_leap_jalali(jy: int) -> bool:
    return jal_cal(jy)["leap"] == 0

def jalali_month_length(jy: int, jm: int) -> int:
    if not 1 <= jm <= 12:
        raise JalaliError(f"Invalid Jalali month {jm}")
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_leap_jalali(jy) else 29


def _g2d(gy: int, gm: int, gd: int) -> int:
    d = (
        _div((gy + _div(gm - 8, 6) + 100100) * 1461, 4)
        + _div(153 * _mod(gm + 9, 12) + 2, 5)
        + gd - 34840408
    )
    d = d - _div(_div(gy + 100100 + _div(gm - 8, 6), 100) * 3, 4) + 752
    return d


def _d2g(jdn: int) -> Tuple[int, int, int]:
    j = 4 * jdn + 139361631
    j = j + _div(_div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _div(_mod(j, 1461), 4) * 5 + 308
    gd = _div(_mod(i, 153), 5) + 1
    gm = _mod(_div(i, 153), 12) + 1
    gy = _div(j, 1461) - 100100 + _div(8 - gm, 6)
    return gy, gm, gd


def _j2d(jy: int, jm: int, jd: int) -> int:
    r = jal_cal(jy)
    return _g2d(r["gy"], 3, r["march"]) + (jm - 1) * 31 - _div(jm, 7) * (jm - 7) + jd - 1


def _d2j(jdn: int) -> Tuple[int, int, int]:
    gy = _d2g(jdn)[0]
    jy = gy - 621
    r = jal_cal(jy)
    jdn1f = _g2d(gy, 3, r["march"])
    k = jdn - jdn1f
    if k >= 0:
        if k <= 185:
            jm = 1 + _div(k, 31)
            jd = _mod(k, 31) + 1
            return jy, jm, jd
        k -= 186
    else:
        jy -= 1
        k += 179
        if r["leap"] == 1:
            k += 1
    jm = 7 + _div(k, 30)
    jd = _mod(k, 30) + 1
    return jy, jm, jd


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    """Gregorian calendar date -> (jy, jm, jd)."""
    return _d2j(_g2d(gy, gm, gd))


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> Tuple[int, int, int]:
    """(jy, jm, jd) -> Gregorian calendar date."""
    if not 1 <= jm <= 12:
        raise JalaliError(f"Invalid Jalali month {jm}")
    if not 1 <= jd <= jalali_month_length(jy, jm):
        raise JalaliError(f"Invalid Jalali day {jd} for {jy}/{jm}")
    return _d2g(_j2d(jy, jm, jd))


# ---------------------------------------------------------------------------
# datetime helpers
# ---------------------------------------------------------------------------

def date_to_jalali(value: _dt.date) -> Tuple[int, int, int]:
    return gregorian_to_jalali(value.year, value.month, value.day)


def jalali_to_date(jy: int, jm: int, jd: int) -> _dt.date:
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    return _dt.date(gy, gm, gd)


def parse_jalali(text: str) -> _dt.date:
    """Parse '1404/06/24' (also accepts Persian digits and '-') into a date."""
    raw = normalize_digits(str(text).strip().replace("-", "/").replace(".", "/"))
    parts = [p for p in raw.split("/") if p != ""]
    if len(parts) != 3:
        raise JalaliError(f"Cannot parse Jalali date: {text!r}")
    jy, jm, jd = (int(p) for p in parts)
    if jy < 100:  # tolerate 2 digit years like 04/06/24
        jy += 1400
    return jalali_to_date(jy, jm, jd)


def format_jalali(value: _dt.date | _dt.datetime | None, persian_digits: bool = True) -> str | None:
    """Format a Gregorian date/datetime as '۱۴۰۴/۰۶/۲۴'."""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        value = value.date()
    jy, jm, jd = date_to_jalali(value)
    text = f"{jy:04d}/{jm:02d}/{jd:02d}"
    return to_persian_digits(text) if persian_digits else text


def format_jalali_long(value: _dt.date | _dt.datetime | None) -> str | None:
    """'جمعه ۲۴ شهریور ۱۴۰۴'"""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        value = value.date()
    jy, jm, jd = date_to_jalali(value)
    return f"{weekday_name_fa(value)} {to_persian_digits(str(jd))} {JALALI_MONTHS[jm - 1]} {to_persian_digits(str(jy))}"


def weekday_name_fa(value: _dt.date) -> str:
    return WEEKDAY_NAMES_FA[value.weekday()]


def weekday_index_fa(value: _dt.date) -> int:
    """0 = شنبه ... 6 = جمعه (product week order)."""
    return (value.weekday() + 2) % 7


def to_persian_digits(text: str) -> str:
    return text.translate(str.maketrans(LATIN_DIGITS, PERSIAN_DIGITS))


def to_latin_digits(text: str) -> str:
    return str(text).translate(str.maketrans(PERSIAN_DIGITS, LATIN_DIGITS))


def normalize_digits(text: str) -> str:
    return to_latin_digits(text).replace("٫", ".").strip()


def jalali_year_bounds(jy: int) -> Tuple[_dt.date, _dt.date]:
    return jalali_to_date(jy, 1, 1), jalali_to_date(jy, 12, jalali_month_length(jy, 12))


def today_jalali_str(today: _dt.date | None = None) -> str:
    return format_jalali(today or _dt.date.today())
