"""Learning intelligence: multidimensional learning state, coverage, retention.

V3 rules encoded here:

* weakness is **not** a wrong-count. Low coverage and low accuracy are different
  diagnoses and uncertainty is a third one;
* every derived value carries ``confidence``, ``evidence`` and ``model_version``;
* everything in this module is rebuildable from raw attempts;
* ``NOT_ENTERED`` never counts as a wrong answer (and never inflates accuracy).
"""

from __future__ import annotations

import datetime as _dt
import math
from typing import Iterable, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import clamp, now_utc, safe_div, today_local
from ..db import models
from . import common

MODEL_VERSION = config.MODEL_VERSION


# ---------------------------------------------------------------------------
# Raw signal extraction
# ---------------------------------------------------------------------------


def _attempt_rows(db: Session, user: models.User, topic_ids: Optional[Iterable[int]] = None) -> list[models.AttemptResult]:
    stmt = select(models.AttemptResult).where(
        models.AttemptResult.user_id == user.id, models.AttemptResult.is_current.is_(True)
    )
    if topic_ids is not None:
        ids = list(topic_ids)
        if not ids:
            return []
        stmt = stmt.where(models.AttemptResult.topic_id.in_(ids))
    return list(db.scalars(stmt))


def _question_pool_size(db: Session, topic_id: int) -> int:
    return (
        db.scalar(
            select(func.count(models.Question.id)).where(
                models.Question.primary_topic_id == topic_id, models.Question.active.is_(True)
            )
        )
        or 0
    )


def retention_from_elapsed(stability_days: float, elapsed_days: float) -> float:
    """Forgetting-curve style retention estimate (configurable, evidence flagged)."""
    if stability_days <= 0:
        return 0.0
    return float(math.exp(-max(elapsed_days, 0.0) / stability_days))


def next_review_interval(stability_days: float, target_success: Optional[float] = None) -> float:
    target = target_success if target_success is not None else config.value("retention.target_success")
    if stability_days <= 0 or target <= 0:
        return config.value("retention.min_days")
    interval = -stability_days * math.log(target)
    return max(config.value("retention.min_days"), min(config.value("retention.max_days"), interval))


def compute_state_for_topic(db: Session, user: models.User, topic_id: int) -> models.LearningState:
    attempts = _attempt_rows(db, user, [topic_id])
    answered = [a for a in attempts if a.state == "ANSWERED"]
    correct = [a for a in attempts if a.result == "CORRECT"]
    wrong = [a for a in attempts if a.result == "WRONG"]
    unanswered = [a for a in attempts if a.result == "UNANSWERED"]
    not_entered = [a for a in attempts if a.state == "NOT_ENTERED"]
    not_evaluable = [a for a in attempts if a.result == "NOT_EVALUABLE" and a.state != "NOT_ENTERED"]

    pool = _question_pool_size(db, topic_id)
    distinct_attempted = len({a.question_id for a in attempts})
    coverage = safe_div(distinct_attempted, pool) if pool else None
    accuracy = safe_div(len(correct), len(answered)) if answered else None

    reference_difficulty = config.value("learning.difficulty_reference") or 2.0
    weighted_total = weighted_correct = 0.0
    for attempt in answered:
        weight = (attempt.difficulty_level or reference_difficulty) / reference_difficulty
        weight = max(0.5, min(2.0, weight))
        weighted_total += weight
        if attempt.result == "CORRECT":
            weighted_correct += weight
    difficulty_adjusted = safe_div(weighted_correct, weighted_total) if weighted_total else None

    wrong_per_question: dict[int, int] = {}
    for attempt in attempts:
        if attempt.result == "WRONG":
            wrong_per_question[attempt.question_id] = wrong_per_question.get(attempt.question_id, 0) + 1
    repeat_threshold = config.value("review.critical_wrong_count")
    repeated = sum(1 for count in wrong_per_question.values() if count >= repeat_threshold)
    repeated_error_signal = safe_div(repeated, distinct_attempted) if distinct_attempted else None

    durations = [a.duration_seconds for a in attempts if a.duration_seconds]
    time_performance = None
    if durations:
        per_question_seconds = sum(durations) / len(durations)
        low = config.value("session.min_minutes_per_question") * 60
        high = config.value("session.max_minutes_per_question") * 60
        # 1.0 = inside the expected band, <1 = faster, >1 = slower than the band
        if per_question_seconds < low:
            time_performance = per_question_seconds / low
        elif per_question_seconds > high:
            time_performance = per_question_seconds / high
        else:
            time_performance = 1.0

    last_attempt_at = None
    if attempts:
        stamps = [a.attempted_on or (a.evaluated_at.date() if a.evaluated_at else None) for a in attempts]
        stamps = [s for s in stamps if s]
        last_attempt_at = max(stamps) if stamps else None
    recency_days = (today_local() - last_attempt_at).days if last_attempt_at else None

    retention_row = db.scalars(
        select(models.RetentionState).where(
            models.RetentionState.user_id == user.id, models.RetentionState.topic_id == topic_id
        )
    ).first()
    retention_estimate = retention_row.retention_estimate if retention_row else None
    retention_confidence = retention_row.confidence if retention_row else None

    prerequisite_health = _prerequisite_health(db, user, topic_id)
    exam_readiness = _exam_readiness(db, user, topic_id, accuracy, coverage, retention_estimate, recency_days)

    evidence_count = len(answered)
    confidence = common.confidence_from_evidence(evidence_count)
    if coverage is not None:
        confidence *= 0.55 + 0.45 * coverage  # a topic barely touched is barely known
    if not attempts:
        confidence = 0.0
    uncertainty = round(1.0 - confidence, 4)

    evidence = {
        "attempts": len(attempts),
        "answered": len(answered),
        "correct": len(correct),
        "wrong": len(wrong),
        "unanswered": len(unanswered),
        "not_entered": len(not_entered),
        "not_evaluable": len(not_evaluable),
        "distinct_questions_attempted": distinct_attempted,
        "pool_size": pool,
        "repeated_error_questions": repeated,
        "last_attempt_on": common.jdate(last_attempt_at),
        "diagnosis_hint": diagnose(accuracy, coverage, len(answered), uncertainty),
        "retention_source": "retention_states" if retention_row else "insufficient_evidence",
    }

    state = db.scalars(
        select(models.LearningState).where(
            models.LearningState.user_id == user.id,
            models.LearningState.topic_id == topic_id,
            models.LearningState.model_version == MODEL_VERSION,
        )
    ).first()
    if state is None:
        state = models.LearningState(user_id=user.id, topic_id=topic_id, model_version=MODEL_VERSION)
        db.add(state)
    state.accuracy = round(accuracy, 4) if accuracy is not None else None
    state.coverage = round(coverage, 4) if coverage is not None else None
    state.attempts = len(attempts)
    state.answered = len(answered)
    state.correct = len(correct)
    state.wrong = len(wrong)
    state.unanswered = len(unanswered)
    state.not_entered = len(not_entered)
    state.retention_estimate = retention_estimate
    state.retention_confidence = retention_confidence
    state.confidence = round(confidence, 4)
    state.recency_days = recency_days
    state.difficulty_adjusted = round(difficulty_adjusted, 4) if difficulty_adjusted is not None else None
    state.repeated_error_signal = round(repeated_error_signal, 4) if repeated_error_signal is not None else None
    state.time_performance = round(time_performance, 4) if time_performance is not None else None
    state.exam_readiness = round(exam_readiness, 4) if exam_readiness is not None else None
    state.prerequisite_health = round(prerequisite_health, 4) if prerequisite_health is not None else None
    state.uncertainty = uncertainty
    state.evidence = evidence
    state.computed_at = now_utc()
    db.flush()
    _store_metrics(db, user, topic_id, pool, distinct_attempted, coverage, len(answered), len(correct), len(wrong),
                   len(unanswered), accuracy)
    return state


def diagnose(
    accuracy: Optional[float], coverage: Optional[float], answered_count: int, uncertainty: float
) -> str:
    """Separate the three fundamentally different diagnoses (V1 + V3)."""
    if answered_count == 0:
        return "NO_EVIDENCE"
    if uncertainty > config.value("recommendation.diagnostic_uncertainty_threshold"):
        return "UNCERTAIN_NEEDS_DIAGNOSTIC"
    low_coverage = coverage is not None and coverage < config.value("priority.low_coverage_threshold")
    high_accuracy = accuracy is not None and accuracy >= config.value("priority.high_accuracy_threshold")
    weak_accuracy = accuracy is not None and accuracy < config.value("priority.weak_accuracy_threshold")
    if low_coverage and high_accuracy:
        return "LOW_COVERAGE_GOOD_ACCURACY"
    if not low_coverage and weak_accuracy:
        return "GOOD_COVERAGE_WEAK_ACCURACY"
    if low_coverage and weak_accuracy:
        return "LOW_COVERAGE_AND_WEAK"
    return "ON_TRACK"


def _store_metrics(
    db: Session,
    user: models.User,
    topic_id: int,
    pool: int,
    attempted: int,
    coverage: Optional[float],
    answered: int,
    correct: int,
    wrong: int,
    unanswered: int,
    accuracy: Optional[float],
) -> None:
    coverage_row = db.scalars(
        select(models.CoverageMetric).where(
            models.CoverageMetric.user_id == user.id,
            models.CoverageMetric.scope_type == "topic",
            models.CoverageMetric.scope_id == topic_id,
        )
    ).first()
    if coverage_row is None:
        coverage_row = models.CoverageMetric(user_id=user.id, scope_type="topic", scope_id=topic_id)
        db.add(coverage_row)
    coverage_row.target_question_count = pool
    coverage_row.attempted_question_count = attempted
    coverage_row.coverage = round(coverage, 4) if coverage is not None else None
    coverage_row.computed_at = now_utc()

    accuracy_row = db.scalars(
        select(models.AccuracyMetric).where(
            models.AccuracyMetric.user_id == user.id,
            models.AccuracyMetric.scope_type == "topic",
            models.AccuracyMetric.scope_id == topic_id,
        )
    ).first()
    if accuracy_row is None:
        accuracy_row = models.AccuracyMetric(user_id=user.id, scope_type="topic", scope_id=topic_id)
        db.add(accuracy_row)
    accuracy_row.answered = answered
    accuracy_row.correct = correct
    accuracy_row.wrong = wrong
    accuracy_row.unanswered = unanswered
    accuracy_row.accuracy = round(accuracy, 4) if accuracy is not None else None
    accuracy_row.unanswered_rate = round(safe_div(unanswered, answered + unanswered) or 0.0, 4) if (answered + unanswered) else None
    accuracy_row.computed_at = now_utc()
    db.flush()


def _prerequisite_health(db: Session, user: models.User, topic_id: int) -> Optional[float]:
    prerequisites = list(
        db.scalars(
            select(models.Topic)
            .join(models.TopicDependency, models.TopicDependency.prerequisite_topic_id == models.Topic.id)
            .where(models.TopicDependency.dependent_topic_id == topic_id)
        )
    )
    if not prerequisites:
        return None
    scores: list[float] = []
    for prerequisite in prerequisites:
        state = db.scalars(
            select(models.LearningState).where(
                models.LearningState.user_id == user.id,
                models.LearningState.topic_id == prerequisite.id,
            )
        ).first()
        if state is None:
            scores.append(0.2)  # unknown prerequisite = low health, explicitly not zero-evidence-turned-perfect
            continue
        parts = [state.accuracy if state.accuracy is not None else 0.3]
        if state.coverage is not None:
            parts.append(state.coverage)
        if state.retention_estimate is not None:
            parts.append(state.retention_estimate)
        scores.append(sum(parts) / len(parts))
    return clamp(sum(scores) / len(scores))


def _exam_readiness(
    db: Session,
    user: models.User,
    topic_id: int,
    accuracy: Optional[float],
    coverage: Optional[float],
    retention: Optional[float],
    recency_days: Optional[int],
) -> Optional[float]:
    exams = list(
        db.scalars(
            select(models.Exam)
            .join(models.ExamTopic, models.ExamTopic.exam_id == models.Exam.id)
            .where(
                models.Exam.user_id == user.id,
                models.ExamTopic.topic_id == topic_id,
                models.Exam.exam_date >= today_local(),
                models.Exam.status.in_(["planned", "in_progress"]),
            )
        )
    )
    if not exams:
        return None
    horizon = config.value("exam.urgency_horizon_days")
    weight_sum = 0.0
    score_sum = 0.0
    for exam in exams:
        days = (exam.exam_date - today_local()).days
        urgency = clamp(1.0 - (days / horizon) if horizon else 0.0, 0.05, 1.0)
        weight_sum += urgency
        score_sum += urgency * _readiness_blend(accuracy, coverage, retention, recency_days)
    return clamp(safe_div(score_sum, weight_sum) or 0.0)


def _readiness_blend(
    accuracy: Optional[float], coverage: Optional[float], retention: Optional[float], recency_days: Optional[int]
) -> float:
    parts = []
    parts.append(accuracy if accuracy is not None else 0.3)
    parts.append(coverage if coverage is not None else 0.2)
    if retention is not None:
        parts.append(retention)
    if recency_days is not None:
        half_life = config.value("learning.recency_half_life_days")
        parts.append(math.exp(-recency_days / half_life) if half_life else 0.5)
    return clamp(sum(parts) / len(parts))


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


def refresh_retention_for_session(db: Session, user: models.User, session: models.TestSession) -> None:
    """Update the per-topic retention model after a practice/review session."""
    attempts = list(
        db.scalars(
            select(models.AttemptResult).where(
                models.AttemptResult.session_id == session.id, models.AttemptResult.is_current.is_(True)
            )
        )
    )
    by_topic: dict[int, list[models.AttemptResult]] = {}
    for attempt in attempts:
        if attempt.topic_id:
            by_topic.setdefault(attempt.topic_id, []).append(attempt)
    for topic_id, topic_attempts in by_topic.items():
        answered = [a for a in topic_attempts if a.state == "ANSWERED"]
        if not answered:
            continue
        success = sum(1 for a in answered if a.result == "CORRECT") / len(answered)
        is_review = session.session_type == "review" or session.intervention_type in {
            "REVIEW", "ACTIVE_RECALL", "ERROR_REVIEW", "PREREQUISITE_REVIEW"
        }
        update_retention(db, user, topic_id, success=success, is_review=is_review, session=session)


def update_retention(
    db: Session,
    user: models.User,
    topic_id: int,
    *,
    success: float,
    is_review: bool,
    session: Optional[models.TestSession] = None,
) -> models.RetentionState:
    row = db.scalars(
        select(models.RetentionState).where(
            models.RetentionState.user_id == user.id, models.RetentionState.topic_id == topic_id
        )
    ).first()
    if row is None:
        row = models.RetentionState(
            user_id=user.id,
            topic_id=topic_id,
            stability_days=config.value("retention.stability_base_days"),
            review_count=0,
            lapses=0,
            evidence_count=0,
        )
        db.add(row)
    base = config.value("retention.stability_base_days")
    growth = config.value("retention.stability_growth")
    now = now_utc()
    if is_review:
        row.review_count += 1
        if success >= 0.7:
            row.stability_days = (row.stability_days or base) * (1 + growth * success)
        else:
            row.lapses += 1
            row.stability_days = max(base, (row.stability_days or base) * 0.5)
    else:
        # first exposures build a base stability only when the topic was handled well
        row.stability_days = max(row.stability_days or base, base * (0.6 + 0.8 * success))
    row.stability_days = min(row.stability_days or base, 180.0)
    row.last_reviewed_at = now
    row.last_review_result = "success" if success >= 0.7 else "partial" if success >= 0.4 else "lapse"
    interval = next_review_interval(row.stability_days)
    row.next_review_at = now + _dt.timedelta(days=interval)
    row.retention_estimate = round(retention_from_elapsed(row.stability_days, 0.0), 4)
    session_evidence = 0
    if session is not None:
        session_evidence = db.scalar(
            select(func.count(models.AttemptResult.id)).where(
                models.AttemptResult.session_id == session.id,
                models.AttemptResult.topic_id == topic_id,
                models.AttemptResult.is_current.is_(True),
            )
        ) or 0
    row.evidence_count = (row.evidence_count or 0) + max(1, session_evidence)
    row.confidence = common.confidence_from_evidence(row.evidence_count or 0)
    row.model_version = MODEL_VERSION
    db.flush()
    return row


def retention_decay_all(db: Session, user: models.User) -> int:
    """Refresh retention estimates for today (called by the dashboard/refresh job)."""
    rows = list(db.scalars(select(models.RetentionState).where(models.RetentionState.user_id == user.id)))
    now = today_local()
    updated = 0
    for row in rows:
        if not row.last_reviewed_at:
            continue
        elapsed = (now - row.last_reviewed_at.date()).days
        row.retention_estimate = round(retention_from_elapsed(row.stability_days or 0, elapsed), 4)
        updated += 1
    db.flush()
    return updated


# ---------------------------------------------------------------------------
# Bulk refresh
# ---------------------------------------------------------------------------


def refresh_topics(db: Session, user: models.User, topic_ids: Optional[Iterable[int]]) -> list[int]:
    if topic_ids is None:
        topic_ids = list(
            db.scalars(
                select(models.AttemptResult.topic_id)
                .where(models.AttemptResult.user_id == user.id, models.AttemptResult.topic_id.is_not(None))
                .distinct()
            )
        )
    touched = []
    for topic_id in {t for t in topic_ids if t}:
        compute_state_for_topic(db, user, topic_id)
        touched.append(topic_id)
    db.flush()
    return touched


def rebuild_all(db: Session, user: models.User) -> dict:
    """Full rebuild of every derived metric for one user (recalculation engine)."""
    topics = refresh_topics(db, user, None)
    retention_decay_all(db, user)
    return {"topics_refreshed": len(topics), "model_version": MODEL_VERSION}


def topic_state_map(db: Session, user: models.User) -> dict[int, models.LearningState]:
    rows = db.scalars(select(models.LearningState).where(models.LearningState.user_id == user.id))
    return {row.topic_id: row for row in rows}


def rollup(db: Session, user: models.User, topic_ids: Iterable[int]) -> dict:
    """Aggregate child topics into one honest summary for parent topics/books."""
    states = [
        state
        for state in db.scalars(
            select(models.LearningState).where(
                models.LearningState.user_id == user.id, models.LearningState.topic_id.in_(list(topic_ids))
            )
        )
    ]
    pool = sum((state.evidence or {}).get("pool_size", 0) for state in states)
    attempted = sum((state.evidence or {}).get("distinct_questions_attempted", 0) for state in states)
    answered = sum(state.answered or 0 for state in states)
    correct = sum(state.correct or 0 for state in states)
    wrong = sum(state.wrong or 0 for state in states)
    unanswered = sum(state.unanswered or 0 for state in states)
    not_entered = sum(state.not_entered or 0 for state in states)
    confidences = [state.confidence for state in states if state.confidence is not None]
    return {
        "topics_with_data": len(states),
        "pool_size": pool,
        "attempted_questions": attempted,
        "coverage": safe_div(attempted, pool) if pool else None,
        "answered": answered,
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "not_entered": not_entered,
        "accuracy": safe_div(correct, answered) if answered else None,
        "mean_confidence": (sum(confidences) / len(confidences)) if confidences else None,
        "volume": answered + unanswered + not_entered,
    }
