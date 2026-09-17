"""Study-task types (V3.1 doc 06) — a registry, not a hard-coded scenario list.

The document asks for «مدل typeدار و قابل گسترش؛ بدون hard-code سناریوهای خاص در هسته»
with the initial set:

    study · practice_test · review · exam_analysis · notes_completion
    written_practice · other

Two rules keep the upgrade additive:

* every legacy V3 code (``read_lesson``, ``test_session``, ``review_session``,
  ``error_review``, ``active_recall``, ``goal_task``, ``exam_prep``,
  ``mock_retake``) stays valid and is *mapped* to a V3.1 family instead of being
  rewritten in existing rows;
* new types can be added from configuration (``tasks.custom_types``) without
  touching the engine.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .. import config

# code → (Persian label, family, default intervention, whether it needs questions)
BASE_TYPES: Dict[str, dict] = {
    "study": {
        "label": "مطالعه/یادگیری",
        "family": "study",
        "intervention": "READ_LESSON",
        "needs_questions": False,
        "hint": "خواندن و فهمیدن؛ واحدش دقیقه است نه سؤال.",
    },
    "practice_test": {
        "label": "تمرین تست",
        "family": "practice",
        "intervention": "MIXED_PRACTICE",
        "needs_questions": True,
        "hint": "تمرین از بانک تست یک مبحث.",
    },
    "review": {
        "label": "مرور",
        "family": "review",
        "intervention": "REVIEW",
        "needs_questions": True,
        "hint": "مرور زمان‌بندی‌شدهٔ همان چیزی که فراموش می‌شود.",
    },
    "exam_analysis": {
        "label": "تحلیل آزمون",
        "family": "analysis",
        "intervention": None,
        "needs_questions": False,
        "hint": "بررسی برگه و خطاها؛ کار شناختی است نه آزمون دوباره.",
    },
    "notes_completion": {
        "label": "تکمیل جزوه/یادداشت",
        "family": "notes",
        "intervention": None,
        "needs_questions": False,
        "hint": "مرتب‌کردن یادداشت‌ها؛ زمان‌بر است ولی تمرین نیست.",
    },
    "written_practice": {
        "label": "تمرین تشریحی/نوشتاری",
        "family": "practice",
        "intervention": None,
        "needs_questions": False,
        "hint": "حل تشریحی؛ با تست چهارگزینه‌ای قاطی نمی‌شود.",
    },
    "other": {
        "label": "سایر",
        "family": "other",
        "intervention": None,
        "needs_questions": False,
        "hint": "کار دیگری که در فهرست نیست؛ از تنظیمات هم می‌توانی نوع جدید بسازی.",
    },
}

# legacy V3 codes stay valid; each maps onto a V3.1 family
LEGACY_TYPES: Dict[str, dict] = {
    "read_lesson": {"label": "خواندن درس", "family": "study", "intervention": "READ_LESSON", "needs_questions": False},
    "test_session": {
        "label": "جلسه تست",
        "family": "practice",
        "intervention": "MIXED_PRACTICE",
        "needs_questions": True,
    },
    "review_session": {"label": "جلسه مرور", "family": "review", "intervention": "REVIEW", "needs_questions": True},
    "error_review": {"label": "بازبینی خطاها", "family": "review", "intervention": "ERROR_REVIEW", "needs_questions": True},
    "active_recall": {"label": "یادآوری فعال", "family": "review", "intervention": "ACTIVE_RECALL", "needs_questions": False},
    "goal_task": {"label": "کار هدف", "family": "study", "intervention": None, "needs_questions": False},
    "exam_prep": {"label": "آماده‌سازی امتحان", "family": "practice", "intervention": "MIXED_PRACTICE", "needs_questions": True},
    "mock_retake": {"label": "تکرار آزمون آزمایشی", "family": "practice", "intervention": "MOCK_EXAM", "needs_questions": True},
}


def custom_types() -> Dict[str, dict]:
    raw = config.value("tasks.custom_types") or []
    result: Dict[str, dict] = {}
    for item in raw:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        code = str(item["code"])
        result[code] = {
            "label": item.get("label") or code,
            "family": item.get("family") or "other",
            "intervention": item.get("intervention"),
            "needs_questions": bool(item.get("needs_questions", False)),
            "hint": item.get("hint") or "نوع سفارشی از تنظیمات.",
            "custom": True,
        }
    return result


def registry() -> Dict[str, dict]:
    merged: Dict[str, dict] = {}
    merged.update(BASE_TYPES)
    for code, payload in LEGACY_TYPES.items():
        merged.setdefault(code, {**payload, "legacy": True})
    merged.update(custom_types())
    return merged


def is_valid(code: Optional[str]) -> bool:
    return bool(code) and code in registry()


def normalize(code: Optional[str]) -> str:
    """Old codes are never rewritten, but planner-facing families are resolved here."""
    if not code:
        return "other"
    return code if code in registry() else "other"


def family_of(code: Optional[str]) -> str:
    entry = registry().get(normalize(code))
    return (entry or {}).get("family", "other")


def label_of(code: Optional[str]) -> str:
    entry = registry().get(normalize(code))
    return (entry or {}).get("label", code or "سایر")


def needs_questions(code: Optional[str]) -> bool:
    entry = registry().get(normalize(code))
    return bool((entry or {}).get("needs_questions"))


def default_intervention(code: Optional[str]) -> Optional[str]:
    entry = registry().get(normalize(code))
    return (entry or {}).get("intervention")


def families() -> List[dict]:
    labels = {
        "study": "یادگیری",
        "practice": "تمرین",
        "review": "مرور",
        "analysis": "تحلیل",
        "notes": "یادداشت",
        "other": "سایر",
    }
    return [{"code": code, "label": label} for code, label in labels.items()]


def payload() -> dict:
    rows = []
    for code, entry in registry().items():
        rows.append(
            {
                "code": code,
                "label": entry.get("label"),
                "family": entry.get("family", "other"),
                "family_label": next(
                    (item["label"] for item in families() if item["code"] == entry.get("family")), "سایر"
                ),
                "needs_questions": bool(entry.get("needs_questions")),
                "hint": entry.get("hint") or "",
                "legacy": bool(entry.get("legacy")),
                "custom": bool(entry.get("custom")),
            }
        )
    rows.sort(key=lambda item: (item["family"], item["code"]))
    return {
        "types": rows,
        "families": families(),
        "count": len(rows),
        "custom_count": len(custom_types()),
        "note": "انواع پایه + کدهای قدیمی V3 (سازگار) + انواع سفارشی تنظیمات؛ هسته سناریوی خاصی را hard-code نمی‌کند.",
    }
