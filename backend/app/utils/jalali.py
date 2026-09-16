"""
تبدیل تاریخ میلادی ↔ هجری شمسی بدون وابستگی خارجی.
الگوریتم: Borkowski (همان مبنای jdatetime) — دقیق برای سال‌های ۱ تا ۳۱۷۷ هجری شمسی.
ذخیره داخلی میلادی است؛ نمایش شمسی (سند 02_CALENDAR_JALALI_IRAN).
هفته ایرانی: شنبه=0 ... جمعه=6
"""
from datetime import date, timedelta

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
PERSIAN_WEEKDAYS = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
SCHOOL_DAYS = {0, 1, 2, 3, 4}  # شنبه تا چهارشنبه

_BREAKS = [
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
]


def _div(a: int, b: int) -> int:
    """تقسیم با کوتاه‌سازی به سمت صفر (مثل JS ~~(a/b)) — نه floor پایتون."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _mod(a: int, b: int) -> int:
    """باقی‌مانده متناظر با _div (علامت مقسوم را حفظ می‌کند)."""
    return a - _div(a, b) * b


def _g2d(gy: int, gm: int, gd: int) -> int:
    """میلادی → شماره روز ژولیَن (JDN)"""
    d = (
        _div((gy + _div(gm - 8, 6) + 100100) * 1461, 4)
        + _div(153 * ((gm + 9) % 12) + 2, 5)
        + gd
        - 34840408
    )
    return d - _div(_div(gy + 100100 + _div(gm - 8, 6), 100) * 3, 4) + 752


def _d2g(jdn: int) -> tuple[int, int, int]:
    """JDN → میلادی"""
    j = 4 * jdn + 139361631
    j += _div(_div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _div(j % 1461, 4) * 5 + 308
    gd = _div(i % 153, 5) + 1
    gm = (_div(i, 153) % 12) + 1
    gy = _div(j, 1461) - 100100 + _div(8 - gm, 6)
    return gy, gm, gd


def _jal_cal(jy: int) -> tuple[int, int, int]:
    """(leap, gy, march) برای یک سال شمسی"""
    bl = len(_BREAKS)
    gy = jy + 621
    leap_j = -14
    jp = _BREAKS[0]
    if jy < jp or jy >= _BREAKS[bl - 1]:
        raise ValueError(f"سال شمسی خارج از محدوده: {jy}")
    jump = 0
    for i in range(1, bl):
        jm = _BREAKS[i]
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(jump % 33, 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div((n % 33) + 3, 4)
    if (jump % 33) == 4 and (jump - n) == 4:
        leap_j += 1
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if (jump - n) < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4
    return leap, gy, march


def gregorian_to_jalali(g_y: int, g_m: int, g_d: int) -> tuple[int, int, int]:
    jdn = _g2d(g_y, g_m, g_d)
    gy = _d2g(jdn)[0]
    jy = gy - 621
    leap, _, march = _jal_cal(jy)
    jdn1f = _g2d(gy, 3, march)
    k = jdn - jdn1f
    if k >= 0:
        if k <= 185:
            return jy, 1 + _div(k, 31), (k % 31) + 1
        k -= 186
    else:
        jy -= 1
        k += 179
        if leap == 1:
            k += 1
    return jy, 7 + _div(k, 30), (k % 30) + 1


def jalali_to_gregorian(j_y: int, j_m: int, j_d: int) -> tuple[int, int, int]:
    _, gy, march = _jal_cal(j_y)
    jdn = _g2d(gy, 3, march) + (j_m - 1) * 31 - _div(j_m, 7) * (j_m - 7) + j_d - 1
    return _d2g(jdn)


def is_jalali_leap(j_y: int) -> bool:
    return _jal_cal(j_y)[0] == 0


def to_jalali_str(d: date, with_weekday: bool = False) -> str:
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    s = f"{jy:04d}/{jm:02d}/{jd:02d}"
    return f"{weekday_name(d)} {s}" if with_weekday else s


def to_jalali_long(d: date) -> str:
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return f"{weekday_name(d)} {jd} {PERSIAN_MONTHS[jm - 1]} {jy}"


def iran_weekday(d: date) -> int:
    """شنبه=0 ... جمعه=6 (python: دوشنبه=0 ... یکشنبه=6)"""
    return (d.weekday() + 2) % 7


def weekday_name(d: date) -> str:
    return PERSIAN_WEEKDAYS[iran_weekday(d)]


def week_start(d: date) -> date:
    """شنبه همان هفته"""
    return d - timedelta(days=iran_weekday(d))


def week_end(d: date) -> date:
    return week_start(d) + timedelta(days=6)


def week_days(anchor: date) -> list[date]:
    s = week_start(anchor)
    return [s + timedelta(days=i) for i in range(7)]


def is_school_day(d: date, season_mode: str = "school_term") -> bool:
    if season_mode == "summer":
        return False
    return iran_weekday(d) in SCHOOL_DAYS


def describe(d: date) -> dict:
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return {
        "date": d.isoformat(),
        "jalali": f"{jy:04d}/{jm:02d}/{jd:02d}",
        "jalali_long": to_jalali_long(d),
        "weekday": weekday_name(d),
        "weekday_index": iran_weekday(d),
    }
