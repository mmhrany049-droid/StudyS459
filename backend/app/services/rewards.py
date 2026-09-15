"""Rewards: points + streak + badges (spec 10, Phase 7).

All amounts are spec constants. Points derive from append-only events;
streak derives from study-task completions (spec 10: study tasks drive
the streak); badges are granted once and recorded as events too.
Motivational only — never feeds planning or selection (spec 10 rule).
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.analytics.context import build_book_context
from app.analytics.finals import pair_buckets
from app.analytics.metrics import normalize_week, user_day
from app.db import utcnow
from app.errors import AppError
from app.models import Task, TestSession
from app.repositories import books as book_repo
from app.repositories import planner as planner_repo
from app.repositories import rewards as repo
from app.schemas.rewards import BadgeOut, RewardEventOut, RewardsSummaryOut
from app.services.users import get_or_create_single_user

POINTS_PER_CORRECT = 2
POINTS_RECOVERY = 1
POINTS_STUDY_TASK = 5
POINTS_DAILY = 15
POINTS_WEEKLY = 50
POINTS_STREAK_DAY = 5

BADGE_DEFS = [
    {"code": "first_20_tests", "title": "۲۰ تست اول",
     "description": "اولین ۲۰ تست نهایی‌شده", "condition_type": "volume_total",
     "condition_value": "20"},
    {"code": "chapter_coverage_80", "title": "پوشش ۸۰٪ فصل",
     "description": "اولین فصل با پوشش حداقل ۸۰٪",
     "condition_type": "chapter_coverage", "condition_value": "0.8"},
    {"code": "streak_7", "title": "استمرار ۷ روزه",
     "description": "۷ روز متوالی فعالیت مطالعاتی",
     "condition_type": "streak_days", "condition_value": "7"},
    {"code": "streak_30", "title": "استمرار ۳۰ روزه",
     "description": "۳۰ روز متوالی فعالیت مطالعاتی",
     "condition_type": "streak_days", "condition_value": "30"},
    {"code": "accuracy_75", "title": "دقت ۷۵٪",
     "description": "دقت حداقل ۷۵٪ در یک مبحث با حداقل ۲۰ تست",
     "condition_type": "topic_accuracy", "condition_value": "0.75/20"},
    {"code": "weekly_topic_goal", "title": "هدف موضوعی هفته",
     "description": "تکمیل یک هدف موضوعی هفتگی",
     "condition_type": "topic_goal_done", "condition_value": "1"},
]


def _ensure_badges(db: Session) -> None:
    for d in BADGE_DEFS:
        repo.ensure_badge(db, **d)


def _grant_badge(db: Session, user_id: int, code: str) -> bool:
    """Grant once; a badge_earned event (0 points) records it."""
    _ensure_badges(db)
    badge = repo.get_badge_by_code(db, code)
    assert badge is not None
    if not repo.grant_badge(db, user_id, badge.id):
        return False
    repo.add_event(
        db, user_id=user_id, event_type="badge_earned", points=0,
        description=f"نشان جدید: {badge.title}",
        related_entity_type="badge", related_entity_id=badge.id,
    )
    return True


# -- streak ------------------------------------------------------------------

def _study_days(db: Session, user_id: int, tz: str) -> set[date]:
    days: set[date] = set()
    for t in planner_repo.list_tasks(db, user_id):
        if (t.task_type == "study" and t.status == "completed"
                and t.completed_at is not None):
            days.add(user_day(t.completed_at, tz))
    return days


def streak_counts(days: set[date], today: date) -> tuple[int, int]:
    """(current, longest) streak over active days. Pure helper."""
    longest = run = 0
    prev: date | None = None
    for d in sorted(days):
        run = run + 1 if prev is not None and d == prev + timedelta(days=1) else 1
        longest = max(longest, run)
        prev = d
    current = 0
    cursor = today
    if cursor not in days:
        cursor -= timedelta(days=1)  # today still open: streak alive via yesterday
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def _study_completions_on_day(
    db: Session, user_id: int, day: date, tz: str
) -> int:
    return sum(1 for d in _study_day_list(db, user_id, tz) if d == day)


def _study_day_list(db: Session, user_id: int, tz: str) -> list[date]:
    out: list[date] = []
    for t in planner_repo.list_tasks(db, user_id):
        if (t.task_type == "study" and t.status == "completed"
                and t.completed_at is not None):
            out.append(user_day(t.completed_at, tz))
    return out


# -- session finish ------------------------------------------------------------

def on_session_finished(
    db: Session, user_id: int, session: TestSession, buckets: dict[int, str],
    *, tz: str,
) -> int:
    """Award session points + volume badges + weekly-goal check."""
    correct_qids = [qid for qid, b in buckets.items() if b == "correct"]
    points = POINTS_PER_CORRECT * len(correct_qids)
    earlier_bad: set[int] = set()
    for (sid, qid), b in pair_buckets(db, user_id).items():
        if sid < session.id and b in ("wrong", "unanswered"):
            earlier_bad.add(qid)
    recovered = [q for q in correct_qids if q in earlier_bad]
    points += POINTS_RECOVERY * len(recovered)
    if points:
        desc = f"تست: {len(correct_qids)} درست (+{POINTS_PER_CORRECT * len(correct_qids)})"
        if recovered:
            desc += f"، {len(recovered)} بازیابی (+{len(recovered)})"
        repo.add_event(
            db, user_id=user_id, event_type="test_session", points=points,
            description=desc, related_entity_type="test_session",
            related_entity_id=session.id,
        )
    _check_volume_badges(db, user_id)
    points += _check_weekly_goal(db, user_id, session, tz=tz)
    return points


def _check_volume_badges(db: Session, user_id: int) -> None:
    pairs = pair_buckets(db, user_id)
    if len(pairs) >= 20:
        _grant_badge(db, user_id, "first_20_tests")
    ever = {qid for (_sid, qid) in pairs}
    for book in book_repo.list_books(db):
        activation = book_repo.get_activation(db, user_id, book.id)
        if not (activation and activation.active):
            continue
        ctx = build_book_context(db, user_id=user_id, book_id=book.id)
        for node in ctx.nodes:
            pool = ctx.pool.get(node.id, set())
            if not pool:
                continue
            node_buckets = [b for (_sid, qid), b in pairs.items() if qid in pool]
            if (node.node_type == "chapter"
                    and len(pool & ever) / len(pool) >= 0.8):
                _grant_badge(db, user_id, "chapter_coverage_80")
            correct = node_buckets.count("correct")
            wrong = node_buckets.count("wrong")
            if (len(node_buckets) >= 20 and correct + wrong > 0
                    and correct / (correct + wrong) >= 0.75):
                _grant_badge(db, user_id, "accuracy_75")


def _check_weekly_goal(db: Session, user_id: int, session: TestSession, *, tz: str) -> int:
    from app.services import goals as goals_service

    week_start = normalize_week(user_day(session.started_at, tz))[0]
    try:
        goal = goals_service.get_week_goal(db, user_id=user_id, week=str(week_start))
    except AppError as e:
        if e.code == "goal_not_found":
            return 0
        raise
    if any(it.goal_type == "topic" and it.progress.done for it in goal.items):
        _grant_badge(db, user_id, "weekly_topic_goal")
    if (goal.items and all(it.progress.done for it in goal.items)
            and not repo.has_event(db, user_id, "weekly_goal", "weekly_goal", goal.id)):
        repo.add_event(
            db, user_id=user_id, event_type="weekly_goal", points=POINTS_WEEKLY,
            description=f"تکمیل هدف هفته {goal.week_start} (+{POINTS_WEEKLY})",
            related_entity_type="weekly_goal", related_entity_id=goal.id,
        )
        return POINTS_WEEKLY
    return 0


# -- task completion -------------------------------------------------------------

def on_task_completed(
    db: Session, user_id: int, task: Task, *, tz: str, today: date | None = None
) -> int:
    """Award task points + streak + daily check. Call ONCE per flip."""
    points = 0
    now_day = today or user_day(utcnow().replace(tzinfo=None), tz)
    if task.task_type == "study":
        points += POINTS_STUDY_TASK
        repo.add_event(
            db, user_id=user_id, event_type="study_task", points=POINTS_STUDY_TASK,
            description=f"تکمیل مطالعه: {task.title} (+{POINTS_STUDY_TASK})",
            related_entity_type="task", related_entity_id=task.id,
        )
        assert task.completed_at is not None
        done_day = user_day(task.completed_at, tz)
        if _study_completions_on_day(db, user_id, done_day, tz) == 1:
            # First study completion that day: the streak grows.
            days = _study_days(db, user_id, tz)
            current, _longest = streak_counts(days, now_day)
            points += POINTS_STREAK_DAY
            repo.add_event(
                db, user_id=user_id, event_type="streak_day",
                points=POINTS_STREAK_DAY,
                description=f"روز {current} استمرار (+{POINTS_STREAK_DAY})",
                related_entity_type="date",
                related_entity_id=int(done_day.strftime("%Y%m%d")),
            )
            if current >= 7:
                _grant_badge(db, user_id, "streak_7")
            if current >= 30:
                _grant_badge(db, user_id, "streak_30")
    points += _check_daily_goal(db, user_id, task)
    return points


def _check_daily_goal(db: Session, user_id: int, task: Task) -> int:
    from app.models import DailyTaskPlacement

    placement = db.get(DailyTaskPlacement, task.id)
    if placement is None:
        return 0
    rows = planner_repo.placements_on(db, user_id, placement.date)
    for r in rows:
        t = db.get(Task, r.task_id)
        if t is not None and t.status != "completed":
            return 0  # day still open
    day_key = int(placement.date.strftime("%Y%m%d"))
    if repo.has_event(db, user_id, "daily_goal", "date", day_key):
        return 0
    repo.add_event(
        db, user_id=user_id, event_type="daily_goal", points=POINTS_DAILY,
        description=f"تکمیل برنامه روز {placement.date} (+{POINTS_DAILY})",
        related_entity_type="date", related_entity_id=day_key,
    )
    return POINTS_DAILY


# -- reads -----------------------------------------------------------------------

def _event_out(e) -> RewardEventOut:
    return RewardEventOut(
        id=e.id, event_type=e.event_type, points=e.points,
        description=e.description, related_entity_type=e.related_entity_type,
        related_entity_id=e.related_entity_id, created_at=e.created_at,
    )


def summary(db: Session, *, user_id: int) -> RewardsSummaryOut:
    user = get_or_create_single_user(db, user_id)
    _ensure_badges(db)
    days = _study_days(db, user.id, user.timezone)
    today = user_day(utcnow().replace(tzinfo=None), user.timezone)
    current, longest = streak_counts(days, today)
    earned = repo.user_badges(db, user.id)
    by_id = {b.id: b for b in repo.list_badges(db)}
    return RewardsSummaryOut(
        user_id=user.id,
        total_points=repo.total_points(db, user.id),
        current_streak=current,
        longest_streak=longest,
        badge_count=len(earned),
        badges=[
            BadgeOut(code=by_id[u.badge_id].code, title=by_id[u.badge_id].title,
                     description=by_id[u.badge_id].description,
                     earned=True, earned_at=u.earned_at)
            for u in earned
        ],
        recent_events=[_event_out(e) for e in repo.list_events(db, user.id, limit=5)],
    )


def list_events(db: Session, *, user_id: int, limit: int) -> list[RewardEventOut]:
    user = get_or_create_single_user(db, user_id)
    if not 1 <= limit <= 200:
        raise AppError("invalid_limit", "limit باید بین ۱ تا ۲۰۰ باشد.", status_code=422)
    return [_event_out(e) for e in repo.list_events(db, user.id, limit=limit)]


def list_badges(db: Session, *, user_id: int) -> list[BadgeOut]:
    user = get_or_create_single_user(db, user_id)
    _ensure_badges(db)
    earned = {u.badge_id: u.earned_at for u in repo.user_badges(db, user.id)}
    return [
        BadgeOut(code=b.code, title=b.title, description=b.description,
                 earned=b.id in earned, earned_at=earned.get(b.id))
        for b in repo.list_badges(db)
    ]
