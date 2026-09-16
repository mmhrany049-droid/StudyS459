"""
Planning Engine — وزن‌های ثابت V2 (سند 14_NUMERIC و 08_PLANNING_ADVICE)
+ لایه رفتاری V2.1 (ظرفیت/تعداد/ترتیب) + سیگنال‌های V2.2 (تدریس‌شده، آمادگی امتحان).
وزن‌های هسته تغییر نمی‌کنند؛ لایه رفتاری فقط روی تعداد و ترتیب اثر دارد.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config as cfg
from .. import models as m
from ..utils import jalali
from .common import node_full_title, node_stats, questions_of_node
from .test_engine import suggest_parity


# ---------------------------------------------------------------- capacity
def day_capacity(db: Session, user: m.User, day: date) -> dict:
    override = db.scalar(select(m.SchoolDayOverride).where(
        m.SchoolDayOverride.user_id == user.id, m.SchoolDayOverride.date == day))
    school = jalali.is_school_day(day, user.season_mode)
    overridden = False
    if override:
        school = override.is_school_day
        overridden = True

    sleep_minutes = user.sleep_hour * 60 + user.sleep_minute
    classes = _classes_on(db, user, day)
    end_minutes = (cfg.DEFAULT_SCHOOL_END_HOUR * 60 + cfg.DEFAULT_SCHOOL_END_MINUTE) if school else 8 * 60
    for c in classes:
        if c.end_time:
            try:
                hh, mm = c.end_time.split(":")
                end_minutes = max(end_minutes, int(hh) * 60 + int(mm))
            except ValueError:
                pass

    capacity = sleep_minutes - end_minutes - cfg.DEFAULT_PERSONAL_TIME_MINUTES
    class_minutes = 0
    for c in classes:
        if c.start_time and c.end_time:
            try:
                sh, sm = map(int, c.start_time.split(":"))
                eh, em = map(int, c.end_time.split(":"))
                class_minutes += max(0, (eh * 60 + em) - (sh * 60 + sm))
            except ValueError:
                class_minutes += 90
        else:
            class_minutes += 90
    capacity -= class_minutes if school else 0

    if overridden and not override.is_school_day:
        capacity = max(int(capacity * cfg.NO_SCHOOL_CAPACITY_MULTIPLIER),
                       cfg.NO_SCHOOL_MIN_CAPACITY_MINUTES)
    capacity = max(capacity, 45)

    planned = db.scalar(select(func.coalesce(func.sum(m.Task.estimated_minutes), 0)).where(
        m.Task.user_id == user.id, m.Task.planned_date == day, m.Task.status == "pending")) or 0
    blocks = max(1, round(capacity / ((cfg.STUDY_BLOCK_MIN_MINUTES + cfg.STUDY_BLOCK_MAX_MINUTES) / 2)))
    return {
        "date": day.isoformat(),
        **jalali.describe(day),
        "is_school_day": school,
        "overridden": overridden,
        "capacity_minutes": int(capacity),
        "planned_minutes": int(planned),
        "remaining_minutes": int(capacity - planned),
        "over_capacity": planned > capacity,
        "suggested_blocks": blocks,
        "classes": [
            {"id": c.id, "title": c.title, "subject_id": c.subject_id,
             "start_time": c.start_time, "end_time": c.end_time}
            for c in classes
        ],
    }


def _classes_on(db: Session, user: m.User, day: date) -> list[m.Schedule]:
    wd = jalali.iran_weekday(day)
    return list(db.scalars(select(m.Schedule).where(
        m.Schedule.user_id == user.id, m.Schedule.day_of_week == wd)).all())


# ---------------------------------------------------------------- habits
def habit_summary(db: Session, user: m.User) -> dict:
    """فاز یادگیری ۳۰ روزه — سند 08_PLANNING_ADVICE_AFTER_30_DAYS."""
    rows = db.execute(
        select(m.Task.planned_date, func.count(m.Task.id))
        .where(m.Task.user_id == user.id, m.Task.status == "completed")
        .group_by(m.Task.planned_date)
    ).all()
    school_counts, free_counts = [], []
    for d, c in rows:
        (school_counts if jalali.is_school_day(d, user.season_mode) else free_counts).append(c)
    active_days = len(rows)
    avg_school = round(sum(school_counts) / len(school_counts), 1) if school_counts else 0.0
    avg_free = round(sum(free_counts) / len(free_counts), 1) if free_counts else 0.0
    avg_duration = db.scalar(select(func.avg(m.TestSession.actual_duration_minutes)).where(
        m.TestSession.user_id == user.id, m.TestSession.actual_duration_minutes.isnot(None)))
    return {
        "active_days": active_days,
        "threshold": cfg.HABIT_LEARNING_DAYS,
        "learning_phase": active_days < cfg.HABIT_LEARNING_DAYS,
        "avg_tasks_school_day": avg_school,
        "avg_tasks_free_day": avg_free,
        "avg_session_minutes": round(float(avg_duration), 1) if avg_duration else None,
    }


def habit_advice(db: Session, user: m.User, day: date, planned_tasks: int) -> str | None:
    h = habit_summary(db, user)
    if h["learning_phase"]:
        return (f"فاز یادگیری عادت: {h['active_days']} روز از {cfg.HABIT_LEARNING_DAYS} روز. "
                "فعلاً فقط ثبت و مشاهده — بدون توصیه ظرفیت.")
    school = jalali.is_school_day(day, user.season_mode)
    baseline = h["avg_tasks_school_day"] if school else h["avg_tasks_free_day"]
    label = "روز کلاس/مدرسه" if school else "روز آزاد"
    if baseline and planned_tasks > baseline + 1:
        return f"عادت تو در {label} حدود {baseline:g} کار است؛ {planned_tasks} کار امروز سنگین است."
    if baseline and planned_tasks < max(1, baseline - 1):
        return f"در {label} معمولاً {baseline:g} کار انجام می‌دهی؛ {planned_tasks} کار سبک است."
    return None


# ---------------------------------------------------------------- state
def current_state(db: Session, user: m.User) -> dict:
    """Current State Engine — self-report + رفتار اخیر، با confidence."""
    snap = db.scalars(select(m.UserStateSnapshot).where(
        m.UserStateSnapshot.user_id == user.id)
        .order_by(m.UserStateSnapshot.captured_at.desc()).limit(1)).first()
    recent_cut = date.today() - timedelta(days=7)
    total = db.scalar(select(func.count(m.Task.id)).where(
        m.Task.user_id == user.id, m.Task.planned_date >= recent_cut)) or 0
    done = db.scalar(select(func.count(m.Task.id)).where(
        m.Task.user_id == user.id, m.Task.planned_date >= recent_cut,
        m.Task.status == "completed")) or 0
    completion = (done / total) if total else 0.5
    evidence = total
    confidence = round(min(1.0, evidence / 30), 2)

    if snap and (datetime.utcnow() - snap.captured_at) < timedelta(hours=18):
        base = {"energy": snap.energy, "focus": snap.focus, "motivation": snap.motivation,
                "stress": snap.stress, "fatigue": snap.fatigue}
        source = "self_report"
    else:
        base = {"energy": 0.5, "focus": 0.5, "motivation": round(0.3 + completion * 0.6, 2),
                "stress": 0.4, "fatigue": 0.4}
        source = "inferred"
    readiness = round(
        (base["energy"] * 0.3 + base["focus"] * 0.3 + base["motivation"] * 0.2
         + (1 - base["stress"]) * 0.1 + (1 - base["fatigue"]) * 0.1), 2)
    return {
        **{k: round(v, 2) for k, v in base.items()},
        "readiness": readiness,
        "source": source,
        "confidence": confidence,
        "evidence_count": evidence,
        "recent_completion_rate": round(completion, 2),
    }


def behavior_features(db: Session, user: m.User) -> dict:
    cut = date.today() - timedelta(days=30)
    total = db.scalar(select(func.count(m.Task.id)).where(
        m.Task.user_id == user.id, m.Task.planned_date >= cut)) or 0
    done = db.scalar(select(func.count(m.Task.id)).where(
        m.Task.user_id == user.id, m.Task.planned_date >= cut, m.Task.status == "completed")) or 0
    skipped = db.scalar(select(func.count(m.Task.id)).where(
        m.Task.user_id == user.id, m.Task.planned_date >= cut, m.Task.status == "skipped")) or 0
    avg_minutes = db.scalar(select(func.avg(m.TestSession.actual_duration_minutes)).where(
        m.TestSession.user_id == user.id, m.TestSession.actual_duration_minutes.isnot(None)))
    manual = db.scalar(select(func.count(m.Task.id)).where(
        m.Task.user_id == user.id, m.Task.manual_override.is_(True))) or 0
    return {
        "task_completion_rate": round(done / total, 2) if total else 0.0,
        "skip_rate": round(skipped / total, 2) if total else 0.0,
        "average_session_minutes": round(float(avg_minutes), 1) if avg_minutes else 0.0,
        "manual_override_count": manual,
        "evidence_count": total,
        "confidence": round(min(1.0, total / 30), 2),
    }


def suggested_task_count(db: Session, user: m.User, day: date) -> int:
    """ظرفیت رفتاری: چند کار برای امروز واقع‌بینانه است."""
    h = habit_summary(db, user)
    state = current_state(db, user)
    school = jalali.is_school_day(day, user.season_mode)
    baseline = h["avg_tasks_school_day"] if school else h["avg_tasks_free_day"]
    if h["learning_phase"] or not baseline:
        baseline = 3 if school else 5
    factor = 0.75 if state["readiness"] < 0.4 else (1.15 if state["readiness"] > 0.75 else 1.0)
    return max(1, min(8, round(baseline * factor)))


# ---------------------------------------------------------------- candidates
def candidate_tasks(db: Session, user: m.User, day: date, limit: int = 12) -> list[dict]:
    """
    امتیازدهی وزن‌دار V2 + سیگنال‌های V2.2.
    """
    cap = day_capacity(db, user, day)
    class_subject_ids = {c["subject_id"] for c in cap["classes"] if c["subject_id"]}

    goal = db.scalar(select(m.WeeklyGoal).where(
        m.WeeklyGoal.user_id == user.id, m.WeeklyGoal.week_start == jalali.week_start(day),
        m.WeeklyGoal.active.is_(True)))
    goal_nodes: set[int] = set()
    count_goal_open = False
    if goal:
        for item in db.scalars(select(m.WeeklyGoalItem).where(
                m.WeeklyGoalItem.goal_id == goal.id)).all():
            if item.goal_type == "topic" and item.node_id:
                goal_nodes.add(item.node_id)
            if item.goal_type == "count" and item.progress_value < item.target_value:
                count_goal_open = True

    taught_recent = {
        t.node_id: t.taught_at
        for t in db.scalars(select(m.TaughtTopic).where(
            m.TaughtTopic.user_id == user.id,
            m.TaughtTopic.taught_at >= day - timedelta(days=14))).all()
    }

    readiness_nodes: dict[int, tuple[str, int]] = {}
    for ue in db.scalars(select(m.UpcomingExam).where(
            m.UpcomingExam.user_id == user.id, m.UpcomingExam.exam_date >= day)).all():
        days_left = (ue.exam_date - day).days
        for t in db.scalars(select(m.UpcomingExamTopic).where(
                m.UpcomingExamTopic.upcoming_exam_id == ue.id)).all():
            prev = readiness_nodes.get(t.node_id)
            if not prev or days_left < prev[1]:
                readiness_nodes[t.node_id] = (ue.title, days_left)

    # همه leafهایی که بانک دارند
    node_ids = set()
    for ts in db.scalars(select(m.TestSet).where(m.TestSet.node_id.isnot(None))).all():
        node_ids.add(ts.node_id)
    node_ids |= goal_nodes | set(taught_recent) | set(readiness_nodes)

    out: list[dict] = []
    for node_id in node_ids:
        node = db.get(m.BookNode, node_id)
        if not node:
            continue
        book = db.get(m.Book, node.book_id)
        if not book or not book.active:
            continue
        stats = node_stats(db, user.id, node_id)
        if stats["total"] == 0 or stats["with_answer_key"] == 0:
            continue

        score = 0.0
        reasons: list[str] = []

        if node_id in goal_nodes:
            score += cfg.WEIGHT_TOPIC_GOAL
            reasons.append(f"هدف موضوعی هفته (+{cfg.WEIGHT_TOPIC_GOAL})")
        if stats["open_review"] > 0:
            share = min(1.0, stats["open_review"] / 10)
            add = cfg.WEIGHT_REVIEW_CRITICAL * share
            score += add
            reasons.append(f"{stats['open_review']} مورد باز در مرور (+{add:.0f})")
        if book.subject_id in class_subject_ids:
            score += cfg.WEIGHT_CLASS_ALIGNMENT + cfg.CLASS_DAY_BONUS
            reasons.append(f"امروز کلاس {book.subject.name} داری "
                           f"(+{cfg.WEIGHT_CLASS_ALIGNMENT}+{cfg.CLASS_DAY_BONUS} bonus)")
        parity = suggest_parity(db, user.id, node_id)
        score += cfg.WEIGHT_PARITY_OPPOSITE
        reasons.append(f"parity پیشنهادی: {'فرد' if parity == 'odd' else 'زوج'} "
                       f"(+{cfg.WEIGHT_PARITY_OPPOSITE})")
        if node_id in readiness_nodes:
            title, days_left = readiness_nodes[node_id]
            factor = 1.0 if days_left <= cfg.READINESS_DEADLINE_BOOST_DAYS else 0.6
            add = cfg.WEIGHT_DEADLINE * factor
            score += add
            reasons.append(f"امتحان «{title}» تا {days_left} روز دیگر (+{add:.0f})")
        if count_goal_open:
            score += cfg.WEIGHT_COUNT_GOAL
            reasons.append(f"هدف تعداد تست هفته (+{cfg.WEIGHT_COUNT_GOAL})")

        # V2.2 — تدریس‌شده با Coverage پایین (S5)
        if node_id in taught_recent:
            taught_at = taught_recent[node_id]
            fresh = (day - taught_at).days <= cfg.TAUGHT_RECENT_DAYS
            if stats["coverage"] < cfg.TAUGHT_LOW_COVERAGE_THRESHOLD:
                bonus = 12 if fresh else 6
                score += bonus
                reasons.append(
                    f"تدریس‌شده در {jalali.to_jalali_str(taught_at)} و Coverage "
                    f"{stats['coverage']*100:.0f}٪ (+{bonus})"
                )
        # هفته‌های آخر: وزن مرور در پنج‌شنبه/جمعه بالاتر
        if jalali.iran_weekday(day) in (5, 6) and stats["open_review"] > 0:
            score += 5
            reasons.append("پنج‌شنبه/جمعه وزن مرور بالاتر (+۵)")

        untouched = stats["total"] - stats["attempted"]
        if score <= 0:
            continue
        out.append({
            "node_id": node_id,
            "book_id": book.id,
            "book_title": book.title,
            "subject_id": book.subject_id,
            "subject": book.subject.name,
            "title": node.title,
            "full_title": node_full_title(db, node_id),
            "score": round(score, 1),
            "parity": parity,
            "suggested_count": min(10, max(5, untouched)) if untouched else 5,
            "coverage": stats["coverage"],
            "accuracy": stats["accuracy"],
            "untouched": untouched,
            "open_review": stats["open_review"],
            "reasons": reasons,
        })

    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]


def generate_plan(db: Session, user: m.User, day: date, replace: bool = False) -> dict:
    """ساخت Taskهای پیشنهادی روز — Taskهای manual دست‌نخورده می‌مانند."""
    if replace:
        for t in db.scalars(select(m.Task).where(
                m.Task.user_id == user.id, m.Task.planned_date == day,
                m.Task.status == "pending", m.Task.source_type == "planner",
                m.Task.manual_override.is_(False))).all():
            db.delete(t)
        db.flush()

    target = suggested_task_count(db, user, day)
    existing = db.scalar(select(func.count(m.Task.id)).where(
        m.Task.user_id == user.id, m.Task.planned_date == day,
        m.Task.status == "pending")) or 0
    need = max(0, target - existing)
    created: list[m.Task] = []
    if need:
        for cand in candidate_tasks(db, user, day, limit=need):
            task = m.Task(
                user_id=user.id, task_type="test",
                title=f"{cand['suggested_count']} تست — {cand['title']}",
                subject_id=cand["subject_id"], book_id=cand["book_id"], node_id=cand["node_id"],
                source_type="planner", priority=int(cand["score"]),
                quantity=cand["suggested_count"],
                estimated_minutes=max(20, cand["suggested_count"] * 3),
                parity=cand["parity"], planned_date=day,
                recommendation_reason=" • ".join(cand["reasons"]),
                planner_version=cfg.APP_VERSION,
                evidence_json={"score": cand["score"], "coverage": cand["coverage"]},
            )
            db.add(task)
            created.append(task)
    db.flush()

    total_tasks = db.scalar(select(func.count(m.Task.id)).where(
        m.Task.user_id == user.id, m.Task.planned_date == day,
        m.Task.status == "pending")) or 0
    state = current_state(db, user)
    cap = day_capacity(db, user, day)
    explanation = (
        f"امروز {total_tasks} کار پیشنهاد شد؛ ظرفیت رفتاری اخیر حدود {target} کار است و "
        f"آمادگی فعلی {state['readiness']:.2f} (اطمینان {state['confidence']:.2f})."
    )
    return {
        "created": len(created),
        "target_tasks": target,
        "explanation": explanation,
        "habit_advice": habit_advice(db, user, day, total_tasks),
        "capacity": cap,
        "state": state,
    }
