"""Rewards: study coins, wake-up habit, streak and badges.

All numbers come from the V2 numeric reference (unchanged in V3). Imported
historical sessions earn **no** coins, exactly as specified.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import local_now, now_utc, today_local
from ..db import models
from ..domain.enums import TaskStatus
from . import common


def _award(
    db: Session,
    user: models.User,
    *,
    event_type: str,
    coins: int,
    description: str,
    dedupe_key: str,
    day: Optional[_dt.date] = None,
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
) -> Optional[models.RewardEvent]:
    exists = db.scalars(select(models.RewardEvent).where(models.RewardEvent.dedupe_key == dedupe_key)).first()
    if exists:
        return None
    event = models.RewardEvent(
        user_id=user.id,
        event_type=event_type,
        coins=coins,
        description=description,
        dedupe_key=dedupe_key,
        related_entity_type=related_type,
        related_entity_id=related_id,
        day=day or today_local(),
    )
    db.add(event)
    user.total_coins = (user.total_coins or 0) + coins
    db.flush()
    return event


def apply_session_rewards(db: Session, user: models.User, session: models.TestSession) -> dict:
    """Coins for a finished session. Imported history is explicitly excluded."""
    if session.is_imported or session.session_type == "imported":
        return {
            "coins": 0,
            "events": [],
            "note": "جلسه واردشده از گذشته است؛ طبق قوانین سکه تعلق نمی‌گیرد.",
        }
    coins = 0
    events: list[dict] = []
    attempts = list(
        db.scalars(
            select(models.AttemptResult).where(
                models.AttemptResult.session_id == session.id, models.AttemptResult.is_current.is_(True)
            )
        )
    )
    correct_coins = config.value("reward.coins_correct_answer")
    review_coins = config.value("reward.coins_successful_review")
    for attempt in attempts:
        if attempt.result == "CORRECT":
            key = f"session:{session.id}:q:{attempt.question_id}:correct"
            is_review = session.session_type == "review"
            amount = review_coins if is_review else correct_coins
            event = _award(
                db, user,
                event_type="correct_answer",
                coins=amount,
                description="پاسخ درست" + (" در مرور" if is_review else ""),
                dedupe_key=key,
                related_type="attempt",
                related_id=attempt.id,
            )
            if event:
                coins += amount
                events.append({"type": event.event_type, "coins": amount})
    day = session.planned_date or today_local()
    completed_today = db.scalar(
        select(func.count(models.StudyTask.id)).where(
            models.StudyTask.user_id == user.id,
            models.StudyTask.planned_date == day,
            models.StudyTask.status == TaskStatus.COMPLETED.value,
        )
    ) or 0
    open_today = db.scalar(
        select(func.count(models.StudyTask.id)).where(
            models.StudyTask.user_id == user.id,
            models.StudyTask.planned_date == day,
            models.StudyTask.status.in_([TaskStatus.PLANNED.value, TaskStatus.IN_PROGRESS.value]),
        )
    ) or 0
    if completed_today and not open_today:
        amount = config.value("reward.coins_all_daily_tests")
        event = _award(
            db, user,
            event_type="daily_tests_completed",
            coins=amount,
            description="تکمیل همه کارهای روز",
            dedupe_key=f"day:{day.isoformat()}:all_done",
            day=day,
        )
        if event:
            coins += amount
            events.append({"type": event.event_type, "coins": amount})
    streak = update_streak(db, user, day)
    if streak.get("increment"):
        amount = config.value("reward.coins_streak_day") * max(1, user.current_streak)
        event = _award(
            db, user,
            event_type="streak_day",
            coins=amount,
            description=f"روز {user.current_streak} از پیوستگی",
            dedupe_key=f"streak:{day.isoformat()}",
            day=day,
        )
        if event:
            coins += amount
            events.append({"type": event.event_type, "coins": amount})
    badge_list = evaluate_badges(db, user)
    return {"coins": coins, "events": events, "streak": user.current_streak, "badges": badge_list}


def award_task_completion(db: Session, user: models.User, task: models.StudyTask) -> dict:
    amount = config.value("reward.coins_task_completed")
    event = _award(
        db, user,
        event_type="task_completed",
        coins=amount,
        description=f"تکمیل کار: {task.title}",
        dedupe_key=f"task:{task.id}:completed",
        day=task.planned_date or today_local(),
        related_type="task",
        related_id=task.id,
    )
    update_streak(db, user, task.planned_date or today_local())
    return {"coins": amount if event else 0, "event": event.event_type if event else None}


def update_streak(db: Session, user: models.User, day: _dt.date) -> dict:
    """Streak: a day with no completed task resets it (strict V2 rule)."""
    last_day = db.scalar(
        select(func.max(models.RewardEvent.day)).where(
            models.RewardEvent.user_id == user.id, models.RewardEvent.event_type == "streak_day"
        )
    )
    if last_day == day:
        return {"current": user.current_streak, "increment": False, "reason": "already_counted"}
    completed = db.scalar(
        select(func.count(models.StudyTask.id)).where(
            models.StudyTask.user_id == user.id,
            models.StudyTask.planned_date == day,
            models.StudyTask.status == TaskStatus.COMPLETED.value,
        )
    ) or 0
    has_activity = bool(completed) or bool(
        db.scalar(
            select(func.count(models.AttemptResult.id)).where(
                models.AttemptResult.user_id == user.id, models.AttemptResult.attempted_on == day
            )
        )
    )
    if not has_activity:
        was = user.current_streak
        user.current_streak = 0
        db.flush()
        return {"current": 0, "increment": False, "reason": "no_activity", "previous": was}
    previous_day = day - _dt.timedelta(days=1)
    yesterday_event = db.scalars(
        select(models.RewardEvent).where(
            models.RewardEvent.user_id == user.id,
            models.RewardEvent.event_type == "streak_day",
            models.RewardEvent.day == previous_day,
        )
    ).first()
    user.current_streak = (user.current_streak or 0) + 1 if yesterday_event else 1
    user.longest_streak = max(user.longest_streak or 0, user.current_streak)
    db.flush()
    return {"current": user.current_streak, "increment": True}


def record_wake_up(db: Session, user: models.User, at: Optional[_dt.datetime] = None) -> dict:
    """Wake-up coins: before 07:00 → +15, before 06:45 → +5 extra, after 07:15 → nothing."""
    local = (at or local_now()).astimezone(local_now().tzinfo) if at else local_now()
    day = local.date()
    existing = db.scalars(
        select(models.WakeUpEvent).where(models.WakeUpEvent.user_id == user.id, models.WakeUpEvent.day == day)
    ).first()
    if existing:
        return {
            "recorded": False,
            "already": True,
            "coins": existing.coins_awarded,
            "local_time": existing.local_time,
            "message": "امروز قبلاً ثبت شده است.",
        }
    target = f"{config.value('reward.wake_target_hour'):02d}:{config.value('reward.wake_target_minute'):02d}"
    late_limit = config.value("reward.wake_late_limit")
    early_bonus_time = config.value("reward.wake_early_bonus_time")
    local_text = local.strftime("%H:%M")
    coins = 0
    reason = ""
    if local_text <= late_limit:
        if local_text <= target:
            coins += config.value("reward.coins_wake_up")
            reason = f"بیداری تا ساعت {target}"
            if local_text <= early_bonus_time:
                coins += config.value("reward.coins_wake_up_early_bonus")
                reason += f" + بونوس قبل از {early_bonus_time}"
        else:
            reason = f"بعد از {target} و تا {late_limit}؛ سکه بیداری‌زود تعلق نگرفت."
    else:
        reason = f"بعد از {late_limit} ثبت شد؛ دیگر سکه بیداری تعلق نمی‌گیرد."
    event = models.WakeUpEvent(
        user_id=user.id, day=day, recorded_at=now_utc(), local_time=local_text, coins_awarded=coins
    )
    db.add(event)
    if coins:
        _award(
            db, user,
            event_type="wake_up",
            coins=coins,
            description=reason,
            dedupe_key=f"wakeup:{day.isoformat()}",
            day=day,
        )
    db.flush()
    common.observe(db, user.id, "wake_up_recorded", payload={"local_time": local_text, "coins": coins}, source="user", day=day)
    return {
        "recorded": True,
        "already": False,
        "coins": coins,
        "local_time": local_text,
        "target": target,
        "late_limit": late_limit,
        "message": reason,
    }


def evaluate_badges(db: Session, user: models.User) -> list[dict]:
    earned = []
    badges = list(db.scalars(select(models.Badge)))
    owned = {
        row.badge_id
        for row in db.scalars(select(models.UserBadge).where(models.UserBadge.user_id == user.id))
    }
    answered_questions = db.scalar(
        select(func.count(func.distinct(models.AttemptResult.question_id))).where(
            models.AttemptResult.user_id == user.id, models.AttemptResult.state == "ANSWERED"
        )
    ) or 0
    best_coverage = db.scalar(
        select(func.max(models.LearningState.coverage)).where(models.LearningState.user_id == user.id)
    )
    best_accuracy = db.scalar(
        select(func.max(models.LearningState.accuracy)).where(models.LearningState.user_id == user.id)
    )
    for badge in badges:
        if badge.id in owned:
            continue
        value = None
        if badge.condition_type == "question_count":
            value = answered_questions
        elif badge.condition_type == "coverage":
            value = best_coverage
        elif badge.condition_type == "streak":
            value = user.longest_streak or 0
        elif badge.condition_type == "accuracy":
            value = best_accuracy
        elif badge.condition_type == "weekly_goal":
            value = None  # weekly goals are evaluated by the planner
        if value is None:
            continue
        if value >= (badge.condition_value or 0):
            db.add(models.UserBadge(user_id=user.id, badge_id=badge.id))
            earned.append({"code": badge.code, "title": badge.title, "icon": badge.icon})
            _award(
                db, user,
                event_type="badge_earned",
                coins=0,
                description=f"نشان: {badge.title}",
                dedupe_key=f"badge:{badge.code}",
                related_type="badge",
                related_id=badge.id,
            )
    db.flush()
    return earned


def summary(db: Session, user: models.User) -> dict:
    recent = list(
        db.scalars(
            select(models.RewardEvent)
            .where(models.RewardEvent.user_id == user.id)
            .order_by(models.RewardEvent.id.desc())
            .limit(15)
        )
    )
    badges = list(
        db.execute(
            select(models.Badge, models.UserBadge.earned_at)
            .join(models.UserBadge, models.UserBadge.badge_id == models.Badge.id)
            .where(models.UserBadge.user_id == user.id)
        ).all()
    )
    today_wake = db.scalars(
        select(models.WakeUpEvent).where(models.WakeUpEvent.user_id == user.id, models.WakeUpEvent.day == today_local())
    ).first()
    return {
        "total_coins": user.total_coins or 0,
        "current_streak": user.current_streak or 0,
        "longest_streak": user.longest_streak or 0,
        "wake_up_today": {
            "recorded": bool(today_wake),
            "coins": today_wake.coins_awarded if today_wake else 0,
            "local_time": today_wake.local_time if today_wake else None,
        },
        "coins_table": [
            {"event": "بیدار شدن تا ۰۷:۰۰", "coins": config.value("reward.coins_wake_up")},
            {"event": "بیداری قبل از ۰۶:۴۵ (بونوس)", "coins": config.value("reward.coins_wake_up_early_bonus")},
            {"event": "تکمیل همه کارهای روز", "coins": config.value("reward.coins_all_daily_tests")},
            {"event": "تکمیل هر کار", "coins": config.value("reward.coins_task_completed")},
            {"event": "هر پاسخ درست", "coins": config.value("reward.coins_correct_answer")},
            {"event": "مرور موفق", "coins": config.value("reward.coins_successful_review")},
            {"event": "هر روز پیوستگی", "coins": config.value("reward.coins_streak_day")},
        ],
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "coins": event.coins,
                "description": event.description,
                "date": common.jdate(event.day),
            }
            for event in recent
        ],
        "badges": [
            {"code": badge.code, "title": badge.title, "icon": badge.icon, "earned_at": common.jdate(earned_at)}
            for badge, earned_at in badges
        ],
        "all_badges": [
            {
                "code": badge.code,
                "title": badge.title,
                "icon": badge.icon,
                "description": badge.description,
                "earned": badge.code in {b["code"] for b in [
                    {"code": bb.code} for bb, _ in badges
                ]},
            }
            for badge in db.scalars(select(models.Badge))
        ],
        "note": "جلسه‌های واردشده از گذشته سکه نمی‌گیرند.",
    }
