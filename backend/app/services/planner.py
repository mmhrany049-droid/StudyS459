"""Weekly planner.

Pipeline (matches the V3 master specification step by step):

1 load context → 2 exams → 3 goals → 4 taught topics → 5 learning state →
6 review → 7 priority → 8 priority suggestions (user decides) → 9 adaptive
questions (only high information value) → 10 capacity → 11 interventions →
12 duration → 13 allocation → 14 balance exam/goal/review/coverage →
15 overload check → 16 explanation → 17 plan → 18 manual edit → 19 finalize.

Two guarantees:

* the auto-planner never overwrites a task with ``manual_override`` unless the
  user explicitly asks for a rebuild;
* if the plan cannot be fully honoured, the system says so and explains, instead
  of silently producing an impossible week.
"""

from __future__ import annotations

import datetime as _dt
import statistics
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.errors import NotFoundError, ValidationError
from ..core.timeutil import clamp, now_utc, safe_div, today_local, week_end, week_label_fa, week_start
from ..db import models
from ..domain.enums import (
    INTERVENTION_LABELS_FA,
    InterventionType,
    PlanningStatus,
    TaskSource,
    TaskStatus,
    TaskType,
)
from . import capacity as capacity_service
from . import common, learning, priority, recommendation, review, selection, tasks as tasks_service

MODEL_VERSION = config.MODEL_VERSION

STAGES = [
    {"key": "context", "label": "بارگذاری شرایط هفته"},
    {"key": "exams", "label": "بررسی امتحان‌های پیش‌رو"},
    {"key": "goals", "label": "بررسی هدف‌های سه‌ماهه"},
    {"key": "taught", "label": "کنترل مباحث تدریس‌شده"},
    {"key": "learning", "label": "محاسبه وضعیت یادگیری"},
    {"key": "review", "label": "ساخت صف مرور"},
    {"key": "priority", "label": "محاسبه اولویت‌ها"},
    {"key": "capacity", "label": "تخمین ظرفیت واقع‌بینانه"},
    {"key": "interventions", "label": "انتخاب نوع مداخله"},
    {"key": "duration", "label": "برآورد بازه زمان"},
    {"key": "allocation", "label": "تخصیص کار به روزها"},
    {"key": "balance", "label": "توازن امتحان/هدف/مرور/پوشش"},
    {"key": "overload", "label": "بررسی بار زیاد"},
    {"key": "explain", "label": "آماده‌سازی توضیح‌ها"},
    {"key": "plan", "label": "ساخت برنامه نهایی"},
]


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


def create_session(db: Session, user: models.User, payload: Optional[dict] = None) -> models.PlanningSession:
    payload = payload or {}
    reference = common.parse_date_if_string(payload.get("week_start")) or today_local()
    start = week_start(reference)
    existing = db.scalars(
        select(models.PlanningSession).where(
            models.PlanningSession.user_id == user.id,
            models.PlanningSession.week_start == start,
            models.PlanningSession.status.not_in([PlanningStatus.DISCARDED.value]),
        )
    ).first()
    if existing and not payload.get("force_new"):
        return existing
    session = models.PlanningSession(
        user_id=user.id,
        week_start=start,
        week_end=week_end(start),
        status=PlanningStatus.INTERVIEW.value,
        seed=payload.get("seed") or int(start.strftime("%Y%m%d")),
        planner_version=MODEL_VERSION,
        animation_stages={"stages": STAGES, "completed": []},
    )
    db.add(session)
    db.flush()
    refresh_context(db, user, session)
    return session


def refresh_context(db: Session, user: models.User, session: models.PlanningSession) -> dict:
    """Steps 1-8: context, exams, goals, taught, learning state, review, priority."""
    week = [session.week_start + _dt.timedelta(days=offset) for offset in range(7)]
    exams = [
        exam
        for exam in db.scalars(
            select(models.Exam).where(
                models.Exam.user_id == user.id,
                models.Exam.status.in_(["planned", "in_progress"]),
                models.Exam.exam_date >= session.week_start,
            )
        )
        if exam
    ]
    goals = list(db.scalars(select(models.Goal).where(models.Goal.user_id == user.id, models.Goal.status == "active")))
    review_stats = review.queue_stats(db, user)
    suggestions = recommendation.weekly_suggestions(db, user, day=session.week_start, limit=6)
    decisions = {
        common.to_int(item.get("topic_id")): item
        for item in ((session.priority_suggestions or {}).get("user_decisions") or [])
        if item.get("topic_id")
    }
    if decisions:
        # user decisions win over the automatic ordering (never silently ignored)
        for suggestion in suggestions:
            decision = decisions.get(common.to_int(suggestion.get("topic_id")))
            if not decision:
                continue
            suggestion["user_decision"] = decision.get("decision") or "accept"
            suggestion["user_note"] = decision.get("note")
            if suggestion["user_decision"] == "increase":
                suggestion["score"] = min(1.0, float(suggestion["score"]) * 1.15)
            elif suggestion["user_decision"] == "decrease":
                suggestion["score"] = float(suggestion["score"]) * 0.8
        suggestions = [s for s in suggestions if (s.get("user_decision") or "accept") != "reject"]
        suggestions.sort(key=lambda item: item["score"], reverse=True)
    session.interview = {
        **(session.interview or {}),
        "context": {
            "exams": [
                {"id": exam.id, "title": exam.title, "date": common.jdate(exam.exam_date), "type": exam.exam_type}
                for exam in exams
            ],
            "goals": [{"id": goal.id, "title": goal.title, "date": common.jdate(goal.target_date)} for goal in goals],
            "review": review_stats,
            "days": [common.jdate(day) for day in week],
            "taught_topics": db.scalar(
                select(func.count(models.TaughtTopic.id)).where(
                    models.TaughtTopic.user_id == user.id, models.TaughtTopic.taught.is_(True)
                )
            ) or 0,
        },
    }
    known = {common.to_int(item.get("topic_id")) for item in suggestions}
    added = [
        item
        for item in decisions.values()
        if item.get("added_by_user") and common.to_int(item.get("topic_id")) not in known
    ]
    session.priority_suggestions = {
        **(session.priority_suggestions or {}),
        "items": suggestions + added,
        "generated_at": common.jdatetime(now_utc()),
        "question": "این مباحث به توجه بیشتری در این هفته نیاز دارند. تأیید، افزایش، کاهش یا رد کن.",
    }
    db.flush()
    return {
        "exams": exams,
        "goals": goals,
        "review": review_stats,
        "suggestions": suggestions,
    }


def adaptive_questions(db: Session, user: models.User, session: models.PlanningSession) -> list[models.PlanningQuestion]:
    """Ask only where the answer can materially change this week's plan."""
    existing = list(
        db.scalars(
            select(models.PlanningQuestion)
            .where(models.PlanningQuestion.planning_session_id == session.id)
            .order_by(models.PlanningQuestion.order_index)
        )
    )
    if existing:
        return existing
    context = (session.interview or {}).get("context", {})
    questions: list[dict] = []
    threshold = config.value("planning.question_information_threshold")

    # 1) capacity uncertainty: how much realistic time is there this week?
    history = capacity_service.completion_history(db, user, 21)
    answered_weeks = len({row["date"] for row in history})
    capacity_uncertainty = 1 - common.confidence_from_evidence(answered_weeks)
    if capacity_uncertainty >= threshold:
        questions.append(
            {
                "code": "weekly_realistic_time",
                "text": "این هفته در مجموع چقدر وقت واقعی و قابل اتکا برای مطالعه داری؟",
                "kind": "single_choice",
                "options": [
                    {"id": "low", "label": "کمتر از ۵ ساعت"},
                    {"id": "medium", "label": "حدود ۵ تا ۱۰ ساعت"},
                    {"id": "high", "label": "بیشتر از ۱۰ ساعت"},
                ],
                "because": "داده کافی از هفته‌های قبل نداریم و این عدد مستقیماً ظرفیت برنامه را تغییر می‌دهد.",
                "information_value": round(capacity_uncertainty, 3),
                "uncertainty_key": "capacity",
            }
        )

    # 2) fixed commitments that the calendar cannot see
    questions.append(
        {
            "code": "fixed_commitments",
            "text": "این هفته قرار/کلاس/اتفاقات خاصی داری که در تقویم ثبت نشده؟",
            "kind": "short_text",
            "options": [],
            "because": "این‌ها «فعالیت» هستند و از ظرفیت کم می‌کنند؛ کار عقب‌افتاده محسوب نمی‌شوند.",
            "information_value": 0.55,
            "uncertainty_key": "activities",
        }
    )

    # 3) exams: only ask when no exam is registered for the week
    if not context.get("exams"):
        questions.append(
            {
                "code": "week_exam",
                "text": "این هفته امتحان یا آزمون آزمایشی داری؟",
                "kind": "single_choice",
                "options": [
                    {"id": "none", "label": "نه"},
                    {"id": "school", "label": "امتحان مدرسه دارم"},
                    {"id": "mock", "label": "آزمون آزمایشی دارم"},
                ],
                "because": "امتحان نزدیک، اولویت مباحث مربوط را بالا می‌برد اما هدف‌های بلندمدت و مرور را حذف نمی‌کند.",
                "information_value": 0.7,
                "uncertainty_key": "exam",
            }
        )

    # 4) focus subject
    focus_uncertainty = 0.45 if len(context.get("goals", [])) == 0 else 0.3
    if focus_uncertainty >= threshold:
        questions.append(
            {
                "code": "focus_subject",
                "text": "این هفته کدام درس بیشترین اولویت را دارد؟",
                "kind": "single_choice",
                "options": [
                    {"id": str(subject.id), "label": subject.name}
                    for subject in db.scalars(select(models.Subject))
                ],
                "because": "بدون هدف فعال، تمرکز هفته را خودت تعیین کن تا سیستم بیش از حد از خودش تصمیم نگیرد.",
                "information_value": round(focus_uncertainty, 3),
                "uncertainty_key": "goal",
            }
        )

    # 5) energy pattern / fragile days
    questions.append(
        {
            "code": "fragile_days",
            "text": "کدام روزهای این هفته احتمال خستگی یا فشار بیشتری دارد؟",
            "kind": "multi_choice",
            "options": [
                {"id": str(index), "label": common.weekday_fa(session.week_start + _dt.timedelta(days=index))}
                for index in range(7)
            ],
            "because": "روز پرریسک باید بار سبک‌تری بگیرد، نه اینکه به‌عنوان شکست ثبت شود.",
            "information_value": 0.42,
            "uncertainty_key": "state",
        }
    )
    questions.append(
        {
            "code": "plan_style",
            "text": "این هفته برنامه دقیق‌تر می‌خواهی یا انعطاف‌پذیرتر؟",
            "kind": "single_choice",
            "options": [
                {"id": "exact", "label": "دقیق‌تر با تعداد مشخص"},
                {"id": "flexible", "label": "انعطاف‌پذیر، فقط تعداد کار"},
            ],
            "because": "سبک برنامه‌ریزی ترجیحی تو در شکل برنامه اثر می‌گذارد.",
            "information_value": 0.35,
            "uncertainty_key": "preference",
        }
    )

    questions = [q for q in questions if q["information_value"] >= threshold]
    questions.sort(key=lambda item: item["information_value"], reverse=True)
    questions = questions[: config.value("planning.max_adaptive_questions")]
    created = []
    for index, item in enumerate(questions):
        question = models.PlanningQuestion(
            planning_session_id=session.id,
            code=item["code"],
            text=item["text"],
            kind=item["kind"],
            options=item["options"],
            because=item["because"],
            information_value=item["information_value"],
            order_index=index,
            uncertainty_key=item["uncertainty_key"],
        )
        db.add(question)
        created.append(question)
    session.status = PlanningStatus.ADAPTIVE_QUESTIONS.value if created else PlanningStatus.PRIORITIES.value
    db.flush()
    return created


def answer_question(
    db: Session, user: models.User, session: models.PlanningSession, question_code: str, answer: dict, *, skipped: bool = False
) -> dict:
    question = db.scalars(
        select(models.PlanningQuestion).where(
            models.PlanningQuestion.planning_session_id == session.id, models.PlanningQuestion.code == question_code
        )
    ).first()
    if not question:
        raise NotFoundError("سؤال برنامه‌ریزی پیدا نشد.")
    row = models.PlanningAnswer(
        planning_question_id=question.id, user_id=user.id, answer=answer or {}, skipped=skipped, answered_at=now_utc()
    )
    db.add(row)
    session.interview = {
        **(session.interview or {}),
        "answers": {**((session.interview or {}).get("answers") or {}), question_code: {"answer": answer, "skipped": skipped}},
    }
    if question_code in {"focus_subject", "week_exam", "fixed_commitments", "fragile_days"}:
        # user reports are stored as data (activities/state), never as raw truth about ability
        common.observe(
            db, user.id, "planning_answer",
            payload={"code": question_code, "answer": answer, "skipped": skipped}, source="self_report",
        )
    if question_code == "fragile_days" and answer and not skipped:
        selected = answer.get("selected") or answer.get("value") or []
        if isinstance(selected, str):
            selected = [selected]
        for index in selected:
            try:
                day = session.week_start + _dt.timedelta(days=int(index))
            except (TypeError, ValueError):
                continue
            existing = db.scalars(
                select(models.SchoolDayOverride).where(
                    models.SchoolDayOverride.user_id == user.id, models.SchoolDayOverride.date == day
                )
            ).first()
            note = "کاربر این روز را پرریسک اعلام کرد."
            if existing:
                existing.reason = note
            else:
                db.add(
                    models.SchoolDayOverride(
                        user_id=user.id, date=day, is_school_day=(day.weekday() not in (3, 4)), reason=note
                    )
                )
    db.flush()
    return {"code": question_code, "skipped": skipped, "recorded": True}


def record_priority_feedback(db: Session, user: models.User, session: models.PlanningSession, items: list[dict]) -> dict:
    """Accept / Increase / Decrease / Reject / Add another — saved as user decisions."""
    stored = [
        {
            "topic_id": common.to_int(item.get("topic_id")),
            "decision": item.get("decision", "accept"),
            "note": item.get("note"),
            "added_by_user": bool(item.get("added_by_user")),
            "recorded_at": common.jdatetime(now_utc()),
        }
        for item in items
        if item.get("topic_id")
    ]
    session.priority_suggestions = {
        **(session.priority_suggestions or {}),
        "user_decisions": stored,
        "decided_at": common.jdatetime(now_utc()),
    }
    for item in stored:
        common.observe(
            db, user.id, "priority_feedback",
            payload=item, source="user",
        )
    session.status = PlanningStatus.ADAPTIVE_QUESTIONS.value
    db.flush()
    common.audit(
        db, "planning_priority_feedback", user_id=user.id, entity_type="planning_session", entity_id=session.id,
        after={"items": stored},
    )
    return {"recorded": len(stored), "note": "بازخورد اولویت‌ها به‌عنوان داده تصمیم کاربر ذخیره شد."}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_plan(db: Session, user: models.User, session: models.PlanningSession, *, rebuild: bool = False) -> dict:
    week = [session.week_start + _dt.timedelta(days=offset) for offset in range(7)]
    context = refresh_context(db, user, session)
    fragile_days = _fragile_days(db, user, session)
    plan_style = (((session.interview or {}).get("answers") or {}).get("plan_style") or {}).get("answer", {}).get("value")

    # 6-7: learning state + review + priority
    learning.rebuild_all(db, user)
    review_stats = context["review"]
    priorities = priority.compute_priorities(db, user, horizon="week", day=session.week_start, limit=24)
    priority.persist_snapshots(db, user, priorities, horizon="week", computed_for=session.week_start)

    # 10: capacity per day
    capacities = {}
    for day in week:
        payload = capacity_service.day_capacity(db, user, day)
        if day in fragile_days:
            payload["realistic_minutes"] = int(payload["realistic_minutes"] * 0.75)
            payload["adjusted_for"] = "روز پرریسک اعلام‌شده توسط کاربر"
        capacities[day] = payload

    # 11-12: intervention + duration per candidate
    candidates = _build_candidates(db, user, session, priorities, context, capacities, week)
    # 13-14: allocation with balance between exam / goal / review / coverage
    allocation, overload = _allocate(db, user, session, candidates, capacities, week, plan_style)
    explanation = _explain(session, allocation, capacities, context, overload)

    existing_auto = list(
        db.scalars(
            select(models.StudyTask).where(
                models.StudyTask.user_id == user.id,
                models.StudyTask.source == TaskSource.PLANNER.value,
                models.StudyTask.planned_date >= session.week_start,
                models.StudyTask.planned_date <= session.week_end,
                models.StudyTask.status == TaskStatus.PLANNED.value,
                models.StudyTask.manual_override.is_(False),
            )
        )
    )
    manual = list(
        db.scalars(
            select(models.StudyTask).where(
                models.StudyTask.user_id == user.id,
                models.StudyTask.planned_date >= session.week_start,
                models.StudyTask.planned_date <= session.week_end,
                models.StudyTask.manual_override.is_(True),
            )
        )
    )
    removed = 0
    for task in existing_auto:
        db.delete(task)
        removed += 1
    db.flush()

    created = []
    for item in allocation:
        task = tasks_service.create_task(
            db,
            user,
            {
                **item["task"],
                "source": TaskSource.PLANNER.value,
                "manual_override": False,
                "created_by": "planner",
                "planner_version": MODEL_VERSION,
                "evidence": item["evidence"],
            },
            planner_version=MODEL_VERSION,
        )
        created.append(task)

    session.status = PlanningStatus.READY.value
    session.auto_plan = {
        "week_start": common.jdate(session.week_start),
        "items": allocation,
        "generated_at": common.jdatetime(now_utc()),
        "removed_auto_tasks": removed,
    }
    session.plan = session.auto_plan
    session.overload = overload
    session.explanation = explanation
    session.capacity_snapshot_id = _store_week_capacity(db, user, session, capacities)
    session.animation_stages = {"stages": STAGES, "completed": [stage["key"] for stage in STAGES]}
    session.confidence = _plan_confidence(priorities, capacities)
    db.flush()
    common.observe(
        db, user.id, "plan_generated",
        payload={"session_id": session.id, "tasks": len(created), "overloaded": overload["has_overload"], "rebuild": rebuild},
        source="system",
    )
    return {
        "session_id": session.id,
        "status": session.status,
        "tasks_created": len(created),
        "auto_tasks_replaced": removed,
        "manual_tasks_preserved": len(manual),
        "overload": overload,
        "explanation": explanation,
        "stages": STAGES,
        "days": _plan_days(db, user, session),
        "confidence": session.confidence,
    }


def _fragile_days(db: Session, user: models.User, session: models.PlanningSession) -> set[_dt.date]:
    rows = db.scalars(
        select(models.SchoolDayOverride).where(
            models.SchoolDayOverride.user_id == user.id,
            models.SchoolDayOverride.date >= session.week_start,
            models.SchoolDayOverride.date <= session.week_end,
        )
    )
    return {row.date for row in rows if row.reason and "پرریسک" in (row.reason or "")}


def _build_candidates(
    db: Session,
    user: models.User,
    session: models.PlanningSession,
    priorities: list[dict],
    context: dict,
    capacities: dict,
    week: list[_dt.date],
) -> list[dict]:
    """Step 11-12-14: intervention + duration + balancing weights."""
    candidates: list[dict] = []
    exam_share = config.value("exam.mock_prep_share")
    nearest_exam = None
    for exam in context["exams"]:
        if exam.exam_date >= session.week_start:
            nearest_exam = exam
            break
    exam_topic_ids: set[int] = set()
    if nearest_exam:
        exam_topic_ids = {
            row.topic_id
            for row in db.scalars(
                select(models.ExamTopic).where(models.ExamTopic.exam_id == nearest_exam.id, models.ExamTopic.checked.is_(True))
            )
        }
    goal_topic_ids: set[int] = set()
    from . import goals as goal_service

    for goal in context["goals"]:
        goal_topic_ids |= set(goal_service.goal_scope_topics(db, goal))

    # review-driven candidates come first: review is cheap and protects retention
    review_items = review.open_items(db, user, limit=config.value("review.max_questions_per_session"))
    review_by_topic: dict[int, list[models.ReviewItem]] = {}
    for item in review_items:
        if item.topic_id:
            review_by_topic.setdefault(item.topic_id, []).append(item)
    for topic_id, items in sorted(review_by_topic.items(), key=lambda pair: -len(pair[1]))[:3]:
        count = min(len(items), config.value("recommendation.package_max_questions"))
        decision = recommendation.choose_intervention(db, user, topic_id)
        intervention = InterventionType.ERROR_REVIEW.value if any(
            item.priority == "critical" for item in items
        ) else InterventionType.REVIEW.value
        from . import duration as duration_service

        estimate = duration_service.estimate_for_task(
            db, user, task_type="review_session", question_count=count, topic_id=topic_id, intervention=intervention
        )
        topic = db.get(models.Topic, topic_id)
        candidates.append(
            {
                "topic_id": topic_id,
                "topic_title": topic.title if topic else None,
                "kind": "review",
                "intervention_type": intervention,
                "question_count": count,
                "minutes": estimate["point_minutes"],
                "duration_low": estimate["low_minutes"],
                "duration_high": estimate["high_minutes"],
                "duration_confidence": estimate["confidence"],
                "duration_method": estimate["method"],
                "priority_score": 0.75 + 0.05 * min(5, len(items)),
                "balance_weight": 1.0,
                "why": f"{len(items)} سؤال در صف مرور این مبحث",
                "source_items": [item.id for item in items][:25],
            }
        )

    # priority driven candidates
    for item in priorities:
        topic_id = item["topic_id"]
        decision = recommendation.choose_intervention(db, user, topic_id)
        intervention = decision["intervention"]
        if intervention == InterventionType.READ_LESSON.value:
            from . import duration as duration_service

            estimate = duration_service.estimate_for_task(db, user, task_type="read_lesson", question_count=None, topic_id=topic_id)
            count = 0
        else:
            count = recommendation.question_count_for(intervention)
            preview = selection.select_for_intervention(db, user, topic_id=topic_id, intervention=intervention, count=count)
            count = preview["count"] or 0
            from . import duration as duration_service

            estimate = duration_service.estimate_for_task(
                db, user, task_type="test_session", question_count=count, topic_id=topic_id, intervention=intervention
            )
        balance = 1.0
        if topic_id in exam_topic_ids:
            balance += exam_share
        if topic_id in goal_topic_ids:
            balance += 0.25
        candidates.append(
            {
                "topic_id": topic_id,
                "topic_title": item.get("topic_title"),
                "kind": "study",
                "intervention_type": intervention,
                "question_count": count,
                "minutes": estimate["point_minutes"],
                "duration_low": estimate["low_minutes"],
                "duration_high": estimate["high_minutes"],
                "duration_confidence": estimate["confidence"],
                "duration_method": estimate["method"],
                "priority_score": item["score"] * balance,
                "balance_weight": balance,
                "why": " / ".join(decision["reasons"][:1]) or item["top_reasons"][0]["label"],
                "priority_components": item["components"],
                "top_reasons": item["top_reasons"],
            }
        )
    candidates.sort(key=lambda item: item["priority_score"], reverse=True)
    return candidates


def _allocate(
    db: Session,
    user: models.User,
    session: models.PlanningSession,
    candidates: list[dict],
    capacities: dict,
    week: list[_dt.date],
    plan_style: Optional[str],
) -> tuple[list[dict], dict]:
    """Steps 13-15: put work on days, balance the mix, detect overload honestly."""
    max_tasks_per_day = config.value("planning.max_tasks_per_day")
    max_tasks_week = config.value("planning.max_tasks_per_week")
    remaining = {day: capacities[day]["realistic_minutes"] for day in week}
    used_tasks = {day: 0 for day in week}
    allocation: list[dict] = []
    kind_counter = {"review": 0, "study": 0}
    total_tasks = 0

    def pick_day(minutes: int, kind: str) -> Optional[_dt.date]:
        # prefer days with free capacity; spread review work early in the week
        ordered = sorted(week, key=lambda day: (used_tasks[day], -remaining[day]))
        if kind == "review":
            ordered = sorted(week, key=lambda day: (day, used_tasks[day]))
        for day in ordered:
            if used_tasks[day] >= max_tasks_per_day:
                continue
            if remaining[day] >= max(15, int(minutes * 0.7)):
                return day
        for day in ordered:
            if used_tasks[day] < max_tasks_per_day:
                return day
        return None

    for candidate in candidates:
        if total_tasks >= max_tasks_week:
            break
        day = pick_day(candidate["minutes"], candidate["kind"])
        if day is None:
            candidate["unplaced_reason"] = "ظرفیت هفته پر شده است."
            continue
        questions = candidate.get("question_count") or 0
        title = _task_title(candidate)
        task_payload = {
            "title": title,
            "task_type": TaskType.REVIEW_SESSION.value if candidate["kind"] == "review" else (
                TaskType.READ_LESSON.value if candidate["intervention_type"] == InterventionType.READ_LESSON.value
                else TaskType.TEST_SESSION.value
            ),
            "intervention_type": candidate["intervention_type"],
            "topic_id": candidate["topic_id"],
            "book_id": db.get(models.Topic, candidate["topic_id"]).book_id if db.get(models.Topic, candidate["topic_id"]) else None,
            "planned_date": day,
            "planned_question_count": questions or None,
            "planned_minutes": candidate["minutes"],
            "duration_low": candidate["duration_low"],
            "duration_high": candidate["duration_high"],
            "duration_confidence": candidate["duration_confidence"],
            "priority_score": candidate["priority_score"],
            "display_order": used_tasks[day],
            "parity": payload_parity(db, user, candidate["topic_id"]),
            "evidence": {
                "why": candidate["why"],
                "intervention_label": INTERVENTION_LABELS_FA.get(
                    InterventionType(candidate["intervention_type"]), candidate["intervention_type"]
                ),
                "duration_method": candidate.get("duration_method"),
                "priority_components": candidate.get("priority_components"),
                "top_reasons": candidate.get("top_reasons"),
                "plan_style": plan_style,
                "balance_weight": candidate.get("balance_weight"),
            },
        }
        allocation.append(
            {
                "task": task_payload,
                "evidence": task_payload["evidence"],
                "topic_id": candidate["topic_id"],
                "day": common.jdate(day),
                "minutes": candidate["minutes"],
                "kind": candidate["kind"],
            }
        )
        remaining[day] -= candidate["minutes"]
        used_tasks[day] += 1
        kind_counter[candidate["kind"]] = kind_counter.get(candidate["kind"], 0) + 1
        total_tasks += 1

    overload_days = []
    for day in week:
        planned = capacities[day]["planned_minutes"] + sum(
            item["minutes"] for item in allocation if item["task"]["planned_date"] == day
        )
        if planned > capacities[day]["realistic_minutes"]:
            overload_days.append(
                {
                    "date": common.jdate(day),
                    "planned_minutes": planned,
                    "realistic_minutes": capacities[day]["realistic_minutes"],
                    "excess": planned - capacities[day]["realistic_minutes"],
                }
            )
    unplaced = [item for item in candidates if item.get("unplaced_reason")]
    overload = {
        "has_overload": bool(overload_days),
        "days": overload_days,
        "unplaced_count": len(unplaced),
        "unplaced_topics": [item["topic_title"] for item in unplaced][:5],
        "policy": "هیچ کاری خودکار حذف یا کم نمی‌شود؛ فقط شفاف اعلام می‌کنیم چه چیزی جا نشد.",
        "message": (
            f"{len(overload_days)} روز بیش از ظرفیت واقع‌بینانه پر شده و {len(unplaced)} کار در هفته جا نشد."
            if overload_days or unplaced else "بار هفته با ظرفیت واقع‌بینانه هم‌خوان است."
        ),
    }
    if overload["has_overload"] or unplaced:
        # honest downgrade instead of silent over-planning
        for item in overload["days"]:
            item["suggestion"] = "می‌توانی کارهای با اولویت پایین‌تر را به هفته بعد یا روز خلوت‌تر منتقل کنی."
    return allocation, overload


def payload_parity(db: Session, user: models.User, topic_id: int) -> Optional[str]:
    from . import sessions as sessions_service

    last = db.scalars(
        select(models.NodeParityState).where(
            models.NodeParityState.user_id == user.id, models.NodeParityState.topic_id == topic_id
        )
    ).first()
    if not last or not last.last_parity:
        return config.value("selection.default_first_parity")
    return "even" if last.last_parity == "odd" else "odd"


def _task_title(candidate: dict) -> str:
    label = INTERVENTION_LABELS_FA.get(InterventionType(candidate["intervention_type"]), candidate["intervention_type"])
    topic = candidate.get("topic_title") or "مبحث"
    if candidate["question_count"]:
        return f"{label} — {topic} ({candidate['question_count']} سؤال)"
    return f"{label} — {topic}"


def _explain(session, allocation, capacities, context, overload) -> dict:
    by_kind: dict[str, int] = {}
    for item in allocation:
        by_kind[item["kind"]] = by_kind.get(item["kind"], 0) + 1
    total_minutes = sum(item["minutes"] for item in allocation)
    weekly_capacity = sum(day["realistic_minutes"] for day in capacities.values())
    return {
        "summary": (
            f"{len(allocation)} کار برای هفته ساخته شد "
            f"({by_kind.get('review', 0)} جلسه مرور و {by_kind.get('study', 0)} جلسه یادگیری) "
            f"با مجموع حدود {total_minutes} دقیقه در برابر ظرفیت واقع‌بینانه {weekly_capacity} دقیقه."
        ),
        "capacity_note": "ظرفیت از عملکرد واقعی گذشته تخمین زده شده است، نه از ساعت‌های آزاد تقویم.",
        "exams": [
            {"title": exam.title, "days_left": (exam.exam_date - session.week_start).days}
            for exam in context["exams"][:3]
        ],
        "goals": [goal.title for goal in context["goals"][:3]],
        "review_open": context["review"]["open"],
        "overload": overload,
        "what_can_i_change": [
            "هر کار را می‌توانی جابه‌جا، حذف، تقسیم یا ادغام کنی؛ تغییر دستی با منبع «کاربر» ثبت می‌شود.",
            "دکمه بازسازی برنامه کار تغییر‌داده‌شده توسط تو را overwrite نمی‌کند.",
            "وزن‌های اولویت در تنظیمات قابل مشاهده و تغییرند و منبع/اطمینان هر عدد ذخیره می‌شود.",
        ],
        "no_magic": "هیچ عددی در این برنامه هارد‌کد نشده؛ همه از رجیستری پارامترها با ذکر منبع می‌آیند.",
    }


def _store_week_capacity(db: Session, user: models.User, session: models.PlanningSession, capacities: dict) -> Optional[int]:
    day = session.week_start
    total_realistic = sum(item["realistic_minutes"] for item in capacities.values())
    row = db.scalars(
        select(models.CapacitySnapshot).where(
            models.CapacitySnapshot.user_id == user.id,
            models.CapacitySnapshot.date == day,
            models.CapacitySnapshot.source == "planning",
        )
    ).first()
    if row is None:
        row = models.CapacitySnapshot(user_id=user.id, date=day, source="planning")
        db.add(row)
    row.realistic_minutes = total_realistic
    row.theoretical_minutes = sum(item["theoretical_minutes"] for item in capacities.values())
    row.planned_minutes = sum(
        item["planned_minutes"] for item in capacities.values()
    )
    row.confidence = statistics.fmean([item["confidence"] for item in capacities.values()]) if capacities else 0.2
    row.factors = {"week": common.jdate(day), "days": [
        {"date": common.jdate(key), "realistic": value["realistic_minutes"], "theoretical": value["theoretical_minutes"]}
        for key, value in capacities.items()
    ]}
    row.evidence = {"note": "ظرفیت هفته از ظرفیت واقع‌بینانه روزها ساخته می‌شود."}
    row.model_version = MODEL_VERSION
    db.flush()
    return row.id


def _plan_confidence(priorities: list[dict], capacities: dict) -> float:
    priority_conf = statistics.fmean([item["confidence"] for item in priorities]) if priorities else 0.2
    capacity_conf = statistics.fmean([day["confidence"] for day in capacities.values()]) if capacities else 0.2
    return round(clamp(0.5 * priority_conf + 0.5 * capacity_conf), 3)


def _plan_days(db: Session, user: models.User, session: models.PlanningSession) -> list[dict]:
    days = []
    for offset in range(7):
        day = session.week_start + _dt.timedelta(days=offset)
        payload = tasks_service.day_tasks(db, user, day)
        days.append(payload)
    return days


# ---------------------------------------------------------------------------
# Manual edit, finalize, rebuild
# ---------------------------------------------------------------------------


def finalize(db: Session, user: models.User, session: models.PlanningSession) -> dict:
    tasks = list(
        db.scalars(
            select(models.StudyTask).where(
                models.StudyTask.user_id == user.id,
                models.StudyTask.planned_date >= session.week_start,
                models.StudyTask.planned_date <= session.week_end,
                models.StudyTask.status != TaskStatus.CANCELLED.value,
            )
        )
    )
    topic_titles = {
        topic.id: topic.title
        for topic in db.scalars(select(models.Topic).where(models.Topic.id.in_([t.topic_id for t in tasks if t.topic_id] or [0])))
    }
    session.plan = {
        **(session.plan or {}),
        "finalized": True,
        "items": [
            {
                "task_id": task.id,
                "title": task.title,
                "topic_id": task.topic_id,
                "topic_title": topic_titles.get(task.topic_id),
                "planned_date": common.jdate(task.planned_date),
                "planned_minutes": task.planned_minutes,
                "question_count": task.planned_question_count,
                "source": task.source,
                "manual_override": task.manual_override,
            }
            for task in tasks
        ],
        "finalized_at": common.jdatetime(now_utc()),
    }
    session.status = PlanningStatus.FINALIZED.value
    session.finalized_at = now_utc()
    db.flush()
    common.audit(
        db, "planning_finalized", user_id=user.id, entity_type="planning_session", entity_id=session.id,
        after={"tasks": len(tasks)},
    )
    return {
        "session_id": session.id,
        "status": session.status,
        "tasks": len(tasks),
        "manual_tasks": len([t for t in tasks if t.manual_override]),
        "days": _plan_days(db, user, session),
    }


def rebuild(db: Session, user: models.User, session: models.PlanningSession, *, confirm: bool = False) -> dict:
    manual_count = db.scalar(
        select(func.count(models.StudyTask.id)).where(
            models.StudyTask.user_id == user.id,
            models.StudyTask.planned_date >= session.week_start,
            models.StudyTask.planned_date <= session.week_end,
            models.StudyTask.manual_override.is_(True),
            models.StudyTask.status == TaskStatus.PLANNED.value,
        )
    ) or 0
    if manual_count and not confirm:
        return {
            "session_id": session.id,
            "rebuilt": False,
            "requires_confirmation": True,
            "manual_tasks": manual_count,
            "message": (
                f"{manual_count} کار در این هفته دستی تغییر کرده است. بازسازی بدون تأیید صریح انجام نمی‌شود "
                "(کارهای دستی هم حفظ می‌شوند)."
            ),
        }
    payload = generate_plan(db, user, session, rebuild=True)
    payload["rebuilt"] = True
    payload["manual_tasks_preserved"] = manual_count
    return payload


def session_payload(db: Session, user: models.User, session: models.PlanningSession) -> dict:
    questions = adaptive_questions(db, user, session)
    answers = {
        row.planning_question_id: row
        for row in db.scalars(select(models.PlanningAnswer).where(models.PlanningAnswer.user_id == user.id))
    }
    priorities = (session.priority_suggestions or {}).get("items", [])
    return {
        "id": session.id,
        "week_start": common.jdate(session.week_start),
        "week_end": common.jdate(session.week_end),
        "week_label": week_label_fa(session.week_start),
        "status": session.status,
        "context": (session.interview or {}).get("context", {}),
        "priority_suggestions": priorities,
        "priority_question": (session.priority_suggestions or {}).get("question"),
        "user_decisions": (session.priority_suggestions or {}).get("user_decisions", []),
        "questions": [
            {
                "id": question.id,
                "code": question.code,
                "text": question.text,
                "kind": question.kind,
                "options": question.options or [],
                "because": question.because,
                "information_value": question.information_value,
                "answered": bool(answers.get(question.id) and not answers[question.id].skipped),
                "answer": (answers.get(question.id).answer if answers.get(question.id) else None),
                "skipped": bool(answers.get(question.id) and answers[question.id].skipped),
            }
            for question in questions
        ],
        "answers": ((session.interview or {}).get("answers") or {}),
        "plan": session.plan or {},
        "auto_plan": session.auto_plan or {},
        "overload": session.overload or {},
        "explanation": session.explanation or {},
        "stages": (session.animation_stages or {}).get("stages", STAGES),
        "confidence": session.confidence,
        "finalized_at": common.jdatetime(session.finalized_at),
        "planner_version": session.planner_version,
    }


def current_session(db: Session, user: models.User, reference: Optional[_dt.date] = None) -> models.PlanningSession:
    reference = reference or today_local()
    start = week_start(reference)
    session = db.scalars(
        select(models.PlanningSession)
        .where(models.PlanningSession.user_id == user.id, models.PlanningSession.week_start == start)
        .order_by(models.PlanningSession.id.desc())
    ).first()
    if session is None:
        session = create_session(db, user, {"week_start": start})
    return session


def midweek_check(db: Session, user: models.User, reference: Optional[_dt.date] = None) -> dict:
    """Wednesday check (V2 rule): warn if weekly progress is below 50%."""
    reference = reference or today_local()
    start = week_start(reference)
    tasks = list(
        db.scalars(
            select(models.StudyTask).where(
                models.StudyTask.user_id == user.id,
                models.StudyTask.planned_date >= start,
                models.StudyTask.planned_date <= week_end(start),
                models.StudyTask.status != TaskStatus.CANCELLED.value,
            )
        )
    )
    planned = len(tasks)
    completed = len([task for task in tasks if task.status == TaskStatus.COMPLETED.value])
    ratio = safe_div(completed, planned)
    is_check_day = common.weekday_fa(reference) == config.value("planning.midweek_check_weekday")
    warning = None
    multiplier = 1.0
    if planned and ratio is not None and ratio < config.value("planning.midweek_progress_threshold") and reference > start:
        warning = (
            f"تا اینجا {round(ratio * 100)}٪ کارهای هفته انجام شده است؛ برای رسیدن به هدف هفته "
            f"وزن کارهای حساس در روزهای پایانی {config.value('planning.catchup_multiplier')} برابر می‌شود "
            "(بدون اینکه چیزی دستوری شود)."
        )
        multiplier = config.value("planning.catchup_multiplier")
    return {
        "week_start": common.jdate(start),
        "is_check_day": is_check_day,
        "planned": planned,
        "completed": completed,
        "progress": round(ratio, 3) if ratio is not None else None,
        "threshold": config.value("planning.midweek_progress_threshold"),
        "catchup_multiplier": multiplier,
        "warning": warning,
    }
