"""Goal engine: ~3 month goals decomposed 3-month → month → week → day → task.

Tracked per goal: baseline, target, milestones, current state, multidimensional
progress (coverage / accuracy / readiness) and confidence. When actual progress
deviates from the plan, *future* milestones are adapted — never silently ignored.
"""

from __future__ import annotations

import datetime as _dt
import statistics
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.errors import NotFoundError, ValidationError
from ..core.timeutil import clamp, safe_div, today_local
from ..db import models
from . import common

MODEL_VERSION = config.MODEL_VERSION

METRIC_LABELS = {
    "coverage": "پوشش",
    "accuracy": "دقت",
    "readiness": "آمادگی",
    "question_count": "تعداد سؤال",
}


def goal_scope_topics(db: Session, goal: models.Goal) -> list[int]:
    """Every topic this goal covers, from the single-node fields and the scope lists.

    A goal may be scoped to several books/topics; the union is explicit so the
    same function drives progress, planning and candidate tasks.
    """
    scope = goal.scope or {}
    topic_ids: set[int] = set()

    def _subtree(topic: models.Topic) -> set[int]:
        return {topic.id} | set(
            db.scalars(select(models.Topic.id).where(models.Topic.path.like(f"{topic.path}{topic.id}/%")))
        )

    for raw_topic_id in [goal.topic_id, *(scope.get("topic_ids") or [])]:
        topic = db.get(models.Topic, common.to_int(raw_topic_id)) if raw_topic_id else None
        if topic:
            topic_ids |= _subtree(topic)

    for raw_book_id in [goal.book_id, *(scope.get("book_ids") or [])]:
        if raw_book_id:
            topic_ids |= set(
                db.scalars(select(models.Topic.id).where(models.Topic.book_id == common.to_int(raw_book_id)))
            )

    for raw_subject_id in [goal.subject_id, *(scope.get("subject_ids") or [])]:
        if raw_subject_id:
            topic_ids |= set(
                db.scalars(
                    select(models.Topic.id)
                    .join(models.Book, models.Book.id == models.Topic.book_id)
                    .where(models.Book.subject_id == common.to_int(raw_subject_id))
                )
            )
    return sorted(topic_ids)


def current_metrics(db: Session, user: models.User, goal: models.Goal) -> dict:
    topic_ids = goal_scope_topics(db, goal)
    if not topic_ids:
        return {"coverage": None, "accuracy": None, "readiness": None, "question_count": 0, "confidence": 0.0}
    states = list(
        db.scalars(
            select(models.LearningState).where(
                models.LearningState.user_id == user.id, models.LearningState.topic_id.in_(topic_ids)
            )
        )
    )
    attempted = sum((state.evidence or {}).get("distinct_questions_attempted", 0) for state in states)
    pool = sum((state.evidence or {}).get("pool_size", 0) for state in states)
    answered = sum(state.answered or 0 for state in states)
    correct = sum(state.correct or 0 for state in states)
    confidences = [state.confidence for state in states if state.confidence is not None]
    readiness_values = [state.exam_readiness for state in states if state.exam_readiness is not None]
    return {
        "coverage": round(safe_div(attempted, pool), 4) if pool else None,
        "accuracy": round(safe_div(correct, answered), 4) if answered else None,
        "readiness": round(statistics.fmean(readiness_values), 4) if readiness_values else None,
        "question_count": answered,
        "attempted_questions": attempted,
        "pool_size": pool,
        "confidence": round(statistics.fmean(confidences), 3) if confidences else 0.0,
    }


def create_goal(db: Session, user: models.User, payload: dict) -> models.Goal:
    start = common.parse_date_if_string(payload.get("start_date")) or today_local()
    target_date = common.parse_date_if_string(payload.get("target_date"))
    if not target_date:
        target_date = start + _dt.timedelta(days=config.value("goal.horizon_days"))
    goal = models.Goal(
        user_id=user.id,
        title=payload.get("title") or "هدف سه‌ماهه",
        goal_type=payload.get("goal_type", "three_month"),
        subject_id=common.to_int(payload.get("subject_id")),
        book_id=common.to_int(payload.get("book_id")),
        topic_id=common.to_int(payload.get("topic_id")),
        scope={
            "subject_ids": [common.to_int(v) for v in (payload.get("subject_ids") or []) if common.to_int(v)],
            "book_ids": [common.to_int(v) for v in (payload.get("book_ids") or []) if common.to_int(v)],
            "topic_ids": [common.to_int(v) for v in (payload.get("topic_ids") or []) if common.to_int(v)],
        },
        start_date=start,
        target_date=target_date,
        baseline=payload.get("baseline") or {},
        target=payload.get("target") or {},
        progress={},
        notes=payload.get("notes"),
    )
    db.add(goal)
    db.flush()
    metrics = current_metrics(db, user, goal)
    goal.baseline = {**metrics, **(goal.baseline or {})}
    goal.progress = {"ratio": 0.0, "metrics": metrics, "computed_at": common.jdatetime(_now())}
    goal.confidence = metrics.get("confidence")
    db.flush()
    _create_objectives(db, user, goal, payload.get("objectives") or [])
    generate_milestones(db, user, goal)
    common.audit(db, "goal_created", user_id=user.id, entity_type="goal", entity_id=goal.id, after={"title": goal.title})
    return goal


def _create_objectives(db: Session, user: models.User, goal: models.Goal, objectives: list[dict]) -> list[models.GoalObjective]:
    created = []
    if not objectives:
        # default: coverage + accuracy on the goal scope (explicit, not invented numbers)
        objectives = [
            {"title": f"پوشش مباحث {goal.title}", "metric": "coverage", "target_value": 0.8},
            {"title": f"دقت مباحث {goal.title}", "metric": "accuracy", "target_value": 0.75},
        ]
    metrics = current_metrics(db, user, goal)
    for item in objectives:
        metric = item.get("metric", "coverage")
        objective = models.GoalObjective(
            goal_id=goal.id,
            topic_id=common.to_int(item.get("topic_id")) or goal.topic_id,
            title=item.get("title") or METRIC_LABELS.get(metric, metric),
            metric=metric,
            target_value=common.to_float(item.get("target_value")),
            current_value=metrics.get(metric),
            unit=item.get("unit"),
        )
        db.add(objective)
        created.append(objective)
    db.flush()
    return created


def generate_milestones(db: Session, user: models.User, goal: models.Goal) -> list[models.GoalMilestone]:
    """Decompose 3 months → months → weeks (days are produced by the planner)."""
    existing = list(db.scalars(select(models.GoalMilestone).where(models.GoalMilestone.goal_id == goal.id)))
    if existing:
        return existing
    start = goal.start_date or today_local()
    end = goal.target_date
    total_days = max(1, (end - start).days)
    months = max(1, min(3, round(total_days / 30)))
    created: list[models.GoalMilestone] = []
    for index in range(months):
        milestone_start = start + _dt.timedelta(days=round(total_days * index / months))
        milestone_end = start + _dt.timedelta(days=round(total_days * (index + 1) / months))
        milestone = models.GoalMilestone(
            goal_id=goal.id,
            level="month",
            title=f"ماه {index + 1} — {goal.title}",
            target_date=milestone_end,
            metrics={"coverage": round(0.8 * (index + 1) / months, 3), "accuracy": round(0.75 * (index + 1) / months, 3)},
            progress={},
        )
        db.add(milestone)
        db.flush()
        created.append(milestone)
        weeks = max(1, round((milestone_end - milestone_start).days / 7))
        for week_index in range(weeks):
            week_end = milestone_start + _dt.timedelta(days=round((milestone_end - milestone_start).days * (week_index + 1) / weeks))
            week = models.GoalMilestone(
                goal_id=goal.id,
                parent_id=milestone.id,
                level="week",
                title=f"هفته {week_index + 1} ماه {index + 1}",
                target_date=week_end,
                metrics={
                    "coverage": round(0.8 * (index * weeks + week_index + 1) / (months * weeks), 3),
                    "accuracy": round(0.75 * (index * weeks + week_index + 1) / (months * weeks), 3),
                },
            )
            db.add(week)
            created.append(week)
    db.flush()
    return created


def refresh_progress(db: Session, user: models.User, goal: models.Goal) -> dict:
    metrics = current_metrics(db, user, goal)
    objectives = list(db.scalars(select(models.GoalObjective).where(models.GoalObjective.goal_id == goal.id)))
    ratios = []
    for objective in objectives:
        current = metrics.get(objective.metric)
        objective.current_value = current
        if objective.target_value is None:
            continue
        baseline = (goal.baseline or {}).get(objective.metric) or 0.0
        span = objective.target_value - baseline
        ratio = clamp(safe_div((current or 0) - baseline, span) if span else 0.0)
        ratios.append(ratio)
        objective.status = "achieved" if (current or 0) >= objective.target_value else "in_progress" if ratio > 0.1 else "pending"
    ratio = round(statistics.fmean(ratios), 4) if ratios else 0.0
    elapsed_ratio = clamp(
        safe_div((today_local() - (goal.start_date or today_local())).days, max(1, (goal.target_date - (goal.start_date or today_local())).days))
    )
    deviation = ratio - elapsed_ratio
    goal.progress = {
        "ratio": ratio,
        "expected_ratio": round(elapsed_ratio, 4),
        "deviation": round(deviation, 4),
        "metrics": metrics,
        "updated_at": common.jdatetime(_now()),
        "status": (
            "ahead" if deviation > config.value("goal.progress_on_track_tolerance")
            else "behind" if deviation < -config.value("goal.progress_on_track_tolerance")
            else "on_track"
        ),
    }
    goal.confidence = metrics.get("confidence")
    goal.status = "achieved" if ratio >= 1 else goal.status
    db.flush()
    return goal.progress


def adapt_milestones(db: Session, user: models.User, goal: models.Goal) -> dict:
    """When actual progress deviates, future milestones are re-based (audited)."""
    progress = goal.progress or {}
    deviation = progress.get("deviation")
    if deviation is None or abs(deviation) < config.value("goal.progress_on_track_tolerance"):
        return {"adapted": 0, "message": "پیشرفت روی ریل است؛ تغییری در نقاط عطف آینده لازم نیست."}
    milestones = list(
        db.scalars(
            select(models.GoalMilestone)
            .where(models.GoalMilestone.goal_id == goal.id, models.GoalMilestone.target_date >= today_local())
            .order_by(models.GoalMilestone.target_date)
        )
    )
    factor = 1 - min(0.35, abs(deviation))
    if deviation > 0:
        factor = 1 + min(0.35, abs(deviation))
    adapted = 0
    for milestone in milestones:
        before = milestone.metrics or {}
        milestone.metrics = {key: round(clamp(value * factor), 4) for key, value in before.items()}
        milestone.adapted_from = {
            "previous_metrics": before,
            "deviation": deviation,
            "adapted_at": common.jdatetime(_now()),
            "reason": "انحراف پیشرفت واقعی از برنامه؛ نقاط عطف آینده بازتنظیم شد.",
        }
        adapted += 1
    db.flush()
    common.audit(
        db, "goal_milestones_adapted", user_id=user.id, entity_type="goal", entity_id=goal.id,
        reason="progress_deviation", after={"adapted": adapted, "deviation": deviation},
    )
    return {
        "adapted": adapted,
        "deviation": deviation,
        "message": "نقاط عطف آینده با پیشرفت واقعی هم‌تراز شد" + (" (عقب‌تر از برنامه)." if deviation < 0 else " (جلوتر از برنامه)."),
    }


def goal_payload(db: Session, user: models.User, goal: models.Goal, *, detailed: bool = True) -> dict:
    progress = goal.progress or {}
    payload = {
        "id": goal.id,
        "title": goal.title,
        "goal_type": goal.goal_type,
        "subject_id": goal.subject_id,
        "book_id": goal.book_id,
        "topic_id": goal.topic_id,
        "scope": goal.scope or {},
        "scope_topic_count": len(goal_scope_topics(db, goal)),
        "status": goal.status,
        "start_date": common.jdate(goal.start_date),
        "target_date": common.jdate(goal.target_date),
        "days_left": (goal.target_date - today_local()).days if goal.target_date else None,
        "baseline": goal.baseline or {},
        "target": goal.target or {},
        "progress": progress,
        "confidence": goal.confidence,
        "confidence_band": common.confidence_band(goal.confidence),
        "notes": goal.notes,
    }
    if detailed:
        payload["objectives"] = [
            {
                "id": objective.id,
                "title": objective.title,
                "metric": objective.metric,
                "metric_label": METRIC_LABELS.get(objective.metric, objective.metric),
                "target_value": objective.target_value,
                "current_value": objective.current_value,
                "status": objective.status,
                "topic_id": objective.topic_id,
            }
            for objective in db.scalars(select(models.GoalObjective).where(models.GoalObjective.goal_id == goal.id))
        ]
        milestones = list(
            db.scalars(
                select(models.GoalMilestone)
                .where(models.GoalMilestone.goal_id == goal.id)
                .order_by(models.GoalMilestone.target_date)
            )
        )
        payload["milestones"] = [
            {
                "id": milestone.id,
                "parent_id": milestone.parent_id,
                "level": milestone.level,
                "title": milestone.title,
                "target_date": common.jdate(milestone.target_date),
                "metrics": milestone.metrics or {},
                "status": milestone.status,
                "adapted_from": milestone.adapted_from or {},
            }
            for milestone in milestones
        ]
    return payload


def list_goals(db: Session, user: models.User, *, refresh: bool = True) -> list[dict]:
    goals = list(db.scalars(select(models.Goal).where(models.Goal.user_id == user.id).order_by(models.Goal.id.desc())))
    payload = []
    for goal in goals:
        if refresh and goal.status == "active":
            refresh_progress(db, user, goal)
        payload.append(goal_payload(db, user, goal, detailed=False))
    return payload


def update_goal(db: Session, user: models.User, goal_id: int, changes: dict) -> models.Goal:
    goal = db.get(models.Goal, goal_id)
    if not goal or goal.user_id != user.id:
        raise NotFoundError("هدف پیدا نشد.")
    for key in ["title", "notes", "status", "goal_type"]:
        if key in changes:
            setattr(goal, key, changes[key])
    if changes.get("target_date"):
        goal.target_date = common.parse_date_if_string(changes["target_date"])
    if changes.get("target"):
        goal.target = changes["target"]
    db.flush()
    common.audit(db, "goal_updated", user_id=user.id, entity_type="goal", entity_id=goal_id, after=changes)
    return goal


def on_task_completed(db: Session, user: models.User, task: models.StudyTask) -> list[dict]:
    """Link a completed task to goals: refresh progress and adapt milestones."""
    updates = []
    goal_ids = set()
    if task.goal_id:
        goal_ids.add(task.goal_id)
    if task.topic_id:
        topic = db.get(models.Topic, task.topic_id)
        for goal in db.scalars(select(models.Goal).where(models.Goal.user_id == user.id, models.Goal.status == "active")):
            scope = goal_scope_topics(db, goal)
            if topic and topic.id in scope:
                goal_ids.add(goal.id)
    for goal_id in goal_ids:
        goal = db.get(models.Goal, goal_id)
        if not goal:
            continue
        progress = refresh_progress(db, user, goal)
        adaptation = adapt_milestones(db, user, goal)
        updates.append(
            {
                "goal_id": goal_id,
                "title": goal.title,
                "ratio": progress["ratio"],
                "status": progress["status"],
                "adaptation": adaptation,
            }
        )
    return updates


def candidate_tasks(db: Session, user: models.User, goal_id: int, *, limit: int = 12) -> list[dict]:
    """Turn milestone gaps into concrete day-level candidates (3m → month → week → day)."""
    goal = db.get(models.Goal, goal_id)
    if not goal or goal.user_id != user.id:
        raise NotFoundError("هدف پیدا نشد.")
    from . import priority

    scope = goal_scope_topics(db, goal)
    if not scope:
        return []
    priorities = priority.compute_priorities(db, user, topics=scope, limit=limit)
    upcoming = db.scalars(
        select(models.GoalMilestone)
        .where(models.GoalMilestone.goal_id == goal.id, models.GoalMilestone.target_date >= today_local())
        .order_by(models.GoalMilestone.target_date)
    ).first()
    candidates = []
    for item in priorities:
        state = db.scalars(
            select(models.LearningState).where(
                models.LearningState.user_id == user.id, models.LearningState.topic_id == item["topic_id"]
            )
        ).first()
        candidates.append(
            {
                "topic_id": item["topic_id"],
                "topic_title": item["topic_title"],
                "priority_score": item["score"],
                "coverage": state.coverage if state else None,
                "accuracy": state.accuracy if state else None,
                "milestone_id": upcoming.id if upcoming else None,
                "milestone_target_date": common.jdate(upcoming.target_date) if upcoming else None,
                "why": f"برای نزدیک‌ترین نقطه عطف هدف ({common.jdate(upcoming.target_date) if upcoming else '—'})",
            }
        )
    return candidates


def _now():
    from ..core.timeutil import now_utc

    return now_utc()
