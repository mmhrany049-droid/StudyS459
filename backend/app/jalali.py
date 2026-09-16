"""تبدیل تاریخ هجری شمسی (جلالی) — بدون وابستگی سنگین (طبق سند V2 تقویم).

ذخیره‌سازی داخلی میلادی ISO است؛ نمایش شمسی در لایه presentation.
الگوریتم کلاسیک FarsiWeb (Roozbeh Pournader) — چرخهٔ ۳۳ ساله.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tehran")

_G_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
_J_DAYS = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]


def to_jalali(d: dt.date) -> tuple[int, int, int]:
    """میلادی → جلالی"""
    gy, gm, gd = d.year - 1600, d.month - 1, d.day
    day_no = (365 * gy + (gy + 3) // 4 - (gy + 99) // 100
              + (gy + 399) // 400 + gd - 1 - 79)
    for i in range(gm):
        day_no += _G_DAYS[i]
    if gm > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        day_no += 1

    j_np = day_no // 12053
    day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (day_no // 1461)
    day_no %= 1461
    if day_no >= 366:
        day_no -= 1
        jy += day_no // 365
        day_no %= 365

    jm = 0
    for i in range(11):
        if day_no < _J_DAYS[i]:
            break
        day_no -= _J_DAYS[i]
        jm = i + 1
    return jy, jm + 1, day_no + 1


def from_jalali(jy: int, jm: int, jd: int) -> dt.date:
    """جلالی → میلادی"""
    jy2, jm2, jd2 = jy - 979, jm - 1, jd - 1
    day_no = 365 * jy2 + (jy2 // 33) * 8 + (jy2 % 33 + 3) // 4 + jd2 + 79
    for i in range(jm2):
        day_no += _J_DAYS[i]

    gy = 1600 + 400 * (day_no // 146097)
    day_no %= 146097
    leap = 1
    if day_no >= 36525:
        day_no -= 1
        gy += 100 * (day_no // 36524)
        day_no %= 36524
        if day_no >= 365:
            day_no += 1
        else:
            leap = 0
    gy += 4 * (day_no // 1461)
    day_no %= 1461
    if day_no >= 366:
        leap = 0
        day_no -= 1
        gy += day_no // 365
        day_no %= 365

    gm = 0
    while day_no >= _G_DAYS[gm] + (1 if (gm == 1 and leap) else 0):
        day_no -= _G_DAYS[gm] + (1 if (gm == 1 and leap) else 0)
        gm += 1
    return dt.date(gy, gm + 1, day_no + 1)


PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# python weekday(): دوشنبه=0، سه‌شنبه=1، چهارشنبه=2، پنج‌شنبه=3، جمعه=4، شنبه=5، یکشنبه=6
WEEKDAY_NAMES = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]
JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def fa_num(x) -> str:
    return str(x).translate(PERSIAN_DIGITS)


def weekday_name_fa(d: dt.date) -> str:
    return WEEKDAY_NAMES[d.weekday()]


def jalali_str(d: dt.date, fa: bool = True) -> str:
    jy, jm, jd = to_jalali(d)
    s = f"{jy:04d}/{jm:02d}/{jd:02d}"
    return s.translate(PERSIAN_DIGITS) if fa else s


def jalali_long(d: dt.date) -> str:
    jy, jm, jd = to_jalali(d)
    return f"{fa_num(jd)} {JALALI_MONTHS[jm - 1]} {fa_num(jy)}"


def today_tehran() -> dt.date:
    return dt.datetime.now(TZ).date()


def now_tehran() -> dt.datetime:
    return dt.datetime.now(TZ)


def parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def week_start_of(d: dt.date) -> dt.date:
    """شنبه‌ی همان هفته (هفته ایرانی: شنبه تا جمعه)."""
    return d - dt.timedelta(days=(d.weekday() - 5) % 7)


def week_days(week_start: dt.date) -> list[dt.date]:
    return [week_start + dt.timedelta(days=i) for i in range(7)]


def jalali_season(d: dt.date) -> str:
    _, jm, _ = to_jalali(d)
    if 1 <= jm <= 3:
        return "spring"
    if 4 <= jm <= 6:
        return "summer"
    if 7 <= jm <= 9:
        return "autumn"
    return "winter"


def season_mode(d: dt.date, override: str | None = None) -> str:
    """school_term برای پاییز/زمستان/بهار، summer برای تابستان؛ قابل override دستی."""
    if override:
        return override
    return "summer" if jalali_season(d) == "summer" else "school_term"


def is_school_day(d: dt.date, season_override: str | None = None) -> bool:
    """شنبه تا چهارشنبه روز مدرسه (در حالت school_term). پنج‌شنبه و جمعه آزاد."""
    if season_mode(d, season_override) == "summer":
        return False
    return d.weekday() not in (3, 4)  # Thursday=3, Friday=4
