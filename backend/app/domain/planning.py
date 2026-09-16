"""موتور برنامه‌ریزی — V2.1 (20_PLANNING_ENGINE_V2_1).

ورودی: goals + planner V1 + review V2 + classes + calendar + personality +
behavior + current_state + capacity + weekly interview + available time.

وزن‌های ثابت V2 (دست‌نخورده):
- هدف موضوعی هفته: ۳۵
- Review بحرانی: ۲۵
- هم‌راستایی کلاس روز: ۱۵
- parity مخالف: ۱۰
- deadline: ۱۰
- هدف تعداد: ۵
- bonus درس کلاس روز: +۱۵
- پنج‌شنبه/جمعه: کارهای goal-critical ×۱٫۵
- چهارشنبه: چک میانی — اگر پیشرفت هدف < ۵۰٪ → هشدار + وزن ۱٫۵ در پنج‌شنبه/جمعه

لایهٔ رفتاری فقط در انتخاب ظرفیت/تعداد/ترتیب اثر می‌گذارد.
خروجی: پیشنهاد توضیح‌پذیر با reason + confidence — نه برنامهٔ اجباری.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.config as cfg
from app.domain import behavior as behavior_mod
from app.domain import capacity as capacity_mod
from app.domain import state as state_mod
from app.domain.selection import suggest_parity
from app.jalali import is_school_day, today_tehran, week_days
from app.models import (Book, BookNode, DailyTaskPlacement, Question, QuestionAttempt,
                        QuestionTopicMap, ReviewQueueItem, Subject, Task, TestSet, User,
                        WeeklyGoal, WeeklyGoalItem)

PLANNER_VERSION = "2.1"


def _node_path(db: Session, node_id: int) -> str:
    parts = []
    cur = db.get(BookNode, node_id)
    while cur is not None:
        parts.append(cur.title)
        cur = db.get(BookNode, cur.parent_id) if cur.parent_id else None
    return " › ".join(reversed(parts))


def _subject_of_book(db: Session, book_id: int) -> str | None:
    b = db.get(Book, book_id)
    if b is None:
        return None
    s = db.get(Subject, b.subject_id)
    return s.name if s else None


def weekly_goal_items(db: Session, user_id: int, week_start):
    return list(db.execute(
        select(WeeklyGoalItem, WeeklyGoal)
        .join(WeeklyGoal, WeeklyGoal.id == WeeklyGoalItem.goal_id)
        .where(WeeklyGoal.user_id == user_id, WeeklyGoal.week_start == week_start,
               WeeklyGoal.active == True))  # noqa: E712
    )


def week_progress(db: Session, user_id: int, week_start) -> dict:
    """پیشرفت اهداف هفته (برای چک میانی چهارشنبه)."""
    items = weekly_goal_items(db, user_id, week_start)
    days = week_days(week_start)
    today = today_tehran()
    week_from = dt.datetime.combine(days[0], dt.time.min)
    week_to = dt.datetime.combine(days[-1] + dt.timedelta(days=1), dt.time.min)

    res = {r: c for r, c in db.execute(
        select(QuestionAttempt.result, func.count(QuestionAttempt.id))
        .where(QuestionAttempt.user_id == user_id,
               QuestionAttempt.answered_at >= week_from,
               QuestionAttempt.answered_at < week_to)
        .group_by(QuestionAttempt.result)).all()}
    attempted_week = sum(res.values())

    count_goal = next((gi for gi, g in items if gi.goal_type == "count"), None)
    topic_goal = next((gi for gi, g in items if gi.goal_type == "topic"), None)

    count_target = count_goal.target_value if count_goal else None
    count_progress = attempted_week / count_target if count_target else None

    topic_progress = None
    topic_node = None
    if topic_goal is not None and topic_goal.node_id:
        topic_node = db.get(BookNode, topic_goal.node_id)
        qids = db.scalars(
            select(QuestionTopicMap.question_id)
            .where(QuestionTopicMap.node_id == topic_goal.node_id)).all()
        if qids:
            cnt = db.scalar(
                select(func.count(QuestionAttempt.id)).where(
                    QuestionAttempt.user_id == user_id,
                    QuestionAttempt.question_id.in_(qids),
                    QuestionAttempt.answered_at >= week_from,
                    QuestionAttempt.answered_at < week_to)) or 0
            topic_progress = cnt / topic_goal.target_value if topic_goal.target_value else None

    midweek_warning = None
    if days[0] <= today <= days[6] and today >= days[cfg.MIDWEEK_CHECK_DAY]:
        prog = topic_progress if topic_progress is not None else count_progress
        if prog is not None and prog < cfg.MIDWEEK_PROGRESS_THRESHOLD:
            midweek_warning = {
                "message": ("پیشرفت هدف هفتگی کمتر از ۵۰٪ است؛ در پنج‌شنبه و جمعه "
                            "وزن کارهای هدف‌محور ۱٫۵ برابر می‌شود."),
                "progress": round(prog, 2),
                "day": "چهارشنبه (چک میانی)",
            }

    return {
        "week_start": week_start.isoformat(),
        "count_target": count_target,
        "count_progress": round(count_progress, 3) if count_progress is not None else None,
        "topic_node": {"id": topic_node.id, "title": topic_node.title} if topic_node else None,
        "topic_progress": round(topic_progress, 3) if topic_progress is not None else None,
        "attempted_week": attempted_week,
        "midweek_warning": midweek_warning,
    }


def build_candidates(db: Session, user: User, d: dt.date, week_start) -> list[dict]:
    """تولید کاندیدهای تست روز با وزن‌های قطعی V2 + دلیل توضیح‌پذیر."""
    user_id = user.id
    items = weekly_goal_items(db, user_id, week_start)
    count_goal = next((gi for gi, g in items if gi.goal_type == "count"), None)
    topic_goal = next((gi for gi, g in items if gi.goal_type == "topic"), None)

    day_classes = capacity_mod.day_classes(db, user_id, d)
    class_subject_names = set()
    for c in day_classes:
        if c.subject_id:
            s = db.get(Subject, c.subject_id)
            if s:
                class_subject_names.add(s.name)

    critical_nodes: set[int] = set()
    rq = list(db.scalars(
        select(ReviewQueueItem).where(
            ReviewQueueItem.user_id == user_id,
            ReviewQueueItem.status == "pending",
            ReviewQueueItem.wrong_count >= cfg.REVIEW_CRITICAL_WRONG_COUNT)))
    if rq:
        qids = [r.entity_id for r in rq]
        rows = db.execute(
            select(QuestionTopicMap.question_id, QuestionTopicMap.node_id)
            .where(QuestionTopicMap.question_id.in_(qids))).all()
        for _, nid in rows:
            critical_nodes.add(nid)

    is_free_day = not is_school_day(d)
    is_catchup = d.weekday() in (3, 4)  # پنج‌شنبه/جمعه
    week_prog = week_progress(db, user_id, week_start)
    midweek_active = week_prog.get("midweek_warning") is not None

    candidates = []
    books = list(db.scalars(select(Book)))
    for book in books:
        subject_name = _subject_of_book(db, book.id)
        test_sets = list(db.scalars(select(TestSet).where(TestSet.book_id == book.id)))
        for ts in test_sets:
            if ts.node_id is None:
                continue
            node = db.get(BookNode, ts.node_id)
            if node is None:
                continue
            score = 0.0
            reasons = []

            # ۱) هدف موضوعی هفته: ۳۵
            if topic_goal is not None:
                match = (topic_goal.node_id == ts.node_id
                         or topic_goal.book_id == book.id
                         or (topic_goal.subject_id is not None and subject_name
                             and db.get(Subject, topic_goal.subject_id).name == subject_name))
                if match:
                    score += cfg.WEIGHT_TOPIC_GOAL
                    reasons.append("هدف موضوعی هفته")

            # ۲) Review بحرانی: ۲۵
            if ts.node_id in critical_nodes:
                score += cfg.WEIGHT_REVIEW_CRITICAL
                reasons.append("مرور بحرانی (غلط تکرارشده)")

            # ۳) هم‌راستایی با کلاس امروز: ۱۵
            if subject_name and subject_name in class_subject_names:
                score += cfg.WEIGHT_CLASS_ALIGNMENT
                reasons.append(f"کلاس {subject_name} امروز")

            # ۴) parity مخالف: ۱۰
            parity = suggest_parity(db, user_id, ts.node_id)
            has_history = db.scalar(
                select(func.count()).select_from(QuestionAttempt).where(
                    QuestionAttempt.user_id == user_id,
                    QuestionAttempt.question_id.in_(
                        select(Question.id).where(Question.test_set_id == ts.id)))
            )
            if has_history:
                score += cfg.WEIGHT_PARITY_OPPOSITE
                reasons.append("parity مخالف دفعهٔ قبل")

            # ۵) هدف تعداد: ۵
            if count_goal is not None:
                score += cfg.WEIGHT_COUNT_GOAL
                reasons.append("هدف تعداد تست هفته")

            # ۶) deadline: ۱۰ — افق جمعه
            if d.weekday() == 4:
                score += cfg.WEIGHT_DEADLINE
                reasons.append("افق جمعه")

            # bonus کلاس روز: +۱۵ (به امتیاز نهایی)
            if subject_name and subject_name in class_subject_names:
                score += cfg.CLASS_DAY_BONUS
                reasons.append("بونوس درس کلاس روز")

            # پنج‌شنبه/جمعه: کارهای goal-critical ×۱٫۵
            if is_catchup and "هدف موضوعی هفته" in reasons:
                score *= cfg.CATCHUP_GOAL_WEIGHT_MULTIPLIER
                reasons.append("وزن جبرانی پنج‌شنبه/جمعه")
                if midweek_active:
                    score *= cfg.CATCHUP_GOAL_WEIGHT_MULTIPLIER
                    reasons.append("هشدار چک میانی چهارشنبه")

            ts_label = ts.title if ts.title.startswith("تست") else f"تست {ts.title}"
            candidates.append({
                "test_set_id": ts.id, "book_id": book.id, "node_id": ts.node_id,
                "title": f"{ts_label} — {node.title}",
                "subject": subject_name,
                "score": round(score, 1), "reasons": reasons,
                "parity": parity,
                "path": _node_path(db, ts.node_id),
            })

    candidates.sort(key=lambda c: -c["score"])
    return candidates


def generate_week_plan(db: Session, user: User, week_start, rebuild: bool = False) -> dict:
    """تولید برنامهٔ پیشنهادی هفته — پیشنهاد، نه اجبار.

    - Taskهای manual_override هرگز overwrite نمی‌شوند.
    - تعداد کار روزانه از Capacity Estimator + وضعیت فعلی.
    - وعده‌ها ۶۰ تا ۱۲۰ دقیقه؛ تعداد تست داخل وعده قابل تغییر.
    """
    from app.domain.interview import planner_inputs

    user_id = user.id
    days = week_days(week_start)
    interview = planner_inputs(db, user, week_start)
    state = state_mod.current_state(db, user)
    energy = state["state"].get("energy")
    behav = behavior_mod.behavior_summary(db, user)
    proc = behav["procrastination"]

    if rebuild:
        old = db.execute(
            select(Task).where(Task.user_id == user_id,
                               Task.source == "planner")).scalars().all()
        for t in old:
            if not t.manual_override:
                db.delete(t)

    created = []
    explanations = []
    for d in days:
        info = capacity_mod.day_info(db, user_id, d)
        day_type = info["day_type"]
        rec = capacity_mod.recommended_task_count(db, user_id, day_type, energy)

        # مصاحبه: روزهای خسته → کمتر؛ پرانرژی → بیشتر
        adjust = 0
        if interview.get("available"):
            iran_dow = (d.weekday() - 5) % 7
            if iran_dow in (interview.get("tired_days") or []):
                adjust -= 1
            if iran_dow in (interview.get("high_energy_days") or []):
                adjust += 1
        # الگوی اهمال‌کاری شناسایی‌شده → بار سبک‌تر در روزهای مدرسه
        if proc.get("pattern_detected") and day_type == "school":
            adjust -= 1
        n_tasks = max(1, rec["recommended_tasks"] + adjust)

        cands = build_candidates(db, user, d, week_start)
        if interview.get("priority_subject"):
            for c in cands:
                if c["subject"] == interview["priority_subject"]:
                    c["score"] += 10
                    c["reasons"].append("اولویت اعلام‌شده در مصاحبهٔ هفته")
            cands.sort(key=lambda c: -c["score"])

        existing = db.execute(
            select(Task).join(DailyTaskPlacement, DailyTaskPlacement.task_id == Task.id)
            .where(DailyTaskPlacement.date == d, Task.user_id == user_id,
                   Task.status.in_(("planned", "in_progress")))
        ).scalars().all()

        take = max(0, n_tasks - len(existing))
        for c in cands[:take]:
            est = min(cfg.SESSION_BLOCK_MAX_MINUTES,
                      max(cfg.SESSION_BLOCK_MIN_MINUTES, c.get("score", 50)))
            qcount = 15 if day_type == "school" else 20
            if proc.get("pattern_detected"):
                qcount = min(qcount, 10)  # entry point کوچک‌تر برای الگوی اهمال‌کاری
            task = Task(
                user_id=user_id, task_type="test",
                title=f"{c['subject'] or ''} — {c['title']}".strip(),
                source_type="goal", source="planner",
                priority=int(max(1, min(10, round(c["score"] / 10)))),
                estimated_minutes=est, due_at=d, status="planned",
                book_id=c["book_id"], node_id=c["node_id"],
                question_count=qcount, parity=c["parity"], timed=False,
                recommendation_reason=" + ".join(c["reasons"]) if c["reasons"] else "پیشنهاد برنامه‌ریز",
                planner_version=PLANNER_VERSION,
                evidence_json={
                    "confidence": round(min(0.9, 0.3 + rec["confidence"]), 2),
                    "evidence_count": rec["evidence_count"] + rec["active_days"],
                    "signals": c["reasons"],
                    "capacity_basis": rec["estimated_capacity"],
                },
                created_by="planner", updated_by="planner",
            )
            db.add(task)
            db.flush()
            db.add(DailyTaskPlacement(task_id=task.id, date=d, position=0))
            created.append({"id": task.id, "date": d.isoformat(), "title": task.title})

        explanations.append({
            "date": d.isoformat(),
            "day_type": day_type,
            "recommended_tasks": n_tasks,
            "basis": (
                f"ظرفیت تخمینی {rec['estimated_capacity']} کار "
                f"(confidence {round(rec['confidence'], 2)}؛ "
                f"{'محافظه‌کارانه — هنوز ۳۰ روز داده نداری' if rec['conservative'] else 'بر پایهٔ دادهٔ واقعی'})"
                + (f"؛ انرژی فعلی {round(energy, 2)}" if energy is not None else "")
                + (f"؛ تعدیل مصاحبهٔ هفته: {adjust:+d}" if adjust else "")
            ),
        })

    behavior_mod.log_event(db, user_id, "plan_generated", {
        "week_start": week_start.isoformat(), "rebuild": rebuild,
        "tasks_created": len(created)})

    return {
        "week_start": week_start.isoformat(),
        "created_tasks": created,
        "explanations": explanations,
        "planner_version": PLANNER_VERSION,
        "note": "این یک پیشنهاد است؛ هر Task را می‌توانی دستی ویرایش/حذف/جابه‌جا کنی.",
    }


def evaluate_past_week(db: Session, user: User, week_start) -> dict:
    """حلقهٔ یادگیری: Plan → Act → Observe → Evaluate → Update.

    ارزیابی هفته و به‌روزرسانی تدریجی ظرفیت (بدون سرزنش کاربر).
    """
    user_id = user.id
    days = week_days(week_start)
    result = {"week_start": week_start.isoformat(), "days": [], "updates": []}

    for d in days:
        tasks = db.execute(
            select(Task).join(DailyTaskPlacement, DailyTaskPlacement.task_id == Task.id)
            .where(DailyTaskPlacement.date == d, Task.user_id == user_id,
                   Task.status != "cancelled")).scalars().all()
        if not tasks:
            continue
        completed = sum(1 for t in tasks if t.status == "completed")
        completion_rate = completed / len(tasks)
        day_type = "school" if is_school_day(d) else "free"

        if d < today_tehran():
            capacity_mod.update_capacity_from_observation(db, user_id, day_type, completed)

        result["days"].append({
            "date": d.isoformat(), "day_type": day_type,
            "planned": len(tasks), "completed": completed,
            "completion_rate": round(completion_rate, 2),
        })

    all_rates = [x["completion_rate"] for x in result["days"]]
    avg = sum(all_rates) / len(all_rates) if all_rates else None
    if avg is not None:
        if avg < 0.5:
            message = ("بار این هفته بیشتر از ظرفیت واقعی بوده است؛ ظرفیت تخمینی کاهش یافت. "
                       "این یادگیری سیستم است، نه خطای تو.")
        elif avg > 0.9:
            message = "برنامه‌ها تقریباً کامل انجام شد؛ افزایش تدریجی بار در هفتهٔ بعد پیشنهاد می‌شود."
        else:
            message = "نرخ تکمیل متعادل است؛ ظرفیت با همین روند به‌تدریج تنظیم می‌شود."
        result["updates"].append({"avg_completion_rate": round(avg, 2), "message": message})

    behavior_mod.log_event(db, user_id, "week_evaluated", {
        "week_start": week_start.isoformat(), "avg_completion": avg})
    return result
