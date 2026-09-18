"""Analytics + dashboard.

The dashboard must answer, in this order: what matters now? what next? why? how
much realistic time is there? which exams? which goal? The UI may only show what
the engines computed here — no business logic in the presentation layer.
"""

from __future__ import annotations

import datetime as _dt
import statistics
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import now_utc, safe_div, today_local, week_start
from ..db import models
from ..domain.enums import TaskStatus
from . import (
    behaviour,
    capacity as capacity_service,
    common,
    goals as goal_service,
    learning,
    planner,
    priority,
    recommendation,
    review,
    rewards as rewards_service,
    tasks as tasks_service,
)


def dashboard(db: Session, user: models.User) -> dict:
    today = today_local()
    learning.retention_decay_all(db, user)
    day_payload = tasks_service.day_tasks(db, user, today)
    capacities = capacity_service.week_capacity(db, user, week_start(today))
    habits = capacity_service.habitual_advice(db, user)
    stats = overall_stats(db, user)
    return {
        "today": {
            "date": common.jdate(today),
            "date_long": common.jdate_long(today),
            "weekday": common.weekday_fa(today),
            "is_school_day": day_payload["capacity"]["is_school_day"],
        },
        "what_matters_now": {
            # every priority on the home screen carries its own "why" (the 4 questions)
            "priorities": [
                {**item, "why": priority.explain_priority(item)}
                for item in priority.compute_priorities(db, user, horizon="week", day=today, limit=5)
            ],
            "review": review.queue_stats(db, user),
        },
        "what_next": {
            "tasks": day_payload["tasks"],
            "over_capacity": day_payload["over_capacity"],
            "capacity": day_payload["capacity"],
        },
        "why": {
            "suggestions": recommendation.weekly_suggestions(db, user, day=today, limit=3),
            "quiet": recommendation.quiet_suggestions(db, user, day=today),
        },
        "time": {
            "realistic_minutes_today": day_payload["capacity"]["realistic_minutes"],
            "theoretical_minutes_today": day_payload["capacity"]["theoretical_minutes"],
            "planned_minutes_today": day_payload["capacity"]["planned_minutes"],
            "week": {
                "realistic_minutes": capacities["realistic_minutes"],
                "planned_minutes": capacities["planned_minutes"],
                "overloaded_days": capacities["overloaded_days"],
            },
            "explanation": day_payload["capacity"]["explanation"],
        },
        "exams": {"upcoming": _upcoming_exams(db, user)},
        "goals": goal_service.list_goals(db, user, refresh=False)[:3],
        "learning": stats,
        "review": review.queue_stats(db, user),
        "habits": habits,
        "midweek": planner.midweek_check(db, user, reference=today),
        "rewards": rewards_service.summary(db, user),
        "checkin": {
            "start_questions": behaviour.daily_questionnaire("start") if not _checkin_done(db, user, today, "start") else [],
            "end_questions": behaviour.daily_questionnaire("end") if not _checkin_done(db, user, today, "end") else [],
            "state": behaviour.current_state(db, user),
        },
        "today_brief": _today_brief(db, user, today, day_payload),
        "empty_state": _empty_state(db, user),
        "generated_at": common.jdatetime(now_utc()),
    }


def _today_brief(db: Session, user: models.User, today: _dt.date, day_payload: dict) -> dict:
    """V3.1 doc 08 — the home screen answers, in order:

    سلام → امروز → ۳ کار مهم → اولویت → آزمون نزدیک → وضعیت آمادگی → پیشنهاد بعدی.
    Everything here is read from the engines; nothing is recomputed or invented.
    """
    from . import calendar_service, exams as exams_service

    tasks = list(day_payload.get("tasks") or [])
    open_tasks = [task for task in tasks if task.get("status") not in {"completed", "skipped", "cancelled"}]
    important = sorted(
        open_tasks,
        key=lambda task: (
            -float(task.get("priority_score") or 0.0),
            task.get("planned_start_time") or "99:99",
            task.get("id") or 0,
        ),
    )[:3]

    exams = exams_service.upcoming_exams(db, user, days=30)
    nearest = exams[0] if exams else None
    nearest_brief = None
    if nearest:
        # readiness already travels with the upcoming payload (coverage+accuracy of
        # the marked topics, with the sample size behind it) — never recomputed here.
        nearest_brief = {
            "id": nearest.get("id"),
            "title": nearest.get("title"),
            "date": nearest.get("date"),
            "days_left": nearest.get("days_left"),
            "exam_type": nearest.get("exam_type"),
            "type_label": nearest.get("type_label"),
            "question_count": nearest.get("question_count"),
            "answer_key_count": nearest.get("answer_key_count"),
            "readiness": nearest.get("readiness"),
            "next_action": nearest.get("next_action"),
        }

    priorities = priority.compute_priorities(db, user, horizon="week", day=today, limit=1)
    top_priority = None
    if priorities:
        top = priorities[0]
        top_priority = {
            "topic_id": top["topic_id"],
            "topic_title": top.get("topic_title"),
            "score": top["score"],
            "confidence": top.get("confidence"),
            "reason": (top.get("top_reasons") or [{}])[0].get("human_text")
            or (top.get("top_reasons") or [{}])[0].get("label"),
        }

    if important:
        nxt = {
            "kind": "task",
            "title": important[0].get("title"),
            "route": "#/",
            "reason": "کار امروز با بیشترین اهمیت؛ انجام‌نشده باقی مانده است.",
        }
    elif top_priority:
        nxt = {
            "kind": "topic",
            "title": top_priority["topic_title"],
            "route": "#/sheet",
            "reason": top_priority["reason"] or "بالاترین اولویت محاسبه‌شده برای این هفته.",
        }
    elif nearest_brief:
        nxt = {
            "kind": "exam",
            "title": f"آماده‌سازی {nearest_brief['title']}",
            "route": "#/exams",
            "reason": "امتحان نزدیک ثبت شده و کاری برای امروز برنامه‌ریزی نشده است.",
        }
    else:
        nxt = {
            "kind": "none",
            "title": "هنوز داده‌ای برای پیشنهاد نیست",
            "route": "#/curriculum",
            "reason": "با تیک «تدریس‌شده»، بانک تست و ثبت یک امتحان، پیشنهادها ساخته می‌شوند.",
        }

    day_info = calendar_service.day_view(db, user, common.jdate(today))
    return {
        "greeting": f"سلام {user.display_name or 'دانش‌آموز'}",
        "date": common.jdate(today),
        "date_long": common.jdate_long(today),
        "weekday": common.weekday_fa(today),
        "is_holiday": day_info["is_holiday"],
        "holiday_titles": day_info["holiday_titles"],
        "important_tasks": important,
        "important_count": len(open_tasks),
        "priority": top_priority,
        "nearest_exam": nearest_brief,
        "next_action": nxt,
        "note": "این صفحه فقط نمایش می‌دهد؛ هر عدد از موتور خودش می‌آید و توضیحش همراه آن است.",
    }


def _upcoming_exams(db: Session, user: models.User) -> list[dict]:
    from . import exams as exams_service

    return exams_service.upcoming_exams(db, user, days=30)


def _checkin_done(db: Session, user: models.User, day: _dt.date, phase: str) -> bool:
    return bool(
        db.scalars(
            select(models.DailyCheckin).where(
                models.DailyCheckin.user_id == user.id,
                models.DailyCheckin.day == day,
                models.DailyCheckin.phase == phase,
            )
        ).first()
    )


def _empty_state(db: Session, user: models.User) -> dict:
    books = db.scalars(select(models.Book)).all()
    questions = db.scalar(select(func.count(models.Question.id))) or 0
    attempts = db.scalar(
        select(func.count(models.AttemptResult.id)).where(models.AttemptResult.user_id == user.id)
    ) or 0
    steps = []
    if not user.onboarding_completed:
        steps.append({"key": "onboarding", "label": "پرسشنامه کوتاه آشنایی (قابل توقف و ادامه)", "route": "#/onboarding"})
    if questions == 0:
        steps.append({"key": "question_bank", "label": "در هر کتاب، بانک تست مباحث را تعریف کن (افزودن بازه)", "route": "#/books"})
    created_exam = db.scalar(select(func.count(models.Exam.id)).where(models.Exam.user_id == user.id)) or 0
    if created_exam == 0:
        steps.append({"key": "exam", "label": "امتحان‌ها و آزمون‌های آزمایشی پیش‌رو را ثبت کن", "route": "#/exams"})
    goals = db.scalar(select(func.count(models.Goal.id)).where(models.Goal.user_id == user.id)) or 0
    if goals == 0:
        steps.append({"key": "goal", "label": "یک هدف سه‌ماهه بساز", "route": "#/goals"})
    if attempts == 0:
        steps.append({"key": "import", "label": "تست‌های قبلی را وارد کن تا از صفر شروع نکنی", "route": "#/import"})
        steps.append({"key": "session", "label": "یا یک جلسه تست جدید شروع کن", "route": "#/test"})
    return {
        "is_empty": not steps,
        "books": len(books),
        "questions": questions,
        "attempts": attempts,
        "steps": steps,
        "message": None if not steps else "برای شروع، این مسیرها آماده است. هیچ داده‌ای از خودمان نمی‌سازیم.",
    }


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


def overall_stats(db: Session, user: models.User) -> dict:
    row = db.execute(
        select(
            func.count(models.AttemptResult.id),
            func.sum(case((models.AttemptResult.result == "CORRECT", 1), else_=0)),
            func.sum(case((models.AttemptResult.result == "WRONG", 1), else_=0)),
            func.sum(case((models.AttemptResult.result == "UNANSWERED", 1), else_=0)),
            func.sum(case((models.AttemptResult.state == "NOT_ENTERED", 1), else_=0)),
            func.sum(case((models.AttemptResult.result == "NOT_EVALUABLE", 1), else_=0)),
        ).where(models.AttemptResult.user_id == user.id, models.AttemptResult.is_current.is_(True))
    ).first()
    attempts, correct, wrong, unanswered, not_entered, not_evaluable = [int(value or 0) for value in (row or [0] * 6)]
    answered = correct + wrong
    pool = db.scalar(select(func.count(models.Question.id)).where(models.Question.active.is_(True))) or 0
    seen = db.scalar(
        select(func.count(func.distinct(models.AttemptResult.question_id))).where(
            models.AttemptResult.user_id == user.id, models.AttemptResult.is_current.is_(True)
        )
    ) or 0
    states = list(db.scalars(select(models.LearningState).where(models.LearningState.user_id == user.id)))
    confidences = [state.confidence for state in states if state.confidence is not None]
    return {
        "attempts": attempts,
        "answered": answered,
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "not_entered": not_entered,
        "not_evaluable": not_evaluable,
        "volume": attempts,
        "accuracy": round(safe_div(correct, answered), 4) if answered else None,
        # coverage ≠ accuracy ≠ volume (V1 rule kept)
        "coverage": round(safe_div(seen, pool), 4) if pool else None,
        "pool_size": pool,
        "questions_seen": seen,
        "mean_confidence": round(statistics.fmean(confidences), 3) if confidences else None,
        "topics_with_state": len(states),
        "note": "پوشش، دقت و حجم سه مفهوم مستقل‌اند و هیچ‌کدام جای دیگری را نمی‌گیرد.",
    }


def book_progress(db: Session, user: models.User, book_id: int) -> dict:
    book = db.get(models.Book, book_id)
    if not book:
        from ..core.errors import NotFoundError

        raise NotFoundError("کتاب پیدا نشد.")
    topics = list(db.scalars(select(models.Topic).where(models.Topic.book_id == book_id).order_by(models.Topic.path)))
    states = {
        state.topic_id: state
        for state in db.scalars(
            select(models.LearningState).where(
                models.LearningState.user_id == user.id,
                models.LearningState.topic_id.in_([topic.id for topic in topics] or [0]),
            )
        )
    }
    taught = {
        row.topic_id
        for row in db.scalars(
            select(models.TaughtTopic).where(
                models.TaughtTopic.user_id == user.id,
                models.TaughtTopic.topic_id.in_([topic.id for topic in topics] or [0]),
                models.TaughtTopic.taught.is_(True),
            )
        )
    }
    parity = {
        row.topic_id: row.last_parity
        for row in db.scalars(
            select(models.NodeParityState).where(
                models.NodeParityState.user_id == user.id,
                models.NodeParityState.topic_id.in_([topic.id for topic in topics] or [0]),
            )
        )
    }
    children: dict[Optional[int], list[models.Topic]] = {}
    for topic in topics:
        children.setdefault(topic.parent_id, []).append(topic)

    def rollup(topic: models.Topic) -> dict:
        descendants = _descendants(topic.id, children)
        ids = [topic.id] + [item.id for item in descendants]
        pool = sum((states[i].evidence or {}).get("pool_size", 0) for i in ids if i in states)
        seen = sum((states[i].evidence or {}).get("distinct_questions_attempted", 0) for i in ids if i in states)
        answered = sum(states[i].answered or 0 for i in ids if i in states)
        correct = sum(states[i].correct or 0 for i in ids if i in states)
        wrong = sum(states[i].wrong or 0 for i in ids if i in states)
        unanswered = sum(states[i].unanswered or 0 for i in ids if i in states)
        last_attempts = [states[i].computed_at for i in ids if i in states and states[i].computed_at]
        row = {
            "topic_id": topic.id,
            "title": topic.title,
            "node_type": topic.node_type,
            "level": topic.depth,
            "questions": pool,
            "attempted": seen,
            "correct": correct,
            "wrong": wrong,
            "unanswered": unanswered,
            "coverage": round(safe_div(seen, pool), 4) if pool else None,
            "accuracy": round(safe_div(correct, answered), 4) if answered else None,
            "last_activity": common.jdatetime(max(last_attempts)) if last_attempts else None,
            "taught": topic.id in taught,
            "last_parity": parity.get(topic.id),
            "children": [rollup(child) for child in children.get(topic.id, [])],
        }
        return row

    return {
        "book": {"id": book.id, "title": book.title, "publisher": book.publisher},
        "rows": [rollup(topic) for topic in children.get(None, [])],
        "note": "پوشش و دقت جدا گزارش می‌شوند؛ «تدریس‌شده» هم وضعیت تسلط نیست.",
    }


def _descendants(topic_id: int, children: dict) -> list[models.Topic]:
    result = []
    stack = list(children.get(topic_id, []))
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(children.get(node.id, []))
    return result


def weakness_report(db: Session, user: models.User, limit: int = 15) -> list[dict]:
    """Weakness is multidimensional; never a raw wrong count."""
    states = list(db.scalars(select(models.LearningState).where(models.LearningState.user_id == user.id)))
    titles = {
        topic.id: topic.title
        for topic in db.scalars(select(models.Topic).where(models.Topic.id.in_([state.topic_id for state in states] or [0])))
    }
    rows = []
    for state in states:
        if not state.attempts:
            continue
        rows.append(
            {
                "topic_id": state.topic_id,
                "topic_title": titles.get(state.topic_id),
                "diagnosis": (state.evidence or {}).get("diagnosis_hint"),
                "coverage": state.coverage,
                "accuracy": state.accuracy,
                "confidence": state.confidence,
                "uncertainty": state.uncertainty,
                "repeated_error_signal": state.repeated_error_signal,
                "retention": state.retention_estimate,
                "recency_days": state.recency_days,
                "exam_readiness": state.exam_readiness,
                "prerequisite_health": state.prerequisite_health,
                "why": _weakness_reason(state),
                "suggested_action": _weakness_action(state),
            }
        )
    def sort_key(item: dict) -> float:
        accuracy = item["accuracy"] if item["accuracy"] is not None else 0.5
        coverage = item["coverage"] if item["coverage"] is not None else 0.5
        readiness = item["exam_readiness"] if item["exam_readiness"] is not None else 0.5
        return (1 - accuracy) + (1 - coverage) * 0.6 + (1 - readiness) * 0.5

    rows.sort(key=sort_key, reverse=True)
    return rows[:limit]


def _weakness_reason(state: models.LearningState) -> str:
    diagnosis = (state.evidence or {}).get("diagnosis_hint")
    mapping = {
        "LOW_COVERAGE_GOOD_ACCURACY": "دامنه دیده‌شده کم است، اما عملکرد روی همین بخش خوب بوده.",
        "GOOD_COVERAGE_WEAK_ACCURACY": "دامنه خوب است اما کیفیت پاسخ‌ها نیاز به تقویت دارد.",
        "LOW_COVERAGE_AND_WEAK": "هم پوشش کم است و هم دقت پایین — احتمال ضعف پایه‌ای یا پیش‌نیاز.",
        "UNCERTAIN_NEEDS_DIAGNOSTIC": "شواهد کافی نیست؛ یک تشخیص کوتاه بهتر از تمرین انبوه است.",
        "NO_EVIDENCE": "هیچ شاهدی نداریم؛ نبود داده با صفر اشتباه گرفته نمی‌شود.",
        "ON_TRACK": "وضعیت متعادل است.",
    }
    return mapping.get(diagnosis, "شواهد این مبحث محدود است.")


def _weakness_action(state: models.LearningState) -> str:
    if state.uncertainty and state.uncertainty > 0.5:
        return "تشخیص کوتاه (۶ تا ۱۲ سؤال)"
    if state.repeated_error_signal and state.repeated_error_signal > 0.25:
        return "بازبینی خطاهای تکراری"
    if state.prerequisite_health is not None and state.prerequisite_health < 0.45:
        return "مرور پیش‌نیاز"
    if state.retention_estimate is not None and state.retention_estimate < 0.6:
        return "مرور فعال"
    if state.coverage is not None and state.coverage < 0.35:
        return "گسترش پوشش با تمرین آسان/متوسط"
    return "تمرین هدف‌دار"


def trends(db: Session, user: models.User, days: int = 30) -> dict:
    since = today_local() - _dt.timedelta(days=days)
    rows = db.execute(
        select(
            models.AttemptResult.attempted_on,
            func.count(models.AttemptResult.id),
            func.sum(case((models.AttemptResult.result == "CORRECT", 1), else_=0)),
            func.sum(case((models.AttemptResult.result == "WRONG", 1), else_=0)),
            func.sum(case((models.AttemptResult.result == "UNANSWERED", 1), else_=0)),
        )
        .where(
            models.AttemptResult.user_id == user.id,
            models.AttemptResult.is_current.is_(True),
            models.AttemptResult.attempted_on >= since,
        )
        .group_by(models.AttemptResult.attempted_on)
        .order_by(models.AttemptResult.attempted_on)
    ).all()
    task_rows = db.execute(
        select(
            models.StudyTask.planned_date,
            func.count(models.StudyTask.id),
            func.sum(case((models.StudyTask.status == TaskStatus.COMPLETED.value, 1), else_=0)),
        )
        .where(models.StudyTask.user_id == user.id, models.StudyTask.planned_date >= since)
        .group_by(models.StudyTask.planned_date)
    ).all()
    tasks_by_day = {day: (planned, completed) for day, planned, completed in task_rows if day}
    series = []
    for day, total, correct, wrong, unanswered in rows:
        planned, completed = tasks_by_day.get(day, (0, 0))
        series.append(
            {
                "date": common.jdate(day),
                "weekday": common.weekday_fa(day),
                "attempts": int(total or 0),
                "correct": int(correct or 0),
                "wrong": int(wrong or 0),
                "unanswered": int(unanswered or 0),
                "accuracy": round(safe_div(int(correct or 0), int(correct or 0) + int(wrong or 0)), 3)
                if (correct or wrong) else None,
                "tasks_planned": int(planned or 0),
                "tasks_completed": int(completed or 0),
            }
        )
    return {
        "from": common.jdate(since),
        "to": common.jdate(today_local()),
        "series": series,
        "summary": {
            "days_with_activity": len(series),
            "attempts": sum(item["attempts"] for item in series),
            "mean_accuracy": round(
                statistics.fmean([item["accuracy"] for item in series if item["accuracy"] is not None]), 3
            ) if any(item["accuracy"] is not None for item in series) else None,
        },
        "note": "همه تاریخ‌ها شمسی و هفته از شنبه است.",
    }


def topic_history(db: Session, user: models.User, topic_id: int, limit: int = 40) -> dict:
    attempts = list(
        db.scalars(
            select(models.AttemptResult)
            .where(
                models.AttemptResult.user_id == user.id,
                models.AttemptResult.topic_id == topic_id,
                models.AttemptResult.is_current.is_(True),
            )
            .order_by(models.AttemptResult.evaluated_at.desc())
            .limit(limit)
        )
    )
    questions = {
        question.id: question.sequence_no
        for question in db.scalars(
            select(models.Question).where(models.Question.id.in_([a.question_id for a in attempts] or [0]))
        )
    }
    state = db.scalars(
        select(models.LearningState).where(
            models.LearningState.user_id == user.id, models.LearningState.topic_id == topic_id
        )
    ).first()
    return {
        "topic_id": topic_id,
        "state": {
            "accuracy": state.accuracy if state else None,
            "coverage": state.coverage if state else None,
            "confidence": state.confidence if state else None,
            "retention": state.retention_estimate if state else None,
            "diagnosis": (state.evidence or {}).get("diagnosis_hint") if state else None,
        },
        "attempts": [
            {
                "id": attempt.id,
                "sequence_no": questions.get(attempt.question_id),
                "state": attempt.state,
                "result": attempt.result,
                "selected_choice": attempt.selected_choice,
                "answer_key": attempt.answer_key_value,
                "date": common.jdate(attempt.attempted_on),
                "session_id": attempt.session_id,
                "source": attempt.source,
            }
            for attempt in attempts
        ],
    }
