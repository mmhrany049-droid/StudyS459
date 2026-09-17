"""Purposeful questioning (V3.1 doc 07) — short, skippable, and *connected*.

The document forbids decorative questions and forbids one answer jumping a
parameter. So every question here declares:

* ``because`` — why we ask it (shown to the student),
* an *axis* — what uncertainty it reduces,
* an *effect* — the bounded, small change it is allowed to make
  (``capacity.today``, ``capacity.tomorrow``, ``planner.weight.<name>`` or
  ``ordering`` only).

Channels and their connections:

====================  =========================================
``onboarding``        scenario questions → model confidence (small deltas)
``day_start``         2–4 questions → *that day's* capacity
``day_end``           2–4 questions → next day's capacity estimate + behaviour
``weekly``            build/close of the week → planner and goal weights
====================  =========================================

Personality answers never lock anything: they only re-order suggestions and
only once enough evidence exists (:func:`ordering_bias`).
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.errors import ValidationError
from ..core.timeutil import today_local
from ..db import models
from . import common

# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

CHANNELS: dict[str, dict] = {
    "onboarding": {
        "label": "پرسشنامهٔ سناریومحور آشنایی",
        "min_questions": 1,
        "max_questions": 8,
        "connector": "model.confidence",
        "connector_fa": "فقط عدم‌قطعیت مدل را کم می‌کند؛ هیچ پارامتری را جهشی تغییر نمی‌دهد.",
    },
    "day_start": {
        "label": "آغاز روز",
        "min_questions": 2,
        "max_questions": 4,
        "connector": "capacity.today",
        "connector_fa": "پاسخ‌ها با گام کوچک روی ظرفیت واقع‌بینانهٔ همین روز اثر می‌گذارند.",
    },
    "day_end": {
        "label": "پایان روز",
        "min_questions": 2,
        "max_questions": 4,
        "connector": "capacity.tomorrow",
        "connector_fa": "اجرا و مانع امروز، فقط برآورد فردا را کمی اصلاح می‌کند.",
    },
    "weekly": {
        "label": "ساخت برنامهٔ هفتگی / پایان هفته",
        "min_questions": 2,
        "max_questions": 4,
        "connector": "planner.weights",
        "connector_fa": "وزن هدف و برنامه را کمی جابه‌جا می‌کند؛ نه قفل و نه حذف.",
    },
}


def _scale(code, text, because, axis, *, min_value=1, max_value=5, effect=None, core=False, base=0.6):
    return {
        "code": code,
        "text": text,
        "kind": "scale",
        "min": min_value,
        "max": max_value,
        "options": [],
        "because": because,
        "axis": axis,
        "effect": effect or {"target": "none"},
        "core": core,
        "base_information_value": base,
    }


def _choice(code, text, because, axis, options, *, effect=None, core=False, base=0.6, multiple=False):
    return {
        "code": code,
        "text": text,
        "kind": "multi_choice" if multiple else "single_choice",
        "options": options,
        "because": because,
        "axis": axis,
        "effect": effect or {"target": "none"},
        "core": core,
        "base_information_value": base,
    }


def _text(code, text, because, axis, *, effect=None, core=False, base=0.3):
    return {
        "code": code,
        "text": text,
        "kind": "short_text",
        "options": [],
        "because": because,
        "axis": axis,
        "effect": effect or {"target": "none"},
        "core": core,
        "base_information_value": base,
    }


BANK: dict[str, dict] = {
    # ---- start of day: energy, real free time, today's priority -------------
    "energy": _scale(
        "energy",
        "انرژی امروزت چطور است؟",
        "انرژی، ظرفیت واقعی همین روز را کمی جابه‌جا می‌کند؛ با گام کوچک و قابل برگشت.",
        "energy",
        effect={"target": "capacity.today", "per_step": 0.05, "neutral": 3, "max_abs": 0.10},
        core=True,
        base=0.75,
    ),
    "free_time": _scale(
        "free_time",
        "امروز چقدر وقت آزاد *قابل استفاده* داری؟",
        "وقت آزاد با ظرفیت واقعی فرق دارد؛ این پاسخ فقط برآورد امروز را اصلاح می‌کند.",
        "free_time",
        effect={"target": "capacity.today", "per_step": 0.05, "neutral": 3, "max_abs": 0.10},
        core=True,
        base=0.72,
    ),
    "today_priority": _choice(
        "today_priority",
        "اگر امروز فقط یک چیز را تمام کنی، چه باشد؟",
        "ترتیب پیشنهادها را با انتخاب خودت هم‌راستا می‌کند؛ بدون تغییر در برنامهٔ کلی.",
        "preference",
        [
            {"id": "goal", "label": "کار هدف فعال"},
            {"id": "review", "label": "مرور چیزی که نزدیک فراموشی است"},
            {"id": "exam", "label": "مبحث امتحان نزدیک"},
            {"id": "open", "label": "کاری که خودم می‌گویم"},
        ],
        effect={"target": "ordering.today", "note": "فقط ترتیب داخل روز را عوض می‌کند."},
        core=True,
        base=0.65,
    ),
    "sleep": _scale(
        "sleep",
        "خواب دیشب چطور بود؟",
        "خواب کم، ظرفیت امروز را کم می‌کند؛ ولی فقط کمی، نه اینکه کارها حذف شوند.",
        "sleep",
        effect={"target": "capacity.today", "per_step": 0.04, "neutral": 3, "max_abs": 0.08},
        base=0.45,
    ),
    "exam_stress": _scale(
        "exam_stress",
        "استرس امتحان امروز چقدر است؟",
        "استرس بالا فقط کمی بار امروز را سبک‌تر می‌کند؛ امتحان حذف نمی‌شود.",
        "stress",
        effect={"target": "capacity.today", "per_step": -0.03, "neutral": 3, "max_abs": 0.06},
        base=0.5,
    ),
    # ---- end of day: execution, obstacle -----------------------------------
    "plan_followed": _scale(
        "plan_followed",
        "چقدر طبق برنامه پیش رفتی؟",
        "مبنای عادت توست، نه قضاوت؛ برآورد فردا را فقط کمی اصلاح می‌کند.",
        "execution",
        effect={"target": "capacity.tomorrow", "per_step": 0.03, "neutral": 3, "max_abs": 0.06},
        core=True,
        base=0.7,
    ),
    "obstacle": _choice(
        "obstacle",
        "بزرگ‌ترین مانع امروز چه بود؟",
        "مانع، دلیل واقعی است؛ پیشنهاد فردا بر همین اساس عوض می‌شود، نه با سرزنش.",
        "obstacle",
        [
            {"id": "sleep", "label": "خستگی و کم‌خوابی"},
            {"id": "phone", "label": "گوشی و حواس‌پرتی"},
            {"id": "unclear", "label": "کار برایم مبهم بود"},
            {"id": "time", "label": "وقت کم بود"},
            {"id": "none", "label": "مانع خاصی نبود"},
        ],
        effect={"target": "capacity.tomorrow", "note": "بسته به مانع، حداکثر ۳٪ برآورد فردا اصلاح می‌شود."},
        core=True,
        base=0.6,
    ),
    "satisfaction": _scale(
        "satisfaction",
        "از امروز چقدر راضی هستی؟",
        "برای دیدن روند حال تو در طول هفته؛ روی اولویت‌ها اثر جهشی ندارد.",
        "mood",
        effect={"target": "none"},
        base=0.35,
    ),
    "tomorrow_focus": _text(
        "tomorrow_focus",
        "فردا روی چه چیزی تمرکز کنی؟",
        "در ترتیب پیشنهادهای فردا استفاده می‌شود؛ اگر دوست نداشتی رد کن.",
        "preference",
        effect={"target": "ordering.tomorrow"},
        base=0.4,
    ),
    # ---- weekly: build / close of the week ---------------------------------
    "week_load": _choice(
        "week_load",
        "بار این هفته چطور بود؟",
        "وزن برنامهٔ هفتهٔ بعد را کمی تنظیم می‌کند تا برنامه از توان واقعی تو جلو نزند.",
        "load",
        [
            {"id": "light", "label": "سبک بود"},
            {"id": "right", "label": "مناسب بود"},
            {"id": "heavy", "label": "سنگین بود"},
        ],
        effect={
            "target": "planner.weight",
            "weight": "priority.weight.opportunity",
            "deltas": {"light": 0.02, "right": 0.0, "heavy": -0.05},
            "max_abs": 0.10,
        },
        core=True,
        base=0.65,
    ),
    "focus_subject": _choice(
        "focus_subject",
        "این هفته کدام درس بیشترین اولویت را دارد؟",
        "وزن هدف را کمی به نفع همان درس می‌چرخاند؛ بقیهٔ درس‌ها حذف نمی‌شوند.",
        "focus",
        [{"id": "none", "label": "بدون تمرکز خاص"}],
        effect={
            "target": "planner.weight",
            "weight": "priority.weight.goal_need",
            "deltas": {"none": 0.0},
            "default_delta": 0.06,
            "max_abs": 0.12,
        },
        core=True,
        base=0.6,
    ),
    "hardest_topic": _text(
        "hardest_topic",
        "سخت‌ترین مبحث این هفته چه بود؟",
        "وزن مرور را کمی برای همان مبحث بالا می‌برد؛ نه اینکه ضعیف اعلام شوی.",
        "difficulty",
        effect={
            "target": "planner.weight",
            "weight": "priority.weight.review_need",
            "per_answer": 0.05,
            "max_abs": 0.10,
        },
        base=0.45,
    ),
    "week_plan_style": _choice(
        "week_plan_style",
        "برنامهٔ هفتهٔ بعد دقیق‌تر باشد یا انعطاف‌پذیرتر؟",
        "شکل برنامه را عوض می‌کند؛ جنس کارها را نه.",
        "style",
        [
            {"id": "exact", "label": "دقیق‌تر با تعداد مشخص"},
            {"id": "flexible", "label": "انعطاف‌پذیر، فقط تعداد کار"},
        ],
        effect={"target": "ordering.week"},
        base=0.4,
    ),
}

CHANNEL_BANK: dict[str, list[str]] = {
    "day_start": ["energy", "free_time", "today_priority", "sleep", "exam_stress"],
    "day_end": ["plan_followed", "obstacle", "satisfaction", "tomorrow_focus"],
    "weekly": ["week_load", "focus_subject", "hardest_topic", "week_plan_style"],
    "onboarding": [],
}


# ---------------------------------------------------------------------------
# Information value and selection
# ---------------------------------------------------------------------------


def _axis_evidence(db: Session, user: models.User, axis: str) -> int:
    """How many *raw* answers we already have on this axis (evidence, not opinion)."""
    rows = db.scalars(
        select(models.DailyCheckin).where(models.DailyCheckin.user_id == user.id).order_by(models.DailyCheckin.day.desc()).limit(60)
    ).all()
    weekly = db.scalars(
        select(models.WeeklyReflection).where(models.WeeklyReflection.user_id == user.id).limit(20)
    ).all()
    count = 0
    for row in list(rows) + list(weekly):
        for key in (row.answers or {}).keys():
            if key == axis or key.startswith(f"{axis}."):
                count += 1
    if count:
        return count
    observations = db.scalar(
        select(func.count(models.BehaviorObservation.id)).where(
            models.BehaviorObservation.user_id == user.id, models.BehaviorObservation.kind.like(f"%{axis}%")
        )
    ) or 0
    return int(observations)


def information_value(db: Session, user: models.User, definition: dict) -> float:
    """Value = how much this answer reduces uncertainty we actually still have."""
    evidence = _axis_evidence(db, user, definition["axis"])
    confidence = common.confidence_from_evidence(evidence)
    return round(min(1.0, definition["base_information_value"] * (1.0 + (1 - confidence))), 3)


def answered_codes(db: Session, user: models.User, channel: str, day: _dt.date) -> set[str]:
    if channel in {"day_start", "day_end"}:
        row = db.scalars(
            select(models.DailyCheckin).where(
                models.DailyCheckin.user_id == user.id,
                models.DailyCheckin.day == day,
                models.DailyCheckin.phase == ("start" if channel == "day_start" else "end"),
            )
        ).first()
    elif channel == "weekly":
        row = db.scalars(
            select(models.WeeklyReflection).where(
                models.WeeklyReflection.user_id == user.id, models.WeeklyReflection.week_start == day
            )
        ).first()
    else:
        row = None
    return set((row.answers or {}).keys()) if row else set()


def questions_for(
    db: Session, user: models.User, channel: str, *, day: Optional[_dt.date] = None, include_answered: bool = False
) -> list[dict]:
    """Adaptive 2–4 questions: core ones first, then whatever reduces most uncertainty."""
    if channel not in CHANNELS:
        raise ValidationError("کانال پرسش‌گری شناخته نشد.", details={"choices": sorted(CHANNELS)})
    anchor = day or today_local()
    if channel == "weekly":
        anchor = anchor - _dt.timedelta(days=(anchor.weekday() - 5) % 7)
    spec = CHANNELS[channel]
    done = set() if include_answered else answered_codes(db, user, channel, anchor)
    rows = []
    for code in CHANNEL_BANK[channel]:
        definition = BANK[code]
        if code in done:
            continue
        if not _contextually_relevant(db, user, code, anchor):
            continue
        rows.append(
            {
                **{key: value for key, value in definition.items() if key != "base_information_value"},
                "information_value": information_value(db, user, definition),
                "channel": channel,
                "skippable": True,
            }
        )
    rows.sort(key=lambda item: (not item["core"], -item["information_value"]))
    limit = min(spec["max_questions"], max(spec["min_questions"], _budget(channel)))
    return rows[:limit]


def _budget(channel: str) -> int:
    if channel in {"day_start", "day_end"}:
        return int(config.value("questioning.daily_max_questions"))
    if channel == "weekly":
        return int(config.value("questioning.weekly_max_questions"))
    return 3


def _contextually_relevant(db: Session, user: models.User, code: str, day: _dt.date) -> bool:
    """No spam and no irrelevant questions."""
    if code == "exam_stress":
        return bool(
            db.scalars(
                select(models.Exam).where(
                    models.Exam.user_id == user.id,
                    models.Exam.exam_date == day,
                    models.Exam.status != "cancelled",
                )
            ).first()
        )
    if code == "sleep":
        return _axis_evidence(db, user, "sleep") < 3
    if code == "focus_subject":
        return True
    if code == "hardest_topic":
        return bool(
            db.scalars(
                select(models.StudyTask).where(
                    models.StudyTask.user_id == user.id,
                    models.StudyTask.planned_date >= day - _dt.timedelta(days=7),
                    models.StudyTask.planned_date <= day,
                )
            ).first()
        )
    if code == "today_priority":
        return True
    return True


def channel_payload(db: Session, user: models.User, channel: str, *, day: Optional[_dt.date] = None) -> dict:
    anchor = day or today_local()
    spec = CHANNELS[channel]
    questions = questions_for(db, user, channel, day=anchor)
    return {
        "channel": channel,
        "label": spec["label"],
        "connector": spec["connector"],
        "connector_fa": spec["connector_fa"],
        "questions": questions,
        "asked_count": len(questions),
        "min_questions": spec["min_questions"],
        "max_questions": spec["max_questions"],
        "skippable": True,
        "tone": "کوتاه، قابل رد کردن، بدون تکرار در همان روز.",
        "note": (
            "سؤال تزئینی پرسیده نمی‌شود: هر سؤال یک محور عدم‌قطعیت دارد و اثرش کوچک و باندشده است."
        ),
        "date": common.jdate(anchor),
    }


# ---------------------------------------------------------------------------
# Effects — small, bounded, stored apart from the raw answers
# ---------------------------------------------------------------------------


def _bounded_delta(definition: dict, value) -> Optional[float]:
    effect = definition.get("effect") or {}
    if effect.get("target") not in {"capacity.today", "capacity.tomorrow", "planner.weight"}:
        return None
    if definition["kind"] == "scale":
        numeric = common.to_float(value)
        if numeric is None:
            return None
        neutral = effect.get("neutral", 3)
        per_step = effect.get("per_step", 0.0)
        raw = (numeric - neutral) * per_step
    elif definition["kind"] == "single_choice":
        deltas = effect.get("deltas") or {}
        key = str(value)
        if key in deltas:
            raw = float(deltas[key])
        else:
            raw = float(effect.get("default_delta", 0.0))
    elif definition["kind"] == "short_text":
        raw = float(effect.get("per_answer", 0.0)) if str(value or "").strip() else 0.0
    else:
        return None
    max_abs = abs(effect.get("max_abs", config.value("questioning.max_answer_delta_pct")))
    return max(-max_abs, min(max_abs, raw))


def _store_effect(
    db: Session,
    user: models.User,
    *,
    channel: str,
    code: str,
    day: _dt.date,
    applied_to: str,
    delta_pct: float,
    confidence: float,
    evidence_count: int,
    note: str,
    checkin_id: Optional[int] = None,
) -> models.QuestionEffect:
    row = db.scalars(
        select(models.QuestionEffect).where(
            models.QuestionEffect.user_id == user.id,
            models.QuestionEffect.channel == channel,
            models.QuestionEffect.question_code == code,
            models.QuestionEffect.day == day,
        )
    ).first()
    if row is None:
        row = models.QuestionEffect(user_id=user.id, channel=channel, question_code=code, day=day)
        db.add(row)
    row.applied_to = applied_to
    row.delta_pct = round(delta_pct, 4)
    row.confidence = round(confidence, 3)
    row.evidence_count = evidence_count
    row.note = note
    row.checkin_id = checkin_id
    row.model_version = config.MODEL_VERSION
    db.flush()
    return row


def apply_answers(
    db: Session,
    user: models.User,
    channel: str,
    answers: dict,
    *,
    day: Optional[_dt.date] = None,
    checkin_id: Optional[int] = None,
    skipped: bool = False,
) -> dict:
    """Turn answers into *bounded* effects; skip is a first-class, recorded answer."""
    anchor = day or today_local()
    effects: list[dict] = []
    for code, value in (answers or {}).items():
        definition = BANK.get(code)
        if not definition:
            continue
        effect = definition.get("effect") or {}
        target = effect.get("target")
        evidence = _axis_evidence(db, user, definition["axis"])
        confidence = common.confidence_from_evidence(evidence)
        if target in {"capacity.today", "capacity.tomorrow"}:
            delta = _bounded_delta(definition, value)
            if delta is None:
                continue
            applied_to = target
            row = _store_effect(
                db,
                user,
                channel=channel,
                code=code,
                day=anchor if target == "capacity.today" else anchor + _dt.timedelta(days=1),
                applied_to=applied_to,
                delta_pct=delta,
                confidence=confidence,
                evidence_count=evidence,
                note=f"{definition['text']} → پاسخ «{value}»",
                checkin_id=checkin_id,
            )
            effects.append(_effect_payload(row))
        elif target == "planner.weight":
            delta = _bounded_delta(definition, value)
            if delta is None:
                continue
            applied_to = f"{effect.get('weight')}@{channel}"
            row = _store_effect(
                db,
                user,
                channel=channel,
                code=code,
                day=anchor,
                applied_to=applied_to,
                delta_pct=delta,
                confidence=confidence,
                evidence_count=evidence,
                note=f"{definition['text']} → پاسخ «{value}»",
                checkin_id=checkin_id,
            )
            effects.append(_effect_payload(row))
        elif target in {"ordering.today", "ordering.tomorrow", "ordering.week"}:
            row = _store_effect(
                db,
                user,
                channel=channel,
                code=code,
                day=anchor,
                applied_to=target,
                delta_pct=0.0,
                confidence=confidence,
                evidence_count=evidence,
                note=f"فقط ترتیب پیشنهاد؛ {definition['text']} → پاسخ «{value}»",
                checkin_id=checkin_id,
            )
            effects.append(_effect_payload(row))
    # obstacles carry their own small, explicit deltas
    if channel == "day_end" and (answers or {}).get("obstacle"):
        deltas = {
            "sleep": -0.03,
            "phone": -0.02,
            "unclear": -0.01,
            "time": -0.02,
            "none": 0.0,
        }
        value = str(answers["obstacle"])
        row = _store_effect(
            db,
            user,
            channel=channel,
            code="obstacle_delta",
            day=anchor + _dt.timedelta(days=1),
            applied_to="capacity.tomorrow",
            delta_pct=deltas.get(value, 0.0),
            confidence=0.4,
            evidence_count=1,
            note=f"مانع امروز: {value} — پیشنهاد فردا کمی سبک‌تر می‌شود، نه حذف کار.",
        )
        effects.append(_effect_payload(row))
    if skipped:
        common.observe(
            db,
            user.id,
            f"questioning.{channel}.skipped",
            payload={"date": common.jdate(anchor)},
            source="self_report",
            day=anchor,
        )
    db.flush()
    return {
        "channel": channel,
        "date": common.jdate(anchor),
        "applied": len(effects),
        "effects": effects,
        "skipped": skipped,
        "note": "اثر پاسخ‌ها کوچک و باندشده است؛ پاسخ‌ها و اثرها جدا ذخیره می‌شوند (خام ≠ مشتق).",
    }


def _effect_payload(row: models.QuestionEffect) -> dict:
    return {
        "question_code": row.question_code,
        "channel": row.channel,
        "applied_to": row.applied_to,
        "delta_pct": row.delta_pct,
        "delta_label": f"{row.delta_pct * 100:+.1f}٪".replace("+", "+"),
        "confidence": row.confidence,
        "evidence_count": row.evidence_count,
        "date": common.jdate(row.day),
        "note": row.note,
    }


def capacity_adjustment(db: Session, user: models.User, day: _dt.date) -> dict:
    """Bounded factor applied to the *realistic* capacity of one day."""
    rows = db.scalars(
        select(models.QuestionEffect).where(
            models.QuestionEffect.user_id == user.id,
            models.QuestionEffect.day == day,
            models.QuestionEffect.applied_to == "capacity.today",
        )
    ).all()
    if not rows:
        return {
            "factor": 1.0,
            "delta_pct": 0.0,
            "reasons": [],
            "confidence": 0.0,
            "note": "پاسخ آغاز روزی برای این روز ثبت نشده؛ ظرفیت بدون اصلاح پرسش‌گری محاسبه شده است.",
        }
    limit = config.value("questioning.max_capacity_delta_pct")
    total = max(-limit, min(limit, sum(row.delta_pct for row in rows)))
    confidence = max((row.confidence for row in rows), default=0.0)
    return {
        "factor": round(1 + total, 4),
        "delta_pct": round(total, 4),
        "reasons": [_effect_payload(row) for row in rows],
        "confidence": round(confidence, 3),
        "limit_pct": limit,
        "note": "اثر تجمیعی پاسخ‌های امروز، باندشده روی ظرفیت واقع‌بینانه.",
    }


def tomorrow_adjustment(db: Session, user: models.User, day: _dt.date) -> dict:
    rows = db.scalars(
        select(models.QuestionEffect).where(
            models.QuestionEffect.user_id == user.id,
            models.QuestionEffect.day == day,
            models.QuestionEffect.applied_to == "capacity.tomorrow",
        )
    ).all()
    if not rows:
        return {"factor": 1.0, "delta_pct": 0.0, "reasons": [], "confidence": 0.0}
    limit = config.value("questioning.max_capacity_delta_pct")
    total = max(-limit, min(limit, sum(row.delta_pct for row in rows)))
    return {
        "factor": round(1 + total, 4),
        "delta_pct": round(total, 4),
        "reasons": [_effect_payload(row) for row in rows],
        "confidence": round(max(row.confidence for row in rows), 3),
        "limit_pct": limit,
        "note": "برآورد فردا از اجرا و موانع امروز — کوچک و قابل برگشت.",
    }


def combined_capacity_adjustment(db: Session, user: models.User, day: _dt.date) -> dict:
    """Both directions: today's own answers + yesterday's end-of-day answers."""
    today = capacity_adjustment(db, user, day)
    # end-of-day answers are stored against the day they should affect (i.e. tomorrow),
    # so the same query answers «what did yesterday's report change for today?»
    yesterday = tomorrow_adjustment(db, user, day)
    reasons = list(today.get("reasons") or []) + list(yesterday.get("reasons") or [])
    limit = config.value("questioning.max_capacity_delta_pct")
    total = max(-limit, min(limit, today["delta_pct"] + yesterday["delta_pct"]))
    return {
        "factor": round(1 + total, 4),
        "delta_pct": round(total, 4),
        "reasons": reasons,
        "confidence": round(max(today.get("confidence", 0.0), yesterday.get("confidence", 0.0)), 3),
        "limit_pct": limit,
        "sources": {"today_report": today["delta_pct"], "yesterday_report": yesterday["delta_pct"]},
        "note": "ظرفیت این روز فقط با گزارش‌های خود کاربر و در بازهٔ کوچک اصلاح می‌شود.",
    }


# ---------------------------------------------------------------------------
# Weekly answers → planner weights (small, bounded, explained)
# ---------------------------------------------------------------------------


def weight_multipliers(db: Session, user: models.User, *, day: Optional[_dt.date] = None) -> dict:
    anchor = day or today_local()
    week_start = anchor - _dt.timedelta(days=(anchor.weekday() - 5) % 7)
    rows = db.scalars(
        select(models.QuestionEffect).where(
            models.QuestionEffect.user_id == user.id,
            models.QuestionEffect.channel == "weekly",
            models.QuestionEffect.day >= week_start,
            models.QuestionEffect.day <= week_start + _dt.timedelta(days=6),
        )
    ).all()
    limit = config.value("questioning.max_weight_delta_pct")
    grouped: dict[str, float] = {}
    for row in rows:
        weight = (row.applied_to or "").split("@")[0]
        if not weight.startswith("priority.weight."):
            continue
        grouped[weight] = grouped.get(weight, 0.0) + row.delta_pct
    result = {}
    for weight, total in grouped.items():
        bounded = max(-limit, min(limit, total))
        result[weight] = {
            "multiplier": round(1 + bounded, 4),
            "delta_pct": round(bounded, 4),
            "note": "از پاسخ‌های هفتگی؛ کوچک و باندشده.",
        }
    return result


def planner_weight_report(db: Session, user: models.User, *, day: Optional[_dt.date] = None) -> dict:
    multipliers = weight_multipliers(db, user, day=day)
    return {
        "weights": multipliers,
        "count": len(multipliers),
        "limit_pct": config.value("questioning.max_weight_delta_pct"),
        "note": "پاسخ‌های هفتگی فقط وزن هدف/مرور را کمی جابه‌جا می‌کنند؛ هیچ وزنی صفر نمی‌شود.",
    }


# ---------------------------------------------------------------------------
# Personality → ordering only (never a lock)
# ---------------------------------------------------------------------------


PREFERENCE_RULES = (
    # dimension, direction, ordering key, threshold key
    ("routine_preference", "high", "stability", "questioning.trait_high_threshold"),
    ("novelty_preference", "high", "variety", "questioning.trait_high_threshold"),
    ("discipline", "high", "hard_first", "questioning.trait_high_threshold"),
    ("stress_tolerance", "low", "easy_first", "questioning.trait_low_threshold"),
)

PREFERENCE_LABELS_FA = {
    "stability": "ترتیب پایدار بین روزها",
    "variety": "تنوع بین کارها",
    "hard_first": "سخت‌تر اول",
    "easy_first": "سبک‌تر اول",
}


def ordering_bias(db: Session, user: models.User) -> dict:
    """Personality is *only* allowed to re-order near-equal suggestions, and only
    once the evidence threshold is met (V3.1 doc 07: «فقط با evidence کافی»)."""
    profile = db.scalars(select(models.UserProfile).where(models.UserProfile.user_id == user.id)).first()
    threshold = config.value("questioning.min_personality_evidence")
    high = config.value("questioning.trait_high_threshold")
    low = config.value("questioning.trait_low_threshold")
    if profile is None:
        return {
            "available": False,
            "hints": [],
            "keys": [],
            "threshold": threshold,
            "reason": "هنوز پروفایلی ساخته نشده؛ ترتیب پیش‌فرض می‌ماند.",
        }
    hints = []
    for dimension, direction, key, threshold_key in PREFERENCE_RULES:
        entry = (profile.personality or {}).get(dimension)
        if not isinstance(entry, dict):
            continue
        evidence = int(entry.get("evidence_count") or 0)
        confidence = float(entry.get("confidence") or 0.0)
        value = common.to_float(entry.get("value"))
        if value is None or evidence < threshold or confidence < config.value("questioning.min_personality_confidence"):
            continue
        boundary = high if direction == "high" else low
        if (direction == "high" and value < boundary) or (direction == "low" and value > boundary):
            continue
        hints.append(
            {
                "key": key,
                "label": PREFERENCE_LABELS_FA[key],
                "dimension": dimension,
                "value": round(value, 3),
                "evidence_count": evidence,
                "confidence": round(confidence, 3),
                "effect": "ordering_only",
                "note": "فقط ترتیب پیشنهادهای هم‌امتیاز را عوض می‌کند؛ نه قفل، نه حذف.",
            }
        )
    return {
        "available": bool(hints),
        "hints": hints,
        "keys": [hint["key"] for hint in hints],
        "threshold": threshold,
        "reason": (
            "شواهد کافی است؛ ترتیب پیشنهادهای هم‌امتیاز می‌تواند با ترجیح ثبت‌شدهٔ تو هم‌راستا شود."
            if hints
            else "شواهد کافی (یا جهت روشن) برای اثرگذاری روی ترتیب نیست؛ ترتیب پیش‌فرض می‌ماند."
        ),
    }


HEAVY_INTERVENTIONS = {
    "DIFFICULT_PRACTICE",
    "ERROR_REVIEW",
    "PREREQUISITE_REVIEW",
    "TIMED_QUIZ",
    "MOCK_EXAM",
}
LIGHT_INTERVENTIONS = {"READ_LESSON", "REVIEW", "EASY_PRACTICE", "ACTIVE_RECALL"}


def _ordering_rank(key: str, candidate: dict, index: int) -> tuple:
    intervention = candidate.get("intervention_type") or ""
    if key == "hard_first":
        return (0 if intervention in HEAVY_INTERVENTIONS else 1, index)
    if key == "easy_first":
        return (0 if intervention in LIGHT_INTERVENTIONS else 1, index)
    if key == "variety":
        return (index % 2, index)
    return (index, index)


def order_candidates(db: Session, user: models.User, candidates: list[dict]) -> tuple[list[dict], Optional[str]]:
    """Re-order only inside near-equal priority bands; a real score gap is never overridden."""
    bias = ordering_bias(db, user)
    if not bias["available"] or len(candidates) < 2:
        return candidates, None
    epsilon = config.value("questioning.ordering_tie_epsilon")
    if not epsilon or epsilon <= 0:
        return candidates, None
    # the engine hands candidates in score order, but this function must not depend on it
    candidates = sorted(candidates, key=lambda item: float(item.get("priority_score") or 0.0), reverse=True)
    bands: list[list[tuple[int, dict]]] = []
    for index, candidate in enumerate(candidates):
        score = float(candidate.get("priority_score") or 0.0)
        if bands and abs(score - float(bands[-1][-1][1].get("priority_score") or 0.0)) < epsilon:
            bands[-1].append((index, candidate))
        else:
            bands.append([(index, candidate)])
    keys = bias["keys"]
    if not keys:
        return candidates, None
    ordered: list[dict] = []
    changed = False
    primary = keys[0]
    for band in bands:
        if len(band) < 2:
            ordered.extend(candidate for _, candidate in band)
            continue
        ranked = sorted(band, key=lambda pair: _ordering_rank(primary, pair[1], pair[0]))
        reordered = [candidate for _, candidate in ranked]
        if reordered != [candidate for _, candidate in band]:
            changed = True
        ordered.extend(reordered)
    note = (
        f"ترتیب {len([b for b in bands if len(b) > 1])} گروه هم‌امتیاز با ترجیح «{PREFERENCE_LABELS_FA[primary]}» تنظیم شد."
        if changed
        else None
    )
    return ordered, note


# ---------------------------------------------------------------------------
# Transparency surface
# ---------------------------------------------------------------------------


def daily_summary(db: Session, user: models.User, *, day: Optional[_dt.date] = None) -> dict:
    anchor = day or today_local()
    start = channel_payload(db, user, "day_start", day=anchor)
    end = channel_payload(db, user, "day_end", day=anchor)
    return {
        "date": common.jdate(anchor),
        "date_long": common.jdate_long(anchor),
        "channels": {"day_start": start, "day_end": end},
        "capacity_effect": combined_capacity_adjustment(db, user, anchor),
        "rules": {
            "max_per_answer": config.value("questioning.max_answer_delta_pct"),
            "max_capacity_total": config.value("questioning.max_capacity_delta_pct"),
            "max_weight_total": config.value("questioning.max_weight_delta_pct"),
            "note": "هیچ پاسخ واحدی پارامتری را جهشی عوض نمی‌کند؛ سقف‌ها در تنظیمات قابل تغییرند.",
        },
        "skippable": True,
    }


def payload(db: Session, user: models.User) -> dict:
    channels = []
    for code, spec in CHANNELS.items():
        channels.append(
            {
                "code": code,
                "label": spec["label"],
                "min_questions": spec["min_questions"],
                "max_questions": spec["max_questions"],
                "connector": spec["connector"],
                "connector_fa": spec["connector_fa"],
            }
        )
    return {
        "channels": channels,
        "questions": [
            {
                "code": code,
                "channel": next((c for c, codes in CHANNEL_BANK.items() if code in codes), "onboarding"),
                "text": item["text"],
                "kind": item["kind"],
                "axis": item["axis"],
                "because": item["because"],
                "effect": item["effect"],
                "core": item.get("core", False),
            }
            for code, item in BANK.items()
        ],
        "ordering": ordering_bias(db, user),
        "note": "هر سؤال یک محور عدم‌قطعیت و یک اثر کوچک و توضیح‌پذیر دارد؛ همه قابل رد کردن‌اند.",
    }
