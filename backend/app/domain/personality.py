"""مدل شخصیت کاربر — V2.1.

قواعد (14_USER_PROFILE_AND_PERSONALITY_V2_1 و 22_CONFIDENCE_AND_EVIDENCE):
- همهٔ امتیازها 0..1 و همراه confidence ذخیره می‌شوند.
- یک پاسخ منفرد ویژگی را قطعی نمی‌کند (حرکت جزئی + افزایش پله‌ای confidence).
- self-report و observed behavior جدا نگه داشته می‌شوند.
- مدل قابل توضیح است: هر نتیجه evidence_count و last_updated دارد.
- ۳ مشاهده نباید مثل ۳۰ مشاهده اعتبار داشته باشد.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

import app.config as cfg
from app.models import UserProfile, User

DIMENSIONS = [
    "discipline", "planning_preference", "procrastination", "competition",
    "reward_sensitivity", "stress_tolerance", "routine_preference",
    "novelty_preference", "self_criticism", "goal_orientation",
]

DIMENSION_LABELS = {
    "discipline": "نظم و انضباط",
    "planning_preference": "ترجیح برنامه‌ریزی",
    "procrastination": "اهمال‌کاری",
    "competition": "رقابت‌طلبی",
    "reward_sensitivity": "حساسیت به پاداش",
    "stress_tolerance": "تحمل استرس",
    "routine_preference": "ترجیح روتین",
    "novelty_preference": "ترجیح تازگی",
    "self_criticism": "خودانتقادی",
    "goal_orientation": "هدف‌محوری",
}


def empty_dim() -> dict:
    return {"value": 0.5, "confidence": 0.0, "evidence_count": 0,
            "last_updated": None, "source": "self_report"}


def get_profile(db: Session, user: User) -> UserProfile:
    p = db.query(UserProfile).filter(UserProfile.user_id == user.id).one_or_none()
    if p is None:
        p = UserProfile(user_id=user.id, personality_json={}, preferences_json={},
                        behavior_json={})
        db.add(p)
        db.flush()
    pj = dict(p.personality_json or {})
    changed = False
    for d in DIMENSIONS:
        if d not in pj:
            pj[d] = empty_dim()
            changed = True
    if changed:
        p.personality_json = pj
    return p


def apply_evidence(db: Session, user: User, dimension: str, evidence_value: float,
                   source: str = "self_report", weight: float = 1.0) -> None:
    """به‌روزرسانی تدریجی یک بعد از مدل کاربر.

    evidence_value در 0..1 (شاهد از پاسخ یا رفتار).
    حرکت ارزش: value += (evidence - value) * STEP * weight
    confidence پله‌ای افزایش می‌یابد (هرگز از یک پاسخ قطعی نمی‌شود).
    """
    p = get_profile(db, user)
    pj = dict(p.personality_json)
    dim = dict(pj.get(dimension) or empty_dim())
    step = cfg.PERSONALITY_VALUE_STEP * weight
    dim["value"] = round(min(1.0, max(0.0,
                                      dim["value"] + (evidence_value - dim["value"]) * step)), 4)
    dim["evidence_count"] += 1
    dim["confidence"] = round(min(cfg.PERSONALITY_CONFIDENCE_MAX,
                                  dim["confidence"] + cfg.PERSONALITY_CONFIDENCE_STEP * weight), 4)
    dim["last_updated"] = dt.datetime.utcnow().isoformat()
    dim["source"] = source
    pj[dimension] = dim
    p.personality_json = pj


def evidence_weight(evidence_count: int) -> float:
    """۳ مشاهده نباید مثل ۳۰ مشاهده اعتبار داشته باشد — وزن confidence-aware."""
    return min(1.0, evidence_count / cfg.EVIDENCE_CONFIDENCE_SATURATION)


def profile_summary(db: Session, user: User) -> dict:
    p = get_profile(db, user)
    out = {}
    for d in DIMENSIONS:
        dim = p.personality_json.get(d) or empty_dim()
        out[d] = {
            "label": DIMENSION_LABELS[d],
            "value": dim["value"],
            "confidence": dim["confidence"],
            "evidence_count": dim["evidence_count"],
            "last_updated": dim.get("last_updated"),
        }
    return {
        "personality": out,
        "preferences": p.preferences_json or {},
        "behavior": p.behavior_json or {},
        "version": p.version,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
