"""موتور رفتار — V2.1 (17_BEHAVIOR_ENGINE_V2_1 و 19_CAPACITY_AND_PROCRASTINATION).

- behavior_events کاملاً append-only است؛ featureها قابل بازمحاسبه‌اند.
- Self-report و Observed Behavior جدا ذخیره و سپس با confidence ترکیب می‌شوند.
- Procrastination Pattern Detection: Hard Task → Delay → Late Start → Stress →
  Lower Completion. هیچ تشخیص پزشکی صادر نمی‌شود؛ فقط پیشنهاد عملی:
  split / entry point کوچک / تغییر ترتیب / شروع با ۵ تست.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.config as cfg
from app.jalali import today_tehran
from app.models import BehaviorEvent, Task, TestSession, User, UserProfile


def log_event(db: Session, user_id: int, event_type: str, payload: dict,
              source: str = "system", event_time: dt.datetime | None = None) -> None:
    """ثبت رویداد رفتاری — append-only."""
    t = event_time or dt.datetime.now(dt.timezone.utc)
    db.add(BehaviorEvent(
        user_id=user_id, event_type=event_type, event_time=t,
        event_date=t.date() if t.tzinfo is None else t.astimezone(
            dt.timezone(dt.timedelta(hours=3, minutes=30))).date(),
        payload_json=payload or {}, source=source,
    ))


def compute_features(db: Session, user_id: int, window: int = 30) -> dict:
    """Featureهای پیشنهادی سند 17 — از رویدادهای خام بازمحاسبه می‌شوند."""
    today = today_tehran()
    since = today - dt.timedelta(days=window)

    events = list(db.scalars(
        select(BehaviorEvent).where(
            BehaviorEvent.user_id == user_id,
            BehaviorEvent.event_date >= since,
        ).order_by(BehaviorEvent.event_time)))

    task_events = [e for e in events if e.event_type in
                   ("task_completed", "task_skipped", "task_edited", "task_rescheduled")]
    completed = [e for e in task_events if e.event_type == "task_completed"]
    skipped = [e for e in task_events if e.event_type == "task_skipped"]

    # نرخ تکمیل
    if task_events:
        completion_rate = len(completed) / max(len(completed) + len(skipped), 1)
    else:
        completion_rate = 0.0

    # میانگین مدت جلسات
    sessions = list(db.scalars(
        select(TestSession).where(
            TestSession.user_id == user_id,
            TestSession.status == "completed",
            TestSession.actual_duration_minutes.isnot(None),
            TestSession.ended_at >= dt.datetime.combine(since, dt.time.min),
        ))) if hasattr(TestSession, "ended_at") else []
    avg_session = (sum(s.actual_duration_minutes for s in sessions) / len(sessions)
                   if sessions else 0.0)

    # تمرکز صبح/عصر: سهم ساعات قبل/بعد ۱۴ از شروع جلسات
    starts = [e for e in events if e.event_type == "session_started"]
    morning = sum(1 for e in starts if (e.payload_json or {}).get("hour", 12) < 14)
    evening = len(starts) - morning
    total_starts = len(starts) or 1
    avg_focus_morning = round(morning / total_starts, 3)
    avg_focus_evening = round(evening / total_starts, 3)

    # نرخ شروع دیرهنگام: شروع Task بعد از ساعت ۲۰
    late_start_rate = (sum(1 for e in starts if (e.payload_json or {}).get("hour", 12) >= 20)
                       / total_starts)

    # نرخ رد کردن کار سخت: از payload (difficulty=hard)
    hard_skips = sum(1 for e in skipped if (e.payload_json or {}).get("difficulty") == "hard")
    hard_total = sum(1 for e in task_events
                     if (e.payload_json or {}).get("difficulty") == "hard") or 1
    hard_task_skip_rate = round(hard_skips / hard_total, 3)

    features = {
        "task_completion_rate": round(completion_rate, 3),
        "avg_focus_morning": avg_focus_morning,
        "avg_focus_evening": avg_focus_evening,
        "average_session_minutes": round(avg_session, 1),
        "late_start_rate": round(late_start_rate, 3),
        "hard_task_skip_rate": hard_task_skip_rate,
    }

    # ذخیره در پروفایل با confidence بر اساس تعداد مشاهده
    p = db.query(UserProfile).filter(UserProfile.user_id == user_id).one_or_none()
    if p is None:
        p = UserProfile(user_id=user_id)
        db.add(p)
        db.flush()
    bj = dict(p.behavior_json or {})
    for k, v in features.items():
        old = bj.get(k) or {}
        ev_count = old.get("evidence_count", 0) + 1
        bj[k] = {
            "value": v,
            "confidence": round(min(0.95, ev_count / cfg.EVIDENCE_CONFIDENCE_SATURATION), 3),
            "evidence_count": ev_count,
            "source": "observed",
            "last_updated": dt.datetime.utcnow().isoformat(),
        }
    p.behavior_json = bj
    return features


def behavior_summary(db: Session, user: User) -> dict:
    features = compute_features(db, user.id)
    bj = db.query(UserProfile).filter(UserProfile.user_id == user.id).one_or_none()
    behavior = (bj.behavior_json if bj else {}) or {}

    # --- تشخیص الگوی اهمال‌کاری (بدون تشخیص پزشکی) ---
    proc = procrastination_analysis(features, behavior)
    return {
        "features": features,
        "behavior_model": behavior,
        "procrastination": proc,
        "recent_events": [{
            "id": e.id, "type": e.event_type, "time": e.event_time.isoformat(),
            "payload": e.payload_json, "source": e.source,
        } for e in db.scalars(
            select(BehaviorEvent).where(BehaviorEvent.user_id == user.id)
            .order_by(BehaviorEvent.event_time.desc()).limit(30))],
    }


def procrastination_analysis(features: dict, behavior: dict) -> dict:
    """الگو: Hard Task → Delay → Late Start → Lower Completion."""
    late = features.get("late_start_rate", 0)
    hard_skip = features.get("hard_task_skip_rate", 0)
    completion = features.get("task_completion_rate", 0)

    signal = 0.0
    signal += 0.4 if late >= 0.5 else (0.2 if late >= 0.3 else 0.0)
    signal += 0.4 if hard_skip >= 0.5 else (0.2 if hard_skip >= 0.3 else 0.0)
    signal += 0.2 if completion < 0.4 else (0.1 if completion < 0.6 else 0.0)

    detected = signal >= 0.5
    # confidence از حجم شواهد رفتاری
    ev = min((behavior.get("hard_task_skip_rate") or {}).get("evidence_count", 0),
             (behavior.get("late_start_rate") or {}).get("evidence_count", 0))
    confidence = round(min(0.9, ev / 15), 3) if detected else 0.0

    suggestions = []
    if detected:
        suggestions = [
            "تسک سخت را به دو نیمهٔ کوچک‌تر split کن",
            "یک entry point کوچک بساز (فقط ۵ تست شروع)",
            "کار سخت را اول روز بگذار، نه آخر شب",
            "شروع با ۵ تست آسان از همان مبحث برای گرم شدن",
        ]

    return {
        "pattern_detected": detected,
        "signal_strength": round(signal, 2),
        "confidence": confidence,
        "evidence_count": ev,
        "message": (
            "الگوی «کار سخت → تأخیر → شروع دیرهنگام → افت تکمیل» در داده‌های اخیر دیده می‌شود. "
            "این یک مشاهدهٔ رفتاری است، نه قضاوت." if detected
            else "الگوی اهمال‌کاری واضحی در داده‌های اخیر دیده نمی‌شود (یا داده کافی نیست)."
        ),
        "suggestions": suggestions,
    }
