"""Behavioural intelligence: adaptive onboarding, current state, patterns.

Rules implemented:

* observed behaviour and self-report are stored **separately** and only then combined;
* one answer never jumps a personality dimension (multi-facet, small deltas);
* a dimension only enters planning above a confidence threshold;
* short-term state is not personality: no permanent labels, no medical claims;
* behavioural raw data is append-only; features are rebuildable.
"""

from __future__ import annotations

import datetime as _dt
import statistics
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import clamp, now_utc, safe_div, today_local
from ..db import models
from . import common

MODEL_VERSION = config.MODEL_VERSION

DIMENSIONS = config.value("behavior.personality_dimensions")
STATE_DIMENSIONS = config.value("behavior.state_dimensions")

DIMENSION_LABELS_FA = {
    "discipline": "نظم و پیوستگی",
    "planning_preference": "ترجیح برنامه‌ریزی",
    "procrastination": "ریسک عقب‌انداختن",
    "competition": "رقابت‌جویی",
    "reward_sensitivity": "حساسیت به پاداش",
    "stress_tolerance": "تحمل فشار",
    "routine_preference": "ترجیح روتین",
    "novelty_preference": "تنوع‌خواهی",
    "self_criticism": "سخت‌گیری با خود",
    "goal_orientation": "هدف‌گرایی",
    "energy_baseline": "انرژی پایه",
    "self_awareness": "خودآگاهی",
}

STATE_LABELS_FA = {
    "energy": "انرژی",
    "focus": "تمرکز",
    "motivation": "انگیزه",
    "stress": "استرس",
    "fatigue": "خستگی",
    "readiness": "آمادگی",
}


# ---------------------------------------------------------------------------
# Profile / personality
# ---------------------------------------------------------------------------


def profile_payload(db: Session, user: models.User) -> dict:
    profile = db.scalars(select(models.UserProfile).where(models.UserProfile.user_id == user.id)).first()
    if profile is None:
        profile = models.UserProfile(user_id=user.id, personality={}, preferences={}, self_reported={})
        db.add(profile)
        db.flush()
    personality = profile.personality or {}
    return {
        "personality": [
            {
                "key": key,
                "label": DIMENSION_LABELS_FA.get(key, key),
                "value": (personality.get(key) or {}).get("value"),
                "confidence": (personality.get(key) or {}).get("confidence", 0.0),
                "confidence_band": common.confidence_band((personality.get(key) or {}).get("confidence")),
                "evidence_count": (personality.get(key) or {}).get("evidence_count", 0),
                "enters_planning": ((personality.get(key) or {}).get("confidence") or 0)
                >= config.value("behavior.personality_confident_threshold"),
                "last_updated": (personality.get(key) or {}).get("last_updated"),
            }
            for key in DIMENSIONS
        ],
        "preferences": profile.preferences or {},
        "self_reported": profile.self_reported or {},
        "observed_summary": observed_features(db, user),
        "separated": {
            "note": "خودگزارشی و رفتار مشاهده‌شده جدا ذخیره می‌شوند و هرگز یکی جای دیگری را نمی‌گیرد.",
            "self_reported_example": (profile.self_reported or {}).get("preferred_study_time"),
            "observed_example": (observed_features(db, user) or {}).get("effective_start_hour"),
        },
        "model_version": profile.model_version,
    }


def apply_answer_effects(db: Session, user: models.User, question: models.OnboardingQuestion, answer: dict) -> dict:
    """Multi-facet update with small deltas and confidence growth only by evidence."""
    profile = db.scalars(select(models.UserProfile).where(models.UserProfile.user_id == user.id)).first()
    if profile is None:
        profile = models.UserProfile(user_id=user.id, personality={}, preferences={}, self_reported={})
        db.add(profile)
        db.flush()
    option_id = str(answer.get("option") or answer.get("value") or "")
    effects = {}
    if question.kind == "single_choice":
        effects = (question.effects or {}).get(option_id, {})
    elif question.kind == "short_text":
        # free text is stored as self-report, never converted into a numeric trait
        profile.self_reported = {
            **(profile.self_reported or {}),
            question.code: {"text": answer.get("text"), "at": common.jdatetime(now_utc())},
        }
    max_delta = config.value("behavior.personality_max_delta_per_answer")
    personality = dict(profile.personality or {})
    deltas = {}
    for dimension, delta in effects.items():
        bounded = max(-max_delta, min(max_delta, float(delta)))
        current = personality.get(dimension) or {"value": 0.5, "confidence": 0.0, "evidence_count": 0}
        new_value = clamp((current.get("value") if current.get("value") is not None else 0.5) + bounded)
        evidence = int(current.get("evidence_count") or 0) + 1
        personality[dimension] = {
            "value": round(new_value, 4),
            "confidence": round(common.confidence_from_evidence(evidence), 3),
            "evidence_count": evidence,
            "last_updated": common.jdatetime(now_utc()),
            "last_delta": round(bounded, 4),
            "source": "questionnaire",
        }
        deltas[dimension] = round(bounded, 4)
    profile.personality = personality
    profile.version = (profile.version or 1) + 1
    db.flush()
    db.add(
        models.OnboardingAnswer(
            user_id=user.id, question_code=question.code, answer=answer, dimension_deltas=deltas, answered_at=now_utc()
        )
    )
    state = db.scalars(select(models.OnboardingState).where(models.OnboardingState.user_id == user.id)).first()
    if state:
        asked = list(state.asked_codes or [])
        if question.code not in asked:
            asked.append(question.code)
        state.asked_codes = asked
        state.uncertainty = dimension_uncertainty(personality)
    db.flush()
    common.observe(
        db, user.id, "onboarding_answered",
        payload={"code": question.code, "option": option_id, "deltas": deltas}, source="self_report",
    )
    return {"deltas": deltas, "personality": personality, "note": "هر پاسخ فقط جهش کوچک می‌دهد؛ یک پاسخ یک ویژگی را قطعی نمی‌کند."}


def dimension_uncertainty(personality: dict) -> dict:
    return {
        key: round(1 - ((personality.get(key) or {}).get("confidence") or 0.0), 3)
        for key in DIMENSIONS
    }


def next_onboarding_question(db: Session, user: models.User) -> Optional[dict]:
    """Choose the most informative next question (uncertainty driven, stoppable)."""
    state = db.scalars(select(models.OnboardingState).where(models.OnboardingState.user_id == user.id)).first()
    if state is None:
        state = models.OnboardingState(user_id=user.id, asked_codes=[], skipped_codes=[], uncertainty={})
        db.add(state)
        db.flush()
    asked = set(state.asked_codes or []) | set(state.skipped_codes or [])
    questions = list(db.scalars(select(models.OnboardingQuestion).where(models.OnboardingQuestion.active.is_(True))))
    profile = db.scalars(select(models.UserProfile).where(models.UserProfile.user_id == user.id)).first()
    personality = (profile.personality if profile else {}) or {}
    remaining = [question for question in questions if question.code not in asked]
    if not remaining:
        state.completed = True
        db.flush()
        return None
    uncertainty = dimension_uncertainty(personality)
    max_questions = config.value("onboarding.max_questions_per_session")
    if len(asked) >= max_questions and len(asked) < config.value("onboarding.target_questions"):
        # one session is enough at a time: pause and let the user resume later
        return None

    def information_value(question: models.OnboardingQuestion) -> float:
        if question.kind == "short_text":
            return 0.3
        touched = {dimension for effect in (question.effects or {}).values() for dimension in effect}
        touched |= {dimension for effect in [question.effects.get(str(option), {}) for option in range(4)] for dimension in effect}
        if not touched:
            return 0.25
        return statistics.fmean([uncertainty.get(dimension, 1.0) for dimension in touched])

    scored = sorted(remaining, key=information_value, reverse=True)
    best = scored[0]
    value = information_value(best)
    return {
        "id": best.id,
        "code": best.code,
        "group": best.group,
        "text": best.text,
        "kind": best.kind,
        "options": best.options or [],
        "information_value": round(value, 3),
        "because": "این سؤال بیشترین کاهش عدم‌قطعیت را در مدل فعلی دارد.",
        "asked_count": len(asked),
        "remaining": len(remaining),
        "stoppable": True,
        "note": "پرسشنامه اجباری نیست؛ هر وقت خواستی متوقف یا ادامه بده.",
        "should_stop": value < config.value("onboarding.uncertainty_stop_threshold"),
    }


def answer_onboarding(db: Session, user: models.User, code: str, answer: dict, *, skip: bool = False) -> dict:
    from ..core.errors import NotFoundError

    question = db.scalars(select(models.OnboardingQuestion).where(models.OnboardingQuestion.code == code)).first()
    if not question:
        raise NotFoundError("سؤال پیدا نشد.")
    state = db.scalars(select(models.OnboardingState).where(models.OnboardingState.user_id == user.id)).first()
    if state is None:
        state = models.OnboardingState(user_id=user.id, asked_codes=[], skipped_codes=[], uncertainty={})
        db.add(state)
        db.flush()
    if skip:
        skipped = list(state.skipped_codes or [])
        if code not in skipped:
            skipped.append(code)
        state.skipped_codes = skipped
        db.flush()
        common.observe(db, user.id, "onboarding_skipped", payload={"code": code}, source="self_report")
        return {"skipped": True, "code": code}
    result = apply_answer_effects(db, user, question, answer)
    return {"skipped": False, "code": code, **result, "next": next_onboarding_question(db, user)}


def complete_onboarding(db: Session, user: models.User) -> dict:
    user.onboarding_completed = True
    state = db.scalars(select(models.OnboardingState).where(models.OnboardingState.user_id == user.id)).first()
    if state:
        state.completed = True
    db.flush()
    return {"completed": True}


# ---------------------------------------------------------------------------
# Current state (check-ins) and observed behaviour
# ---------------------------------------------------------------------------


def check_in(
    db: Session,
    user: models.User,
    answers: dict,
    *,
    phase: str = "start",
    day: Optional[_dt.date] = None,
) -> models.UserState:
    """2-5 short questions at the start/end of the day feed the state engine."""
    day = day or today_local()
    row = db.scalars(
        select(models.DailyCheckin).where(
            models.DailyCheckin.user_id == user.id, models.DailyCheckin.day == day, models.DailyCheckin.phase == phase
        )
    ).first()
    if row is None:
        row = models.DailyCheckin(user_id=user.id, day=day, phase=phase, answers=answers)
        db.add(row)
    else:
        row.answers = answers
    values = {}
    confidence = {}
    for key in STATE_DIMENSIONS:
        raw = answers.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            raw = common.to_float(common.normalize_digits(raw))
        if raw is None:
            continue
        value = float(raw)
        if value > 1:  # a 1..5 scale is normalised, never guessed
            value = value / 5.0
        values[key] = clamp(value)
        confidence[key] = 0.9  # a direct self-report is high confidence about *now*
    observed = observed_features(db, user)
    if "energy" not in values and observed.get("energy_proxy") is not None:
        values["energy"] = observed["energy_proxy"]
        confidence["energy"] = 0.35
        confidence["energy_source"] = "inferred_from_behaviour"
    state = models.UserState(
        user_id=user.id,
        day=day,
        energy=values.get("energy"),
        focus=values.get("focus"),
        motivation=values.get("motivation"),
        stress=values.get("stress"),
        fatigue=values.get("fatigue"),
        readiness=values.get("readiness"),
        confidence=confidence,
        source="checkin",
        evidence={"answers": answers, "phase": phase, "observed": observed},
    )
    db.add(state)
    profile = db.scalars(select(models.UserProfile).where(models.UserProfile.user_id == user.id)).first()
    if profile:
        profile.self_reported = {
            **(profile.self_reported or {}),
            f"{phase}_checkin": {"answers": answers, "at": common.jdatetime(now_utc())},
        }
    db.flush()
    return state


def current_state(db: Session, user: models.User) -> dict:
    state = db.scalars(
        select(models.UserState).where(models.UserState.user_id == user.id).order_by(models.UserState.captured_at.desc())
    ).first()
    observed = observed_features(db, user)
    if state is None:
        return {
            "available": False,
            "dimensions": [],
            "observed": observed,
            "message": "امروز ثبت وضعیتی انجام نشده؛ می‌توانی یک چک‌این کوتاه انجام بدهی.",
            "note": "وضعیت لحظه‌ای با «شخصیت» متفاوت است و جدا ذخیره می‌شود.",
        }
    return {
        "available": True,
        "captured_at": common.jdatetime(state.captured_at),
        "source": state.source,
        "dimensions": [
            {
                "key": key,
                "label": STATE_LABELS_FA.get(key, key),
                "value": getattr(state, key),
                "confidence": (state.confidence or {}).get(key),
            }
            for key in STATE_DIMENSIONS
        ],
        "observed": observed,
        "note": "وضعیت لحظه‌ای است، نه برچسب شخصیتی.",
    }


def observed_features(db: Session, user: models.User) -> dict:
    """Features computed from real behaviour only (rebuildable, no fusion with self-report)."""
    executions = list(
        db.scalars(
            select(models.TaskExecution).where(
                models.TaskExecution.user_id == user.id, models.TaskExecution.outcome == "completed"
            )
        )
    )
    tasks = list(db.scalars(select(models.StudyTask).where(models.StudyTask.user_id == user.id)))
    planned = len(tasks)
    completed = len([task for task in tasks if task.status == "completed"])
    skipped = len([task for task in tasks if task.status == "skipped"])
    edited = len([task for task in tasks if task.manual_override])
    start_hours = [execution.started_at.hour for execution in executions if execution.started_at]
    durations = [execution.actual_minutes for execution in executions if execution.actual_minutes]
    hard_skipped = [
        task for task in tasks
        if task.status == "skipped" and (task.planned_minutes or 0) >= config.value("behavior.long_task_split_minutes")
    ]
    late_start_rate = safe_div(len([hour for hour in start_hours if hour >= 18]), len(start_hours)) if start_hours else None
    return {
        "task_completion_rate": round(safe_div(completed, planned), 3) if planned else None,
        "skip_rate": round(safe_div(skipped, planned), 3) if planned else None,
        "edit_rate": round(safe_div(edited, planned), 3) if planned else None,
        "average_session_minutes": round(statistics.fmean(durations), 1) if durations else None,
        "effective_start_hour": round(statistics.median(start_hours), 1) if start_hours else None,
        "late_start_rate": round(late_start_rate, 3) if late_start_rate is not None else None,
        "hard_task_skip_rate": round(safe_div(len(hard_skipped), planned), 3) if planned else None,
        "energy_proxy": _energy_proxy(db, user),
        "evidence_counts": {
            "executions": len(executions),
            "tasks": planned,
            "tasks_with_start_time": len(start_hours),
        },
        "note": "رفتار مشاهده‌شده فقط از داده واقعی ساخته می‌شود؛ خودگزارشی جای آن نمی‌نشیند.",
    }


def _energy_proxy(db: Session, user: models.User) -> Optional[float]:
    """Coarse proxy: how much of the planned work actually happened recently."""
    since = today_local() - _dt.timedelta(days=7)
    rows = list(
        db.scalars(
            select(models.StudyTask).where(
                models.StudyTask.user_id == user.id, models.StudyTask.planned_date >= since
            )
        )
    )
    if not rows:
        return None
    completed = len([task for task in rows if task.status == "completed"])
    return round(clamp(safe_div(completed, len(rows)) or 0.0), 3)


def detect_patterns(db: Session, user: models.User) -> list[models.BehaviorPattern]:
    """Procrastination style patterns — computed with enough evidence, never as a label."""
    min_evidence = config.value("behavior.pattern_min_evidence")
    features = observed_features(db, user)
    counts = features["evidence_counts"]
    results: list[dict] = []
    if counts["tasks"] >= min_evidence:
        hard_skip = features.get("hard_task_skip_rate") or 0.0
        completion = features.get("task_completion_rate") or 0.0
        if hard_skip >= 0.25:
            results.append(
                {
                    "code": "hard_task_avoidance",
                    "description": "کارهای بلند/سخت بیشتر از بقیه عقب می‌افتند.",
                    "strength": round(hard_skip, 3),
                    "suggestion": "کارهای بلندتر از ۷۵ دقیقه را به قطعه‌های کوچک بشکن؛ شروع با ۵ تست آسان یک نقطه ورود خوب است.",
                    "evidence": {"hard_task_skip_rate": hard_skip, "tasks": counts["tasks"]},
                }
            )
        if completion <= 0.5 and counts["tasks"] >= min_evidence:
            results.append(
                {
                    "code": "over_planning",
                    "description": "بار برنامه بیشتر از ظرفیت واقعی است.",
                    "strength": round(1 - completion, 3),
                    "suggestion": "تعداد کار روزانه کاهش پیدا کند؛ ظرفیت به‌صورت تدریجی بازمحاسبه می‌شود.",
                    "evidence": {"completion_rate": completion, "tasks": counts["tasks"]},
                }
            )
        late = features.get("late_start_rate")
        if late is not None and late >= 0.6 and counts["tasks_with_start_time"] >= min_evidence:
            results.append(
                {
                    "code": "late_start",
                    "description": "شروع کارها معمولاً دیرتر از برنامه اتفاق می‌افتد.",
                    "strength": round(late, 3),
                    "suggestion": "یک کار کوتاه ۱۰ دقیقه‌ای در ابتدای وعده بگذار تا شروع آسان‌تر شود.",
                    "evidence": {"late_start_rate": late, "effective_start_hour": features.get("effective_start_hour")},
                }
            )
        if (features.get("edit_rate") or 0) >= 0.4:
            results.append(
                {
                    "code": "plan_fit_mismatch",
                    "description": "کارهای پیشنهادی زیاد دستی تغییر داده می‌شوند؛ یعنی پیشنهاد با ترجیح واقعی هم‌خوان نیست.",
                    "strength": round(features["edit_rate"], 3),
                    "suggestion": "سبک برنامه‌ریزی (تعداد کار در برابر ساعت دقیق) در مصاحبه هفتگی بازبینی شود.",
                    "evidence": {"edit_rate": features["edit_rate"]},
                }
            )
    stored = {
        row.pattern_code: row
        for row in db.scalars(select(models.BehaviorPattern).where(models.BehaviorPattern.user_id == user.id))
    }
    output: list[models.BehaviorPattern] = []
    for item in results:
        row = stored.get(item["code"])
        if row is None:
            row = models.BehaviorPattern(user_id=user.id, pattern_code=item["code"], first_seen=today_local())
            db.add(row)
        row.description = item["description"]
        row.strength = item["strength"]
        row.evidence_count = counts["tasks"]
        row.confidence = common.confidence_from_evidence(counts["tasks"])
        row.last_seen = today_local()
        row.evidence = item["evidence"]
        row.suggestion = item["suggestion"]
        output.append(row)
    db.flush()
    return output


def behaviour_summary(db: Session, user: models.User) -> dict:
    patterns = detect_patterns(db, user)
    return {
        "features": observed_features(db, user),
        "patterns": [
            {
                "code": pattern.pattern_code,
                "description": pattern.description,
                "strength": pattern.strength,
                "confidence": pattern.confidence,
                "evidence_count": pattern.evidence_count,
                "suggestion": pattern.suggestion,
                "evidence": pattern.evidence,
                "dismissed_until": common.jdatetime(pattern.dismissed_until),
                "disclaimer": "این‌ها الگوهای آماری برای تنظیم برنامه‌اند، نه تشخیص روان‌شناختی.",
            }
            for pattern in patterns
        ],
        "raw_events": db.scalar(
            select(func.count(models.BehaviorObservation.id)).where(models.BehaviorObservation.user_id == user.id)
        ) or 0,
        "observed_vs_self_report": {
            "observed": observed_features(db, user),
            "self_reported": (db.scalars(select(models.UserProfile).where(models.UserProfile.user_id == user.id)).first().self_reported or {}),
            "policy": "اگر خودگزارشی با رفتار واقعی اختلاف داشت، هر دو نگه داشته می‌شوند و با اطمینان نتیجه‌گیری می‌شود.",
        },
    }


def dismiss_pattern(db: Session, user: models.User, pattern_code: str, hours: int = 72) -> dict:
    from ..core.errors import NotFoundError

    row = db.scalars(
        select(models.BehaviorPattern).where(
            models.BehaviorPattern.user_id == user.id, models.BehaviorPattern.pattern_code == pattern_code
        )
    ).first()
    if not row:
        raise NotFoundError("الگو پیدا نشد.")
    row.dismissed_until = now_utc() + _dt.timedelta(hours=hours)
    db.flush()
    return {"pattern_code": pattern_code, "dismissed_until": common.jdatetime(row.dismissed_until)}


# ---------------------------------------------------------------------------
# Daily / weekly check-in questionnaires (V2.2)
# ---------------------------------------------------------------------------

START_DAY_QUESTIONS = [
    {"code": "energy", "text": "انرژی امروزت چطور است؟", "kind": "scale", "min": 1, "max": 5},
    {"code": "sleep", "text": "خوابت چطور بود؟", "kind": "scale", "min": 1, "max": 5},
    {"code": "free_time", "text": "امروز چقدر وقت آزاد واقعی داری؟", "kind": "scale", "min": 1, "max": 5},
    {"code": "mental_priority", "text": "ذهنت درگیر چه چیزی است؟", "kind": "short_text"},
    {"code": "exam_stress", "text": "استرس امتحان امروز چقدر است؟", "kind": "scale", "min": 1, "max": 5},
]

END_DAY_QUESTIONS = [
    {"code": "plan_followed", "text": "چقدر طبق برنامه پیش رفتی؟", "kind": "scale", "min": 1, "max": 5},
    {"code": "main_distraction", "text": "بزرگ‌ترین عامل حواس‌پرتی امروز چه بود؟", "kind": "short_text"},
    {"code": "satisfaction", "text": "از امروز چقدر راضی هستی؟", "kind": "scale", "min": 1, "max": 5},
    {"code": "tomorrow_focus", "text": "فردا روی چه چیزی تمرکز کنی؟", "kind": "short_text"},
]

WEEKLY_REFLECTION_QUESTIONS = [
    {"code": "hardest_topic", "text": "سخت‌ترین مبحث این هفته چه بود؟", "kind": "short_text"},
    {"code": "best_habit", "text": "کدام عادت خوب جواب داد؟", "kind": "short_text"},
    {"code": "drop_or_add", "text": "چه چیزی را حذف یا اضافه کنیم؟", "kind": "short_text"},
    {"code": "week_load", "text": "بار این هفته چطور بود؟", "kind": "single_choice",
     "options": [{"id": "light", "label": "سبک"}, {"id": "right", "label": "مناسب"}, {"id": "heavy", "label": "سنگین"}]},
]


def daily_questionnaire(phase: str = "start", *, db=None, user=None) -> list[dict]:
    """V3.1 doc 07: 2–4 purposeful questions per day, not a fixed form.

    The adaptive list needs the student's evidence, so callers that have a session
    pass it in; without a session the previous fixed list stays as a safe fallback.
    """
    if db is not None and user is not None:
        from . import questioning

        channel = "day_start" if phase == "start" else "day_end"
        return questioning.questions_for(db, user, channel)
    return START_DAY_QUESTIONS if phase == "start" else END_DAY_QUESTIONS


def save_daily_checkin(db: Session, user: models.User, phase: str, answers: dict, *, skipped: bool = False) -> dict:
    day = today_local()
    row = db.scalars(
        select(models.DailyCheckin).where(
            models.DailyCheckin.user_id == user.id, models.DailyCheckin.day == day, models.DailyCheckin.phase == phase
        )
    ).first()
    if row is None:
        row = models.DailyCheckin(user_id=user.id, day=day, phase=phase, answers=answers, skipped=skipped)
        db.add(row)
    else:
        row.answers = answers
        row.skipped = skipped
    db.flush()
    # end-of-day answers become behaviour observations (self report channel)
    for key, value in (answers or {}).items():
        common.observe(
            db, user.id, f"checkin.{phase}.{key}",
            payload={"value": value}, source="self_report", day=day,
        )
    # V3.1 doc 07: the same answers produce *small, bounded* effects on again derived
    # values (today's capacity / next day's estimate) and those effects are stored
    # separately from the raw answer.
    from . import questioning

    channel = "day_start" if phase == "start" else "day_end"
    effect_report = questioning.apply_answers(
        db, user, channel, (answers or {}) if not skipped else {}, day=day, checkin_id=row.id, skipped=skipped
    )
    if phase == "start" and not skipped:
        numeric = {
            key: common.to_float(common.normalize_digits(str(value))) if not isinstance(value, (int, float)) else float(value)
            for key, value in (answers or {}).items()
            if key in STATE_DIMENSIONS or key in {"sleep", "free_time", "exam_stress"}
        }
        check_in(db, user, numeric, phase="start", day=day)
    return {
        "phase": phase,
        "date": common.jdate(day),
        "skipped": skipped,
        "recorded": True,
        "effects": effect_report["effects"],
        "effects_note": effect_report["note"],
    }


def save_weekly_reflection(db: Session, user: models.User, answers: dict, *, skipped: bool = False, week_start_value=None) -> dict:
    start = week_start_value or today_local() - _dt.timedelta(days=(today_local().weekday() - 5) % 7)
    row = db.scalars(
        select(models.WeeklyReflection).where(
            models.WeeklyReflection.user_id == user.id, models.WeeklyReflection.week_start == start
        )
    ).first()
    if row is None:
        row = models.WeeklyReflection(user_id=user.id, week_start=start, answers=answers, skipped=skipped)
        db.add(row)
    else:
        row.answers = answers
        row.skipped = skipped
    db.flush()
    for key, value in (answers or {}).items():
        common.observe(db, user.id, f"reflection.{key}", payload={"value": value}, source="self_report")
    # V3.1 doc 07: closing the week nudges planner/goal weights a little (bounded).
    from . import questioning

    effect_report = questioning.apply_answers(
        db, user, "weekly", (answers or {}) if not skipped else {}, day=start, checkin_id=row.id, skipped=skipped
    )
    return {
        "week_start": common.jdate(start),
        "recorded": True,
        "skipped": skipped,
        "effects": effect_report["effects"],
        "effects_note": effect_report["note"],
    }
