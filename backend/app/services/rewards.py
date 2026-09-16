"""سیستم سکه، Streak و نشان — سند 07_REWARDS_AND_COINS_V2 و 14_NUMERIC."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config as cfg
from .. import models as m

V22_BADGES = [
    ("bank_builder", "معمار بانک تست", "ثبت پاسخ‌نامه برای ۱۰۰ سوال", "answer_keys", 100),
    ("importer", "بایگان", "وارد کردن ۱۰۰ تست گذشته", "imported_attempts", 100),
    ("exam_tracker", "امتحان‌شناس", "ثبت ۳ نوبت امتحان با زمان", "exam_attempts", 3),
    ("ready", "آماده امتحان", "ساخت اولین آمادگی امتحان", "upcoming_exams", 1),
    ("taught_follower", "پیگیر کلاس", "ثبت ۱۰ مبحث تدریس‌شده", "taught_topics", 10),
]


def ensure_badges(db: Session) -> None:
    for code, title, desc, cond, val in V22_BADGES:
        if not db.scalar(select(m.Badge).where(m.Badge.code == code)):
            db.add(m.Badge(code=code, title=title, description=desc,
                           condition_type=cond, condition_value=val))
    db.flush()


def award(db: Session, user: m.User, event_type: str, points: int, description: str = "",
          entity_type: str | None = None, entity_id: int | None = None,
          event_date: date | None = None) -> int:
    if points == 0:
        return 0
    db.add(m.RewardEvent(
        user_id=user.id, event_type=event_type, points=points, description=description,
        related_entity_type=entity_type, related_entity_id=entity_id,
        event_date=event_date or date.today(),
    ))
    user.total_points += points
    return points


def record_wake_up(db: Session, user: m.User, when: datetime, day: date | None = None) -> dict:
    day = day or when.date()
    existing = db.scalar(
        select(m.WakeUpEvent).where(m.WakeUpEvent.user_id == user.id, m.WakeUpEvent.date == day)
    )
    if existing:
        return {"already": True, "points": existing.points_awarded,
                "time": existing.recorded_time,
                "message": "بیدار شدن امروز قبلاً ثبت شده است."}

    mins = when.hour * 60 + when.minute
    deadline = cfg.WAKE_UP_DEADLINE_HOUR * 60 + cfg.WAKE_UP_DEADLINE_MINUTE
    early = cfg.WAKE_UP_EARLY_HOUR * 60 + cfg.WAKE_UP_EARLY_MINUTE
    late_limit = cfg.WAKE_UP_LATE_LIMIT_HOUR * 60 + cfg.WAKE_UP_LATE_LIMIT_MINUTE

    points = 0
    if mins <= deadline:
        points = cfg.POINTS_WAKE_UP
        if mins < early:
            points += cfg.POINTS_WAKE_UP_EARLY_BONUS
    msg = (
        f"+{points} سکه بیدار شدن" if points
        else ("ثبت شد، اما بعد از ۰۷:۱۵ سکه تعلق نمی‌گیرد."
              if mins > late_limit else "ثبت شد؛ بعد از ۰۷:۰۰ سکه بیدار شدن ندارد.")
    )
    db.add(m.WakeUpEvent(user_id=user.id, date=day, recorded_at=when,
                         recorded_time=f"{when.hour:02d}:{when.minute:02d}",
                         points_awarded=points))
    award(db, user, "wake_up", points, "بیدار شدن زودهنگام", event_date=day)
    return {"already": False, "points": points,
            "time": f"{when.hour:02d}:{when.minute:02d}", "message": msg}


def touch_streak(db: Session, user: m.User, day: date | None = None) -> int:
    """یک روز با Task/جلسه کامل‌شده → streak +1؛ گپ → صفر."""
    day = day or date.today()
    if user.last_streak_date == day:
        return user.current_streak
    if user.last_streak_date == day - timedelta(days=1):
        user.current_streak += 1
    else:
        user.current_streak = 1
    user.last_streak_date = day
    user.longest_streak = max(user.longest_streak, user.current_streak)
    award(db, user, "streak_day", cfg.POINTS_STREAK_DAY,
          f"حفظ Streak روز {user.current_streak}", event_date=day)
    return user.current_streak


def check_badges(db: Session, user: m.User) -> list[str]:
    ensure_badges(db)
    earned: list[str] = []
    counts = {
        "answer_keys": db.scalar(select(func.count(m.Question.id)).where(
            m.Question.answer_key.isnot(None))) or 0,
        "imported_attempts": db.scalar(select(func.count(m.QuestionAttempt.id)).where(
            m.QuestionAttempt.user_id == user.id, m.QuestionAttempt.is_imported.is_(True))) or 0,
        "exam_attempts": db.scalar(select(func.count(m.ExamAttempt.id)).where(
            m.ExamAttempt.user_id == user.id)) or 0,
        "upcoming_exams": db.scalar(select(func.count(m.UpcomingExam.id)).where(
            m.UpcomingExam.user_id == user.id)) or 0,
        "taught_topics": db.scalar(select(func.count(m.TaughtTopic.id)).where(
            m.TaughtTopic.user_id == user.id)) or 0,
    }
    for badge in db.scalars(select(m.Badge)).all():
        if counts.get(badge.condition_type, 0) >= badge.condition_value:
            has = db.scalar(select(m.UserBadge).where(
                m.UserBadge.user_id == user.id, m.UserBadge.badge_id == badge.id))
            if not has:
                db.add(m.UserBadge(user_id=user.id, badge_id=badge.id))
                earned.append(badge.title)
    return earned


def summary(db: Session, user: m.User) -> dict:
    today = date.today()
    today_points = db.scalar(select(func.coalesce(func.sum(m.RewardEvent.points), 0)).where(
        m.RewardEvent.user_id == user.id, m.RewardEvent.event_date == today)) or 0
    week_points = db.scalar(select(func.coalesce(func.sum(m.RewardEvent.points), 0)).where(
        m.RewardEvent.user_id == user.id,
        m.RewardEvent.event_date >= today - timedelta(days=6))) or 0
    wake = db.scalar(select(m.WakeUpEvent).where(
        m.WakeUpEvent.user_id == user.id, m.WakeUpEvent.date == today))
    badges = db.execute(
        select(m.Badge.title, m.UserBadge.earned_at)
        .join(m.UserBadge, m.UserBadge.badge_id == m.Badge.id)
        .where(m.UserBadge.user_id == user.id)
        .order_by(m.UserBadge.earned_at.desc())
    ).all()
    return {
        "coins": user.total_points,
        "today_points": today_points,
        "week_points": week_points,
        "current_streak": user.current_streak,
        "longest_streak": user.longest_streak,
        "wake_up_today": bool(wake),
        "wake_up_time": wake.recorded_time if wake else None,
        "badges": [{"title": b[0], "earned_at": b[1].isoformat()} for b in badges],
    }
