"""Recalculation and integrity.

V3: "If answer key, topic mapping, taught state or other source data changes:
preserve audit history; recalculate affected attempt results; recalculate
accuracy/coverage/learning state; recalculate priorities/recommendations when
needed. Support incremental and full rebuilds. Version important models."

Nothing here mutates raw data: raw observations stay untouched, derived tables are
recomputed and every job is recorded.
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import now_utc
from ..db import models
from ..domain.enums import JobStatus, RecalcScope
from . import common, learning, priority, review, sessions as sessions_service

MODEL_VERSION = config.MODEL_VERSION


def _job(db: Session, user: models.User, scope: str, scope_id: Optional[int], trigger: str, incremental: bool) -> models.RecalculationJob:
    job = models.RecalculationJob(
        user_id=user.id,
        scope=scope,
        scope_id=scope_id,
        trigger=trigger,
        status=JobStatus.RUNNING.value,
        incremental=incremental,
        started_at=now_utc(),
        model_version=MODEL_VERSION,
    )
    db.add(job)
    db.flush()
    return job


def _finish(db: Session, job: models.RecalculationJob, changes: dict, error: Optional[str] = None) -> None:
    job.status = JobStatus.FAILED.value if error else JobStatus.DONE.value
    job.changes = changes
    job.finished_at = now_utc()
    job.error = error
    db.flush()


def recalculate(
    db: Session,
    user: models.User,
    *,
    scope: str = RecalcScope.USER.value,
    scope_id: Optional[int] = None,
    trigger: str = "manual",
    incremental: bool = True,
) -> dict:
    job = _job(db, user, scope, scope_id, trigger, incremental)
    try:
        result: dict = {}
        if scope == RecalcScope.QUESTION.value and scope_id:
            result["attempts"] = sessions_service.reevaluate_question(db, user, scope_id, reason=trigger)
            learning.refresh_topics(db, user, None)
        elif scope == RecalcScope.TOPIC.value and scope_id:
            topic = db.get(models.Topic, scope_id)
            topic_ids: set[int] = {scope_id}
            if topic:
                topic_ids |= set(
                    db.scalars(select(models.Topic.id).where(models.Topic.path.like(f"{topic.path}{topic.id}/%")))
                )
            question_ids = list(
                db.scalars(select(models.Question.id).where(models.Question.primary_topic_id.in_(topic_ids)))
            )
            changed = 0
            for question_id in question_ids:
                outcome = sessions_service.reevaluate_question(db, user, question_id, reason=trigger)
                changed += outcome["changed"]
            learning.refresh_topics(db, user, topic_ids)
            review.rebuild_for_questions(db, user, set(question_ids))
            result = {"topics": sorted(topic_ids), "questions": len(question_ids), "changed": changed}
        elif scope == RecalcScope.ANSWER_KEY.value and scope_id:
            result["attempts"] = sessions_service.reevaluate_question(db, user, scope_id, reason=trigger)
            learning.refresh_topics(db, user, None)
        else:
            result = full_rebuild(db, user)
        priority.persist_snapshots(
            db, user, priority.compute_priorities(db, user, horizon="week", limit=25), horizon="week"
        )
        _finish(db, job, result)
        common.audit(
            db, "recalculation_completed", user_id=user.id, entity_type="recalculation_job", entity_id=job.id,
            reason=trigger, after=result,
        )
        return {
            "job_id": job.id,
            "scope": scope,
            "scope_id": scope_id,
            "incremental": incremental,
            "changes": result,
            "model_version": MODEL_VERSION,
            "audit_preserved": True,
            "message": "داده خام دست‌نخورده ماند؛ فقط مقادیر مشتق‌شده بازمحاسبه شد.",
        }
    except Exception as exc:  # pragma: no cover - defensive, surfaced as a failed job
        _finish(db, job, {}, str(exc))
        common.audit(db, "recalculation_failed", user_id=user.id, entity_type="recalculation_job", entity_id=job.id, reason=str(exc))
        raise


def full_rebuild(db: Session, user: models.User) -> dict:
    """Full rebuild of derived data (never of raw observations)."""
    learning.rebuild_all(db, user)
    learning.retention_decay_all(db, user)
    question_ids = list(
        db.scalars(
            select(models.AttemptResult.question_id).where(
                models.AttemptResult.user_id == user.id, models.AttemptResult.is_current.is_(True)
            ).distinct()
        )
    )
    review_result = review.rebuild_for_questions(db, user, set(question_ids))
    priorities = priority.compute_priorities(db, user, horizon="week", limit=40)
    priority.persist_snapshots(db, user, priorities, horizon="week")
    return {
        "topics": len(list(db.scalars(select(models.LearningState.id).where(models.LearningState.user_id == user.id)))),
        "review": review_result,
        "priorities": len(priorities),
        "model_version": MODEL_VERSION,
    }


def jobs(db: Session, user: models.User, limit: int = 20) -> list[dict]:
    rows = list(
        db.scalars(
            select(models.RecalculationJob)
            .where(models.RecalculationJob.user_id == user.id)
            .order_by(models.RecalculationJob.id.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": row.id,
            "scope": row.scope,
            "scope_id": row.scope_id,
            "trigger": row.trigger,
            "status": row.status,
            "incremental": row.incremental,
            "changes": row.changes,
            "started_at": common.jdatetime(row.started_at),
            "finished_at": common.jdatetime(row.finished_at),
            "model_version": row.model_version,
        }
        for row in rows
    ]


def audit_trail(db: Session, entity_type: Optional[str] = None, entity_id: Optional[int] = None, limit: int = 50) -> list[dict]:
    stmt = select(models.AuditEvent)
    if entity_type:
        stmt = stmt.where(models.AuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(models.AuditEvent.entity_id == entity_id)
    rows = list(db.scalars(stmt.order_by(models.AuditEvent.id.desc()).limit(limit)))
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "actor": row.actor,
            "reason": row.reason,
            "before": row.before,
            "after": row.after,
            "at": common.jdatetime(row.created_at),
        }
        for row in rows
    ]


def integrity_report(db: Session, user: models.User) -> dict:
    """A self-check that catches the classic corruptions the spec warns about."""
    issues: list[dict] = []
    # 1) responses that are ANSWERED but have no selected choice
    broken_entries = db.scalars(
        select(models.ResponseEntry).where(
            models.ResponseEntry.state == "ANSWERED", models.ResponseEntry.selected_choice.is_(None)
        )
    ).all()
    if broken_entries:
        issues.append({"code": "answered_without_choice", "count": len(broken_entries)})
    # 2) attempts that are current but reference a superseded answer key version
    mismatched = db.scalars(
        select(models.AttemptResult).where(
            models.AttemptResult.user_id == user.id,
            models.AttemptResult.is_current.is_(True),
            models.AttemptResult.state == "ANSWERED",
        )
    ).all()
    stale = 0
    needs_recalc: list[int] = []
    for attempt in mismatched:
        question = db.get(models.Question, attempt.question_id)
        if question and (question.current_answer_key or None) != (attempt.answer_key_value or None):
            stale += 1
            needs_recalc.append(attempt.question_id)
    if stale:
        issues.append(
            {
                "code": "stale_attempts_after_answer_key_change",
                "count": stale,
                "question_ids": sorted(set(needs_recalc))[:50],
                "hint": "بازمحاسبه لازم است (POST /recalculations).",
            }
        )
    # 3) sessions marked completed but with no attempts at all
    empty_done = db.scalar(
        select(models.TestSession.id)
        .where(models.TestSession.user_id == user.id, models.TestSession.status == "completed")
        .where(
            ~select(models.AttemptResult.id)
            .where(models.AttemptResult.session_id == models.TestSession.id)
            .exists()
        )
    )
    if empty_done:
        issues.append({"code": "completed_session_without_attempts", "session_id": empty_done})
    # 4) parity/learning state with missing evidence flag
    return {
        "checked_at": common.jdatetime(now_utc()),
        "issues": issues,
        "ok": not issues,
        "raw_data_untouched": True,
        "note": "این بررسی هیچ داده‌ای را تغییر نمی‌دهد؛ فقط ناسازگاری‌ها را گزارش می‌کند.",
    }
