"""موتور وضعیت فعلی — V2.1 (18_STATE_ENGINE_V2_1).

Stateهای energy/focus/motivation/stress/fatigue/readiness همه 0..1 + confidence.
State لحظه‌ای با Personality یکی نیست.
Self-report و رفتار اخیر جدا ذخیره و سپس با confidence ترکیب می‌شوند.
State Engine فقط توصیه را تغذیه می‌کند؛ مستقلاً Task نمی‌سازد.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jalali import today_tehran
from app.models import DailyTaskPlacement, Task, TestSession, User, UserStateSnapshot


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def observed_state(db: Session, user_id: int) -> dict:
    """وضعیت استنتاجی از رفتار اخیر (۷ روز اخیر) — جدا از self-report."""
    today = today_tehran()
    since = today - dt.timedelta(days=7)
    tasks = list(db.scalars(
        select(Task).join(DailyTaskPlacement, DailyTaskPlacement.task_id == Task.id)
        .where(DailyTaskPlacement.date >= since, DailyTaskPlacement.date <= today,
               Task.user_id == user_id, Task.status != "cancelled")))
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    completion_rate = (completed / total) if total else None

    # روند اخیر: روزهای اخیر چقدر فعال بوده
    active_days = db.scalar(
        select(func.count(func.distinct(DailyTaskPlacement.date)))
        .join(Task, Task.id == DailyTaskPlacement.task_id)
        .where(Task.user_id == user_id, Task.status == "completed",
               DailyTaskPlacement.date >= since)) or 0
    activity = active_days / 7.0

    # دقت اخیر
    from app.models import QuestionAttempt
    rows = db.execute(
        select(QuestionAttempt.result, func.count(QuestionAttempt.id))
        .where(QuestionAttempt.user_id == user_id,
               QuestionAttempt.answered_at >= dt.datetime.combine(since, dt.time.min))
        .group_by(QuestionAttempt.result)).all()
    res = {r: c for r, c in rows}
    answered = res.get("correct", 0) + res.get("wrong", 0)
    accuracy = (res.get("correct", 0) / answered) if answered else None

    return {
        "completion_rate_7d": completion_rate,
        "active_days_7d": active_days,
        "activity": round(activity, 3),
        "accuracy_7d": accuracy,
        "evidence_count": total,
    }


def check_in(db: Session, user: User, answers: dict) -> UserStateSnapshot:
    """ثبت self-report روزانه: انرژی/تمرکز/انگیزه/استرس/خستگی (۱..۵) + خواب."""
    def five(key) -> float:
        return _clamp01(((float(answers.get(key, 3))) - 1) / 4)

    energy = five("energy")
    focus = five("focus")
    motivation = five("motivation")
    stress = five("stress")
    fatigue = five("fatigue")
    sleep_hours = float(answers.get("sleep_hours", 7))
    # خواب کافی (۸ ساعت مرجع) انرژی را تعدیل می‌کند
    sleep_factor = _clamp01(sleep_hours / 8.0)

    readiness = _clamp01(
        0.3 * energy * (0.5 + 0.5 * sleep_factor)
        + 0.25 * focus
        + 0.25 * motivation
        + 0.2 * (1 - stress) * (1 - 0.5 * fatigue)
    )

    snap = UserStateSnapshot(
        user_id=user.id, captured_date=today_tehran(),
        energy=energy, focus=focus, motivation=motivation,
        stress=stress, fatigue=fatigue, readiness=readiness,
        source="self_report",
        confidence_json={
            "energy": 0.9, "focus": 0.9, "motivation": 0.9,
            "stress": 0.9, "fatigue": 0.9, "readiness": 0.85,
            "evidence_count": 1,
        },
    )
    db.add(snap)
    db.flush()

    # رویداد رفتاری self_report (جدا از observed)
    from app.domain.behavior import log_event
    log_event(db, user.id, "state_check_in", {
        "energy": energy, "focus": focus, "motivation": motivation,
        "stress": stress, "fatigue": fatigue, "sleep_hours": sleep_hours,
        "readiness": readiness,
    }, source="self_report")
    return snap


def current_state(db: Session, user: User) -> dict:
    """ترکیب آخرین self-report با رفتار مشاهده‌شده — با confidence."""
    snap = db.execute(
        select(UserStateSnapshot)
        .where(UserStateSnapshot.user_id == user.id)
        .order_by(UserStateSnapshot.captured_at.desc())
    ).scalars().first()

    observed = observed_state(db, user.id)

    state = {}
    confidence = {}
    for k in ("energy", "focus", "motivation", "stress", "fatigue", "readiness"):
        if snap is not None:
            state[k] = round(getattr(snap, k), 3)
            confidence[k] = 0.6 if snap.captured_date == today_tehran() else 0.3
        else:
            state[k] = 0.5
            confidence[k] = 0.1

    # ترکیب با رفتار مشاهده‌شده (رفتار خاموش‌تر اما مستقل است)
    if observed["completion_rate_7d"] is not None:
        cr = observed["completion_rate_7d"]
        # رفتار: انگیزه و آمادگی مشاهده‌شده
        obs_motivation = _clamp01(0.5 + (cr - 0.5) * 0.8)
        w = observed["evidence_count"] / max(observed["evidence_count"] + 10, 1)
        state["motivation"] = round(_clamp01(state["motivation"] * (1 - w) + obs_motivation * w), 3)
        state["readiness"] = round(_clamp01(state["readiness"] * (1 - w * 0.6) +
                                            (state["readiness"] * (1 - w) + obs_motivation * w) * w * 0.6), 3)
        confidence["motivation"] = round(min(0.95, confidence["motivation"] + 0.2 * w), 3)
        confidence["readiness"] = round(min(0.95, confidence["readiness"] + 0.15 * w), 3)

    return {
        "state": state,
        "confidence": confidence,
        "observed": observed,
        "last_check_in": snap.captured_at.isoformat() if snap else None,
        "last_check_in_date": snap.captured_date.isoformat() if snap else None,
        "note": "وضعیت لحظه‌ای است و با شخصیت یکی نیست؛ فقط توصیه را تغذیه می‌کند.",
    }
