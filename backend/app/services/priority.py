"""Priority engine — answers *WHAT matters*, not when and not what to do.

Conceptual formula from the V3 master specification::

    Exam Need + Goal Need + Learning Need + Coverage Need + Review Need +
    Prerequisite Need + Retention Risk + Behavioral Fit + Opportunity
    − Capacity Cost − Recent Saturation

Every weight lives in :mod:`app.config` with provenance and confidence labels.
Nothing here is a magic number and every score ships with its components so the
UI can answer "why?" without saying "the AI says so".
"""

from __future__ import annotations

import datetime as _dt
import statistics
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import clamp, safe_div, today_local
from ..db import models
from . import common

MODEL_VERSION = config.MODEL_VERSION

WEIGHTS = {
    "exam_need": "priority.weight.exam_need",
    "goal_need": "priority.weight.goal_need",
    "learning_need": "priority.weight.learning_need",
    "coverage_need": "priority.weight.coverage_need",
    "review_need": "priority.weight.review_need",
    "prerequisite_need": "priority.weight.prerequisite_need",
    "retention_risk": "priority.weight.retention_risk",
    "behavioral_fit": "priority.weight.behavioral_fit",
    "opportunity": "priority.weight.opportunity",
}
NEGATIVE_WEIGHTS = {
    "capacity_cost": "priority.weight.capacity_cost",
    "recent_saturation": "priority.weight.recent_saturation",
}

COMPONENT_LABELS_FA = {
    "exam_need": "نیاز امتحان",
    "goal_need": "نیاز هدف بلندمدت",
    "learning_need": "نیاز یادگیری",
    "coverage_need": "نیاز پوشش",
    "review_need": "نیاز مرور",
    "prerequisite_need": "پیش‌نیاز",
    "retention_risk": "ریسک فراموشی",
    "behavioral_fit": "تناسب رفتاری",
    "opportunity": "فرصت",
    "capacity_cost": "هزینه ظرفیت",
    "recent_saturation": "اشباع اخیر",
}


# ---------------------------------------------------------------------------
# Component computation
# ---------------------------------------------------------------------------


def _topic_scope_ids(db: Session, topic_id: int) -> tuple[list[int], list[int]]:
    """Return (self, descendants) - parents are used for exam/goal inheritance."""
    topic = db.get(models.Topic, topic_id)
    if not topic:
        return [topic_id], []
    descendants = list(
        db.scalars(select(models.Topic.id).where(models.Topic.path.like(f"{topic.path}{topic.id}/%")))
    )
    ancestors: list[int] = []
    current = topic
    while current.parent_id:
        current = db.get(models.Topic, current.parent_id)
        if not current:
            break
        ancestors.append(current.id)
    return descendants, ancestors


def exam_component(db: Session, user: models.User, topic_id: int, day: _dt.date) -> tuple[float, dict]:
    descendants, ancestors = _topic_scope_ids(db, topic_id)
    scope = set(descendants) | {topic_id} | set(ancestors)
    rows = list(
        db.execute(
            select(models.Exam, models.ExamTopic)
            .join(models.ExamTopic, models.ExamTopic.exam_id == models.Exam.id)
            .where(
                models.Exam.user_id == user.id,
                models.ExamTopic.topic_id.in_(scope),
                models.Exam.status.in_(["planned", "in_progress"]),
                models.Exam.exam_date >= day,
            )
        ).all()
    )
    if not rows:
        return 0.0, {"exams": [], "reason": "امتحان نزدیکی مرتبط با این مبحث وجود ندارد."}
    horizon = config.value("exam.urgency_horizon_days")
    best = 0.0
    evidence = []
    for exam, mark in rows:
        days = (exam.exam_date - day).days
        urgency = clamp(1.0 - (days / horizon), 0.05, 1.0)
        weight = 1.0 if mark.mark_kind == "actual" else config.value("exam.overlap_weight")
        direct = 1.0 if mark.topic_id == topic_id else 0.65
        score = urgency * weight * direct
        evidence.append(
            {
                "exam_id": exam.id,
                "title": exam.title,
                "date": common.jdate(exam.exam_date),
                "days_left": days,
                "mark_kind": mark.mark_kind,
                "urgency": round(urgency, 3),
                "score": round(score, 3),
            }
        )
        best = max(best, score)
    evidence.sort(key=lambda item: item["score"], reverse=True)
    return clamp(best * (1 + config.value("exam.urgency_boost") * best)), {
        "exams": evidence[:3],
        "reason": f"نزدیک‌ترین امتحان مرتبط: {evidence[0]['title']} ({evidence[0]['days_left']} روز مانده)",
    }


def goal_component(db: Session, user: models.User, topic_id: int, day: _dt.date) -> tuple[float, dict]:
    topic = db.get(models.Topic, topic_id)
    if not topic:
        return 0.0, {}
    goals = list(
        db.scalars(
            select(models.Goal).where(
                models.Goal.user_id == user.id,
                models.Goal.status == "active",
                models.Goal.target_date >= day,
            )
        )
    )
    if not goals:
        return 0.0, {"reason": "هدف فعالی ثبت نشده است."}
    score = 0.0
    evidence = []
    for goal in goals:
        matches = (
            goal.topic_id == topic_id
            or goal.book_id == topic.book_id
            or (goal.subject_id and topic.book_id and _book_subject_id(db, topic.book_id) == goal.subject_id)
        )
        if not matches:
            continue
        deficit = _goal_deficit(db, user, goal)
        total_days = max(1, (goal.target_date - (goal.start_date or day)).days)
        elapsed = max(0, (day - (goal.start_date or day)).days)
        time_pressure = clamp(elapsed / total_days)
        value = clamp(deficit * (0.5 + 0.6 * time_pressure))
        evidence.append(
            {
                "goal_id": goal.id,
                "title": goal.title,
                "progress_deficit": round(deficit, 3),
                "time_pressure": round(time_pressure, 3),
                "score": round(value, 3),
            }
        )
        score = max(score, value)
    if not evidence:
        return 0.0, {"reason": "این مبحث در اهداف فعال نیست."}
    return clamp(score), {"goals": evidence, "reason": f"هدف «{evidence[0]['title']}» از برنامه عقب‌تر از انتظار است."}


def _goal_deficit(db: Session, user: models.User, goal: models.Goal) -> float:
    objectives = list(
        db.scalars(select(models.GoalObjective).where(models.GoalObjective.goal_id == goal.id))
    )
    deficits = []
    for objective in objectives:
        if objective.target_value is None:
            continue
        current = objective.current_value
        if current is None:
            state = db.scalars(
                select(models.LearningState).where(
                    models.LearningState.user_id == user.id, models.LearningState.topic_id == objective.topic_id
                )
            ).first()
            if state is None:
                current = 0.0
            elif objective.metric == "accuracy":
                current = state.accuracy or 0.0
            elif objective.metric == "coverage":
                current = state.coverage or 0.0
            elif objective.metric == "readiness":
                current = state.exam_readiness or 0.0
            else:
                current = 0.0
        baseline = (goal.baseline or {}).get(objective.metric, 0.0)
        span = objective.target_value - baseline
        deficits.append(clamp(safe_div(objective.target_value - current, span) if span else 0.0))
    if not deficits:
        progress = (goal.progress or {}).get("ratio")
        return clamp(1 - progress) if progress is not None else 0.5
    return clamp(statistics.fmean(deficits))


def learning_component(state: Optional[models.LearningState]) -> tuple[float, dict]:
    if state is None or not state.answered:
        return 1.0, {
            "reason": "هنوز شواهدی از این مبحث نداریم؛ نیاز یادگیری حداکثر در نظر گرفته می‌شود.",
            "source": "no_evidence",
        }
    accuracy = state.accuracy if state.accuracy is not None else 0.0
    uncertainty = state.uncertainty if state.uncertainty is not None else 1.0
    repeated = state.repeated_error_signal or 0.0
    weak = config.value("priority.weak_accuracy_threshold")
    accuracy_gap = clamp((weak - accuracy) / weak) if accuracy < weak else 0.0
    value = clamp(0.55 * accuracy_gap + 0.30 * uncertainty + 0.15 * repeated)
    return value, {
        "reason": (
            "دقت پایین‌تر از آستانه" if accuracy_gap > 0.3 else
            "شواهد ناکافی؛ یک تشخیص کوتاه مفیدتر از تمرین زیاد است." if uncertainty > 0.4 else
            "خطاهای تکراری در این مبحث" if repeated > 0.2 else "وضعیت یادگیری متعادل است."
        ),
        "accuracy": accuracy,
        "uncertainty": uncertainty,
        "repeated_error_signal": repeated,
        "source": "learning_state",
    }


def coverage_component(state: Optional[models.LearningState]) -> tuple[float, dict]:
    if state is None:
        return 1.0, {"reason": "هیچ سؤالی از این مبحث دیده نشده است."}
    if state.coverage is None:
        return 0.0, {"reason": "در بانک تست این مبحث سؤالی تعریف نشده است؛ نیاز پوشش تعریف‌نشده."}
    return clamp(1 - state.coverage), {
        "reason": f"پوشش {round(state.coverage * 100)}٪ از سؤالات این مبحث",
        "coverage": state.coverage,
    }


def review_component(db: Session, user: models.User, topic_id: int, day: _dt.date) -> tuple[float, dict]:
    items = list(
        db.scalars(
            select(models.ReviewItem).where(
                models.ReviewItem.user_id == user.id,
                models.ReviewItem.topic_id == topic_id,
                models.ReviewItem.state == "open",
            )
        )
    )
    if not items:
        return 0.0, {"reason": "آیتم مرور بازی برای این مبحث نیست.", "open_items": 0}
    critical = sum(1 for item in items if item.priority == "critical")
    due = sum(1 for item in items if item.scheduled_for and item.scheduled_for <= day)
    value = clamp(min(1.0, (len(items) / 12) + 0.25 * min(1.0, critical / 3) + 0.2 * min(1.0, due / 5)))
    return value, {
        "reason": f"{len(items)} سؤال در صف مرور ({critical} بحرانی)",
        "open_items": len(items),
        "critical": critical,
        "due": due,
    }


def prerequisite_component(db: Session, user: models.User, state: Optional[models.LearningState]) -> tuple[float, dict]:
    if state is not None and state.prerequisite_health is not None:
        value = clamp(1 - state.prerequisite_health)
        reason = (
            "پیش‌نیازهای این مبحث ضعیف‌اند؛ ابتدا پیش‌نیاز را تثبیت کن."
            if value > 0.4 else "وضعیت پیش‌نیازها قابل قبول است."
        )
        return value, {"reason": reason, "prerequisite_health": state.prerequisite_health}
    return 0.0, {"reason": "پیش‌نیازی برای این مبحث ثبت نشده است.", "prerequisite_health": None}


def retention_component(state: Optional[models.LearningState], day: _dt.date) -> tuple[float, dict]:
    if state is None or state.retention_estimate is None:
        return 0.25, {"reason": "تخمین نگه‌داشت هنوز شواهد کافی ندارد."}
    decay_rate = (state.evidence or {}).get("retention_decay_per_day")
    risk = clamp(1 - state.retention_estimate)
    return risk, {
        "reason": f"تخمین نگه‌داشت {round(state.retention_estimate * 100)}٪ — احتمال فراموشی {round(risk * 100)}٪",
        "retention": state.retention_estimate,
        "decay_rate": decay_rate,
    }


def behavioral_fit_component(db: Session, user: models.User, topic_id: int, state: Optional[models.LearningState]) -> tuple[float, dict]:
    """Personality/state only enter the model above a confidence threshold (V2.2)."""
    user_state = db.scalars(
        select(models.UserState).where(models.UserState.user_id == user.id).order_by(models.UserState.captured_at.desc())
    ).first()
    profile = db.scalars(select(models.UserProfile).where(models.UserProfile.user_id == user.id)).first()
    evidence: dict = {}
    score = 0.5
    threshold = config.value("behavior.personality_confident_threshold")
    if user_state is not None:
        energy = user_state.energy if user_state.energy is not None else 0.5
        fatigue = user_state.fatigue if user_state.fatigue is not None else 0.5
        difficulty = _topic_difficulty(db, topic_id)
        # high energy fits demanding topics, low energy fits easier work
        fit = clamp(energy * (0.4 + 0.6 * difficulty) + (1 - fatigue) * 0.3)
        score = fit
        evidence["state"] = {"energy": energy, "fatigue": fatigue, "captured_at": common.jdatetime(user_state.captured_at)}
    if profile and profile.personality:
        procrastination = (profile.personality.get("procrastination") or {})
        if (procrastination.get("confidence") or 0) >= threshold:
            evidence["procrastination"] = {
                "value": procrastination.get("value"),
                "confidence": procrastination.get("confidence"),
                "note": "اثر رفتاری فقط با اطمینان کافی وارد وزن‌دهی می‌شود.",
            }
    return clamp(score), {
        "reason": "تناسب با وضعیت فعلی و ترجیحات تأییدشده" if evidence else "داده رفتاری کافی برای این مؤلفه نیست.",
        **evidence,
    }


def opportunity_component(db: Session, user: models.User, day: _dt.date) -> tuple[float, dict]:
    from . import capacity as capacity_service

    cap = capacity_service.day_capacity(db, user, day)
    if cap["realistic_minutes"] <= 0:
        return 0.0, {"reason": "ظرفیت واقع‌بینانه امروز صفر است."}
    ratio = clamp(safe_div(cap["planned_minutes"], cap["realistic_minutes"]) or 0.0)
    remaining = clamp(1 - ratio)
    return remaining, {
        "reason": f"{cap['realistic_minutes']} دقیقه ظرفیت واقع‌بینانه و {cap['planned_minutes']} دقیقه برنامه‌ریزی‌شده",
        "remaining_ratio": round(remaining, 3),
    }


def cost_component(db: Session, user: models.User, topic_id: int, day: _dt.date) -> tuple[float, dict]:
    from . import capacity as capacity_service

    cap = capacity_service.day_capacity(db, user, day)
    uncovered = db.scalar(
        select(func.count(models.Question.id)).where(
            models.Question.primary_topic_id == topic_id, models.Question.active.is_(True)
        )
    ) or 0
    estimate = config.value("session.max_minutes_per_question") * min(20, max(5, uncovered))
    ratio = clamp(safe_div(min(estimate, 120), cap["realistic_minutes"] or 1) or 0.0)
    return ratio, {
        "reason": f"برآورد کار مؤثر حدود {int(min(estimate, 120))} دقیقه در برابر ظرفیت {cap['realistic_minutes']} دقیقه",
        "estimated_minutes": int(min(estimate, 120)),
    }


def saturation_component(db: Session, user: models.User, topic_id: int, day: _dt.date) -> tuple[float, dict]:
    window = config.value("priority.saturation_window_days")
    since = day - _dt.timedelta(days=window)
    recent_attempts = db.scalar(
        select(func.count(models.AttemptResult.id)).where(
            models.AttemptResult.user_id == user.id,
            models.AttemptResult.topic_id == topic_id,
            models.AttemptResult.is_current.is_(True),
            models.AttemptResult.attempted_on >= since,
        )
    ) or 0
    reference = config.value("priority.saturation_reference_attempts") * window
    value = clamp(safe_div(recent_attempts, reference) or 0.0)
    return value, {
        "reason": f"{recent_attempts} تلاش در {window} روز اخیر روی این مبحث",
        "recent_attempts": recent_attempts,
        "window_days": window,
    }


def _topic_difficulty(db: Session, topic_id: int) -> float:
    """Average relative difficulty of a topic's questions (0..1), defaulted when unknown."""
    rows = list(
        db.scalars(
            select(models.Question.difficulty_level).where(
                models.Question.primary_topic_id == topic_id, models.Question.active.is_(True)
            )
        )
    )
    levels = [row for row in rows if row]
    if not levels:
        return 0.5
    reference = config.value("learning.difficulty_reference") or 2.0
    return clamp(statistics.fmean(levels) / (reference * 2))


def _book_subject_id(db: Session, book_id: int) -> Optional[int]:
    book = db.get(models.Book, book_id)
    return book.subject_id if book else None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def compute_topic_priority(
    db: Session, user: models.User, topic_id: int, *, horizon: str = "week", day: Optional[_dt.date] = None
) -> dict:
    day = day or today_local()
    state = db.scalars(
        select(models.LearningState).where(
            models.LearningState.user_id == user.id, models.LearningState.topic_id == topic_id
        )
    ).first()
    components: dict[str, dict] = {}

    def record(name: str, value: float, evidence: dict) -> float:
        components[name] = {
            "value": round(clamp(value), 4),
            "label": COMPONENT_LABELS_FA[name],
            "evidence": evidence,
        }
        return clamp(value)

    exam_value, exam_evidence = exam_component(db, user, topic_id, day)
    goal_value, goal_evidence = goal_component(db, user, topic_id, day)
    learning_value, learning_evidence = learning_component(state)
    coverage_value, coverage_evidence = coverage_component(state)
    review_value, review_evidence = review_component(db, user, topic_id, day)
    prereq_value, prereq_evidence = prerequisite_component(db, user, state)
    retention_value, retention_evidence = retention_component(state, day)
    behavior_value, behavior_evidence = behavioral_fit_component(db, user, topic_id, state)
    opportunity_value, opportunity_evidence = opportunity_component(db, user, day)
    cost_value, cost_evidence = cost_component(db, user, topic_id, day)
    saturation_value, saturation_evidence = saturation_component(db, user, topic_id, day)

    positive = {
        "exam_need": record("exam_need", exam_value, exam_evidence),
        "goal_need": record("goal_need", goal_value, goal_evidence),
        "learning_need": record("learning_need", learning_value, learning_evidence),
        "coverage_need": record("coverage_need", coverage_value, coverage_evidence),
        "review_need": record("review_need", review_value, review_evidence),
        "prerequisite_need": record("prerequisite_need", prereq_value, prereq_evidence),
        "retention_risk": record("retention_risk", retention_value, retention_evidence),
        "behavioral_fit": record("behavioral_fit", behavior_value, behavior_evidence),
        "opportunity": record("opportunity", opportunity_value, opportunity_evidence),
    }
    negative = {
        "capacity_cost": record("capacity_cost", cost_value, cost_evidence),
        "recent_saturation": record("recent_saturation", saturation_value, saturation_evidence),
    }

    score = 0.0
    contributions = []
    for name, value in positive.items():
        weight = config.value(WEIGHTS[name])
        contribution = weight * value
        score += contribution
        contributions.append({"component": name, "label": COMPONENT_LABELS_FA[name], "weight": weight, "contribution": round(contribution, 4)})
    for name, value in negative.items():
        weight = config.value(NEGATIVE_WEIGHTS[name])
        contribution = -weight * value
        score += contribution
        contributions.append({"component": name, "label": COMPONENT_LABELS_FA[name], "weight": weight, "contribution": round(contribution, 4)})

    score = max(0.0, min(1.0, score))
    # every contribution keeps its raw value and evidence so explanations can be
    # traced all the way back to the input data (V3 explainability requirement)
    for contribution in contributions:
        detail = components.get(contribution["component"]) or {}
        contribution["value"] = detail.get("value")
        contribution["evidence"] = detail.get("evidence") or {}
        contribution["human_text"] = (
            f"{contribution['label']}: " + (str((detail.get('evidence') or {}).get("reason") or ""))
        ).strip(": ")
    contributions.sort(key=lambda item: abs(item["contribution"]), reverse=True)
    confidence = state.confidence if state and state.confidence is not None else 0.15
    return {
        "topic_id": topic_id,
        "horizon": horizon,
        "computed_for": common.jdate(day),
        "score": round(score, 4),
        "components": {**components},
        "contributions": contributions,
        "top_reasons": contributions[:3],
        "confidence": round(confidence, 3),
        "model_version": MODEL_VERSION,
        "learning_state_summary": {
            "accuracy": state.accuracy if state else None,
            "coverage": state.coverage if state else None,
            "attempts": state.attempts if state else 0,
        }
        if state else None,
    }


def actionable_topics(db: Session, user: models.User, *, include_unplannable: bool = False) -> list[models.Topic]:
    """Topics that can enter a *timed* suggestion.

    V3.1 doc 04: a topic without a question bank stays visible in the curriculum but
    is never scheduled, estimated or suggested with a time — so the planner, the
    recommendations and the goal decomposition all consume this list.
    """
    taught_rows = db.scalars(
        select(models.TaughtTopic.topic_id).where(models.TaughtTopic.user_id == user.id, models.TaughtTopic.taught.is_(True))
    )
    taught = set(taught_rows)
    with_questions = set(
        db.scalars(
            select(models.Question.primary_topic_id)
            .where(models.Question.active.is_(True), models.Question.primary_topic_id.is_not(None))
            .distinct()
        )
    )
    with_attempts = set(
        db.scalars(select(models.AttemptResult.topic_id).where(models.AttemptResult.user_id == user.id).distinct())
    )
    exam_topics = set(
        db.scalars(
            select(models.ExamTopic.topic_id)
            .join(models.Exam, models.Exam.id == models.ExamTopic.exam_id)
            .where(models.Exam.user_id == user.id, models.Exam.status.in_(["planned", "in_progress"]))
        )
    )
    relevant = taught | with_questions | with_attempts | exam_topics
    if not relevant:
        return []
    topics = list(db.scalars(select(models.Topic).where(models.Topic.id.in_(relevant))))
    leaf_or_attempted = [
        topic for topic in topics
        if topic.is_leaf or topic.id in with_attempts or topic.id in exam_topics
    ]
    if include_unplannable:
        return leaf_or_attempted
    from . import curriculum as curriculum_service

    plannable = curriculum_service.plannable_topic_ids(db, [topic.id for topic in leaf_or_attempted])
    return [topic for topic in leaf_or_attempted if topic.id in plannable]


def visible_only_count(db: Session) -> int:
    """How many topics exist but have no question bank anywhere in their subtree."""
    from sqlalchemy import func

    total = db.scalar(select(func.count(models.Topic.id))) or 0
    return total - len(_all_plannable_topic_ids(db))


def _all_plannable_topic_ids(db: Session) -> set[int]:
    from . import curriculum as curriculum_service

    return curriculum_service.plannable_topic_ids(db)


def unplannable_topics(db: Session, user: models.User) -> list[dict]:
    """The visible-only counterparts of :func:`actionable_topics`, reported honestly."""
    candidates = actionable_topics(db, user, include_unplannable=True)
    plannable = {topic.id for topic in actionable_topics(db, user)}
    rows = []
    for topic in candidates:
        if topic.id in plannable:
            continue
        rows.append(
            {
                "topic_id": topic.id,
                "title": topic.title,
                "reason": "بانک تست ندارد؛ فقط در درخت آموزشی دیده می‌شود",
                "how_to_make_plannable": "با «بانک تست این مبحث» چند سؤال و کلید اضافه کن.",
            }
        )
    return rows


def compute_priorities(
    db: Session,
    user: models.User,
    *,
    horizon: str = "week",
    day: Optional[_dt.date] = None,
    limit: Optional[int] = None,
    topics: Optional[Iterable[int]] = None,
) -> list[dict]:
    day = day or today_local()
    candidates = list(topics) if topics is not None else [topic.id for topic in actionable_topics(db, user)]
    results = [compute_topic_priority(db, user, topic_id, horizon=horizon, day=day) for topic_id in candidates]
    results.sort(key=lambda item: item["score"], reverse=True)
    titles = {
        topic.id: topic.title
        for topic in db.scalars(select(models.Topic).where(models.Topic.id.in_([r["topic_id"] for r in results] or [0])))
    }
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank
        item["topic_title"] = titles.get(item["topic_id"])
    return results[:limit] if limit else results


def persist_snapshots(
    db: Session, user: models.User, items: list[dict], *, horizon: str = "week", computed_for: Optional[_dt.date] = None
) -> int:
    day = computed_for or today_local()
    existing = {
        row.topic_id: row
        for row in db.scalars(
            select(models.PrioritySnapshot).where(
                models.PrioritySnapshot.user_id == user.id,
                models.PrioritySnapshot.horizon == horizon,
                models.PrioritySnapshot.computed_for == day,
            )
        )
    }
    for item in items:
        row = existing.get(item["topic_id"])
        if row is None:
            row = models.PrioritySnapshot(
                user_id=user.id, topic_id=item["topic_id"], horizon=horizon, computed_for=day
            )
            db.add(row)
        row.score = item["score"]
        row.components = item["components"]
        row.confidence = item["confidence"]
        row.rank = item.get("rank")
        row.model_version = MODEL_VERSION
    db.flush()
    return len(items)


def explain_priority(item: dict) -> dict:
    """The four mandatory questions: What? Why? Evidence? What can I change?"""
    top = item["top_reasons"]
    why = "، ".join(
        f"{reason['label']} ({'+' if reason['contribution'] >= 0 else ''}{round(reason['contribution'], 3)})" for reason in top
    )
    return {
        "what": f"مبحث «{item.get('topic_title') or item['topic_id']}» با امتیاز {round(item['score'], 3)} در رتبه {item.get('rank')}",
        "why": f"مؤثرترین مؤلفه‌ها: {why}",
        "evidence": {reason["component"]: reason for reason in top},
        "what_can_i_change": [
            "وزن‌های موتور اولویت در تنظیمات قابل تغییر و آزمایش هستند (بدون هارد‌کد).",
            "اگر می‌خواهی این مبحث کمتر بیاید، کاهش دستی اولویت یا رد پیشنهاد ثبت می‌شود و در آینده لحاظ می‌گردد.",
            "اگر تیک «تدریس‌شده» یا نگاشت سؤال به مبحث اشتباه است، اصلاح آن باعث بازمحاسبه اولویت می‌شود.",
        ],
        "confidence": item["confidence"],
        "model_version": item["model_version"],
    }
