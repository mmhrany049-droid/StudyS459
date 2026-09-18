"""Activity model (V3.1 doc 06) — the other half of «همه چیز درس خواندن نیست».

An activity occupies time and availability; it is *never* a failed study task and
it never becomes "missed work". Categories and scheduling types are registries
too, so a student or an extension can add their own without touching the engine.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .. import config
from .enums import ACTIVITY_LABELS_FA, ActivityCategory

# code → (label, whether it typically blocks study time, hint)
BASE_CATEGORIES: Dict[str, dict] = {
    ActivityCategory.SPORT.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.SPORT], "blocks": True},
    ActivityCategory.GYM.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.GYM], "blocks": True},
    ActivityCategory.WORK.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.WORK], "blocks": True},
    ActivityCategory.APPOINTMENT.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.APPOINTMENT], "blocks": True},
    ActivityCategory.FAMILY.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.FAMILY], "blocks": True},
    ActivityCategory.SCHOOL.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.SCHOOL], "blocks": True},
    ActivityCategory.COMMUTE.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.COMMUTE], "blocks": True},
    ActivityCategory.REST.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.REST], "blocks": True},
    ActivityCategory.TRAVEL.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.TRAVEL], "blocks": True},
    ActivityCategory.CLASS.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.CLASS], "blocks": True},
    ActivityCategory.OTHER.value: {"label": ACTIVITY_LABELS_FA[ActivityCategory.OTHER], "blocks": True},
}

SCHEDULING_TYPES: Dict[str, dict] = {
    "fixed": {"label": "ثابت", "hint": "سر ساعت مشخصی اتفاق می‌افتد و قابل جابه‌جایی نیست."},
    "preferred": {"label": "ترجیحی", "hint": "بهتر است در آن بازه باشد، ولی اگر نشد اشکالی ندارد."},
    "flexible": {"label": "انعطاف‌پذیر", "hint": "در طول روز/هفته هر وقت شد انجام می‌شود."},
    "deadline_only": {"label": "فقط مهلت", "hint": "فقط باید تا یک روز تمام شود؛ زمانش آزاد است."},
}


def custom_categories() -> Dict[str, dict]:
    raw = config.value("activities.custom_categories") or []
    result: Dict[str, dict] = {}
    for item in raw:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        code = str(item["code"])
        result[code] = {
            "label": item.get("label") or code,
            "blocks": bool(item.get("blocks", True)),
            "hint": item.get("hint") or "دستهٔ سفارشی از تنظیمات.",
            "custom": True,
        }
    return result


def categories() -> Dict[str, dict]:
    merged: Dict[str, dict] = {}
    merged.update(BASE_CATEGORIES)
    merged.update(custom_categories())
    return merged


def is_valid_category(code: Optional[str]) -> bool:
    return bool(code) and code in categories()


def category_label(code: Optional[str]) -> str:
    entry = categories().get(code or "")
    return (entry or {}).get("label", code or "سایر")


def is_valid_scheduling(value: Optional[str]) -> bool:
    return bool(value) and value in SCHEDULING_TYPES


def payload() -> dict:
    return {
        "categories": [
            {"code": code, "label": entry["label"], "blocks_time": bool(entry.get("blocks", True)), "custom": bool(entry.get("custom"))}
            for code, entry in sorted(categories().items())
        ],
        "scheduling_types": [
            {"code": code, "label": entry["label"], "hint": entry["hint"]} for code, entry in SCHEDULING_TYPES.items()
        ],
        "custom_count": len(custom_categories()),
        "policy": "فعالیت‌ها زمان را اشغال می‌کنند و هرگز «کار مطالعهٔ انجام‌نشده» حساب نمی‌شوند.",
        "note": "دسته‌های سفارشی از تنظیمات (activities.custom_categories) اضافه می‌شوند؛ هسته سناریویی را hard-code نمی‌کند.",
    }


def list_categories() -> List[dict]:
    return payload()["categories"]
