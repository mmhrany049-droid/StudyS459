"""سیستم جایزه V2 — سکه مطالعه + بیدار شدن + streak سخت‌گیرانه + نشان‌ها.

جدول قطعی سکه (07_REWARDS_AND_COINS_V2 و 14_NUMERIC):
- بیدار شدن تا ۰۷:۰۰ → +۱۵ (قبل ۰۶:۴۵ → +۵ اضافی)؛ بعد ۰۷:۱۵ سکه ندارد
- تکمیل تمام تست‌های روز → +۴۰
- تکمیل Task غیرتست → +۸
- پاسخ درست → +۲
- مرور موفق → +۳
- هدف روزانه → +۲۰ ؛ هدف هفتگی → +۷۰
- هر روز Streak → +۱۰
- Import گذشته → سکه ندارد
- یک روز بدون Task تکمیل‌شده → current_streak = 0
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.config as cfg
from app.jalali import now_tehran, today_tehran
from app.models import (Badge, DailyTaskPlacement, QuestionAttempt, ReviewQueueItem, RewardEvent,
                        Task, TestSession, User, UserBadge, WakeUpEvent)


def add_reward(db: Session, user: User, event_type: str, coins: int, description: str,
               entity_type: str | None = None, entity_id: int | None = None) -> RewardEvent:
    ev = RewardEvent(user_id=user.id, event_type=event_type, points=coins, coins=coins,
                     description=description, related_entity_type=entity_type,
                     related_entity_id=entity_id)
    db.add(ev)
    user.coins += coins
    user.total_points += coins
    return ev


def wake_up(db: Session, user: User) -> dict:
    """ثبت بیدار شدن — فقط یک‌بار در روز؛ پنجرهٔ سکه تا ۰۷:۰۰ (+۵ تا ۰۶:۴۵)."""
    now = now_tehran()
    today = now.date()
    existing = db.execute(
        select(WakeUpEvent).where(WakeUpEvent.user_id == user.id, WakeUpEvent.date == today)
    ).scalar_one_or_none()
    if existing is not None:
        return {"ok": False, "reason": "already_recorded",
                "message": "امروز بیدار شدنت ثبت شده است.", "coins": 0}

    minutes = now.hour * 60 + now.minute
    deadline = cfg.WAKE_UP_DEADLINE_HOUR * 60 + cfg.WAKE_UP_DEADLINE_MINUTE
    early = cfg.WAKE_UP_DEADLINE_HOUR * 60 + 15  # 06:45
    late_limit = cfg.WAKE_UP_LATE_LIMIT_HOUR * 60 + cfg.WAKE_UP_LATE_LIMIT_MINUTE

    coins = 0
    message = "ثبت شد؛ امروز خارج از پنجرهٔ سکهٔ بیدار شدن بود (بعد از ۰۷:۱۵)."
    if minutes <= deadline:
        coins = cfg.POINTS_WAKE_UP
        message = f"بیدار شدن تا ۰۷:۰۰ ثبت شد؛ +{coins} سکه."
        if minutes < early:
            coins += cfg.POINTS_WAKE_UP_EARLY_BONUS
            message = f"بیدار شدن قبل از ۰۶:۴۵! +{coins} سکه (با پاداش زودهنگامی)."
    elif minutes <= late_limit:
        message = "ثبت شد (۰۷:۰۰ تا ۰۷:۱۵)؛ سکهٔ بیدار شدن تعلق نگرفت."

    ev = WakeUpEvent(user_id=user.id, date=today, points_awarded=coins)
    db.add(ev)
    if coins > 0:
        add_reward(db, user, "wake_up", coins, message)
    return {"ok": True, "coins": coins, "message": message}


def _last_activity_date(db: Session, user_id: int) -> dt.date | None:
    return db.scalar(
        select(func.max(DailyTaskPlacement.date))
        .join(Task, Task.id == DailyTaskPlacement.task_id)
        .where(Task.user_id == user_id, Task.status == "completed")
    )


def refresh_streak(db: Session, user: User) -> None:
    """قانون سخت‌گیرانه: بیش از یک روز بدون Task تکمیل‌شده → صفر."""
    last = _last_activity_date(db, user.id)
    today = today_tehran()
    if last is None:
        user.current_streak = 0
        return
    if (today - last).days > 1:
        user.current_streak = 0


def streak_day_reward(db: Session, user: User) -> None:
    """+۱۰ سکه به ازای هر روز Streak (هنگام اولین تکمیل Task در روز)."""
    today = today_tehran()
    already = db.execute(
        select(RewardEvent.id).where(
            RewardEvent.user_id == user.id,
            RewardEvent.event_type == "streak_day",
            func.date(RewardEvent.created_at) == today,
        )
    ).scalar_one_or_none()
    if already is None:
        user.current_streak += 1
        if user.current_streak > user.longest_streak:
            user.longest_streak = user.current_streak
        add_reward(db, user, "streak_day", cfg.POINTS_STREAK_DAY,
                   f"روز {user.current_streak} از Streak فعال")


def complete_task_rewards(db: Session, user: User, task: Task) -> None:
    """پاداش‌های تکمیل Task: streak + سکهٔ کار غیرتست."""
    refresh_streak(db, user)
    streak_day_reward(db, user)
    if task.task_type != "test":
        add_reward(db, user, "task_completed", cfg.POINTS_COMPLETE_TASK,
                   f"تکمیل «{task.title}»", "task", task.id)
    check_badges(db, user)


def on_test_session_completed(db: Session, user: User, session: TestSession) -> dict:
    """پایان جلسهٔ تست (عادی): +۲ به ازای هر پاسخ درست؛ تکمیل تستهای روز → +۴۰."""
    if session.is_imported:
        return {"coins": 0, "note": "import سکه ندارد"}
    correct = db.scalar(
        select(func.count(QuestionAttempt.id)).where(
            QuestionAttempt.session_id == session.id,
            QuestionAttempt.result == "correct",
        )
    ) or 0
    coins = correct * cfg.POINTS_CORRECT_ANSWER
    if coins:
        add_reward(db, user, "correct_answers", coins,
                   f"{correct} پاسخ درست در جلسهٔ تست", "test_session", session.id)
    # تکمیل تمام تست‌های مشخص‌شدهٔ آن روز
    today = session.session_date or today_tehran()
    test_tasks = db.execute(
        select(Task).join(DailyTaskPlacement, DailyTaskPlacement.task_id == Task.id)
        .where(DailyTaskPlacement.date == today, Task.task_type == "test",
               Task.status != "cancelled", Task.user_id == user.id)
    ).scalars().all()
    if test_tasks and all(t.status == "completed" for t in test_tasks):
        already = db.execute(
            select(RewardEvent.id).where(
                RewardEvent.user_id == user.id,
                RewardEvent.event_type == "daily_tests_complete",
                func.date(RewardEvent.created_at) == today,
            )
        ).scalar_one_or_none()
        if already is None:
            add_reward(db, user, "daily_tests_complete", cfg.POINTS_COMPLETE_DAILY_TESTS,
                       "تکمیل تمام تست‌های امروز")
            coins += cfg.POINTS_COMPLETE_DAILY_TESTS
    return {"coins": coins}


def successful_review_reward(db: Session, user: User, question_id: int) -> None:
    add_reward(db, user, "review_success", cfg.POINTS_SUCCESSFUL_REVIEW,
               "مرور موفق یک سوال", "question", question_id)


def check_badges(db: Session, user: User) -> list[Badge]:
    """بررسی و اعطای نشان‌ها."""
    earned: list[Badge] = []
    owned = {b.badge_id for b in db.scalars(
        select(UserBadge).where(UserBadge.user_id == user.id))}

    stats: dict[str, int] = {}
    stats["tasks_completed"] = db.scalar(
        select(func.count(Task.id)).where(Task.user_id == user.id,
                                          Task.status == "completed")) or 0
    stats["tests_completed"] = db.scalar(
        select(func.count(TestSession.id)).where(
            TestSession.user_id == user.id, TestSession.status == "completed",
            TestSession.is_imported == False)) or 0  # noqa: E712
    stats["imports"] = db.scalar(
        select(func.count(TestSession.id)).where(
            TestSession.user_id == user.id, TestSession.is_imported == True)) or 0  # noqa: E712
    stats["streak"] = user.longest_streak
    stats["coins"] = user.coins
    stats["reviews_resolved"] = db.scalar(
        select(func.count(ReviewQueueItem.id)).where(
            ReviewQueueItem.user_id == user.id,
            ReviewQueueItem.status == "resolved")) or 0
    answered = db.scalar(
        select(func.count(QuestionAttempt.id)).where(
            QuestionAttempt.user_id == user.id,
            QuestionAttempt.result.in_(("correct", "wrong")))) or 0
    correct = db.scalar(
        select(func.count(QuestionAttempt.id)).where(
            QuestionAttempt.user_id == user.id,
            QuestionAttempt.result == "correct")) or 0
    stats["volume"] = db.scalar(
        select(func.count(QuestionAttempt.id)).where(
            QuestionAttempt.user_id == user.id)) or 0
    stats["accuracy"] = int(100 * correct / answered) if answered else 0

    from app.models import OnboardingAnswer
    stats["questionnaire"] = db.scalar(
        select(func.count(OnboardingAnswer.id)).where(
            OnboardingAnswer.user_id == user.id)) or 0

    for badge in db.scalars(select(Badge)):
        if badge.id in owned:
            continue
        val = stats.get(badge.condition_type)
        if val is None:
            continue
        if badge.condition_type == "accuracy":
            ok = stats["volume"] >= 50 and val >= badge.condition_value
        elif badge.condition_type == "questionnaire":
            ok = val >= badge.condition_value * 30  # ~۳۰ پاسخ = کامل
        else:
            ok = val >= badge.condition_value
        if ok:
            db.add(UserBadge(user_id=user.id, badge_id=badge.id))
            earned.append(badge)
    return earned


def rewards_summary(db: Session, user: User) -> dict:
    refresh_streak(db, user)
    events = list(db.scalars(
        select(RewardEvent).where(RewardEvent.user_id == user.id)
        .order_by(RewardEvent.created_at.desc()).limit(50)))
    badges = list(db.scalars(select(UserBadge).where(UserBadge.user_id == user.id)))
    badge_map = {b.id: b for b in db.scalars(select(Badge))}
    return {
        "coins": user.coins,
        "total_points": user.total_points,
        "current_streak": user.current_streak,
        "longest_streak": user.longest_streak,
        "wake_up_today": db.execute(
            select(WakeUpEvent).where(WakeUpEvent.user_id == user.id,
                                      WakeUpEvent.date == today_tehran())
        ).scalar_one_or_none() is not None,
        "events": [{
            "id": e.id, "event_type": e.event_type, "coins": e.coins,
            "description": e.description, "created_at": e.created_at.isoformat(),
        } for e in events],
        "badges": [{
            "code": badge_map[ub.badge_id].code,
            "title": badge_map[ub.badge_id].title,
            "description": badge_map[ub.badge_id].description,
            "earned_at": ub.earned_at.isoformat(),
        } for ub in badges if ub.badge_id in badge_map],
    }
