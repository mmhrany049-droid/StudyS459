"""Review engine.

V2 owns the exact numbers and they are inherited unchanged:

* at most 25 questions per review session;
* clustered *topic-near* questions (shared topic, or a common ancestor within
  depth 2), presented in a **random** order;
* critical = a question wrong at least twice -> it should come back within 2 days;
  other wrong/unanswered items -> within 3 days.

V3 adds: the intervention type is chosen before the questions
(``ERROR_REVIEW`` vs ``REVIEW`` vs ``ACTIVE_RECALL`` etc.) and the review queue is
rebuilt from raw attempts, never hand-maintained.
"""

from __future__ import annotations

import datetime as _dt
import random
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import now_utc, today_local
from ..db import models
from ..domain.enums import InterventionType, ReviewItemState, ReviewReason
from . import common


def _topic_ancestors(db: Session, topic: models.Topic) -> list[int]:
    ids: list[int] = []
    current = topic
    while current.parent_id:
        current = db.get(models.Topic, current.parent_id)
        if not current:
            break
        ids.append(current.id)
    return ids


def topics_near(db: Session, topic_a: Optional[int], topic_b: Optional[int]) -> bool:
    """V2 definition of 'topic near': shared node, or common ancestor within depth 2."""
    if topic_a is None or topic_b is None:
        return False
    if topic_a == topic_b:
        return True
    a = db.get(models.Topic, topic_a)
    b = db.get(models.Topic, topic_b)
    if not a or not b:
        return False
    depth_limit = config.value("review.cluster_common_parent_depth")
    a_ancestors = _topic_ancestors(db, a)[:depth_limit]
    b_ancestors = _topic_ancestors(db, b)[:depth_limit]
    return bool(set(a_ancestors) & set(b_ancestors))


# ---------------------------------------------------------------------------
# Queue maintenance (rebuilt from raw attempts)
# ---------------------------------------------------------------------------


def sync_from_session(db: Session, user: models.User, session: models.TestSession) -> dict:
    """Materialise review items after a session. Correct answers in a *review*
    session resolve the existing item; wrong/unanswered items are opened/kept."""
    attempts = list(
        db.scalars(
            select(models.AttemptResult).where(
                models.AttemptResult.session_id == session.id, models.AttemptResult.is_current.is_(True)
            )
        )
    )
    question_ids = [a.question_id for a in attempts]
    return rebuild_for_questions(db, user, set(question_ids), session=session, attempts=attempts)


def rebuild_for_questions(
    db: Session,
    user: models.User,
    question_ids: Iterable[int],
    *,
    session: Optional[models.TestSession] = None,
    attempts: Optional[list[models.AttemptResult]] = None,
) -> dict:
    """Recompute review items for a set of questions from their current attempts."""
    ids = {q for q in question_ids if q}
    if not ids:
        return {"opened": 0, "resolved": 0, "updated": 0}
    if attempts is None:
        attempts = list(
            db.scalars(
                select(models.AttemptResult).where(
                    models.AttemptResult.user_id == user.id,
                    models.AttemptResult.question_id.in_(ids),
                    models.AttemptResult.is_current.is_(True),
                )
            )
        )
    by_question: dict[int, list[models.AttemptResult]] = {}
    for attempt in attempts:
        if attempt.question_id in ids:
            by_question.setdefault(attempt.question_id, []).append(attempt)

    existing = {
        row.question_id: row
        for row in db.scalars(
            select(models.ReviewItem).where(
                models.ReviewItem.user_id == user.id,
                models.ReviewItem.question_id.in_(ids),
                models.ReviewItem.state == ReviewItemState.OPEN.value,
            )
        )
    }
    critical_threshold = config.value("review.critical_wrong_count")
    normal_days = config.value("review.normal_max_days")
    critical_days = config.value("review.critical_max_days")
    opened = resolved = updated = 0
    today = today_local()
    for question_id, question_attempts in by_question.items():
        question_attempts.sort(key=lambda a: a.evaluated_at or now_utc())
        wrong_count = sum(1 for a in question_attempts if a.result == "WRONG")
        unanswered_count = sum(1 for a in question_attempts if a.result == "UNANSWERED")
        last = question_attempts[-1]
        topic_id = last.topic_id
        row = existing.get(question_id)
        # a correct answer inside a review-ish session resolves the item
        last_session = db.get(models.TestSession, last.session_id) if last.session_id else None
        resolved_by_correct = (
            last.result == "CORRECT"
            and last_session is not None
            and last_session.session_type in {"review", "practice"}
            and last_session.intervention_type in {
                InterventionType.REVIEW.value,
                InterventionType.ERROR_REVIEW.value,
                InterventionType.ACTIVE_RECALL.value,
            }
        )
        if resolved_by_correct and row is not None:
            row.state = ReviewItemState.RESOLVED.value
            row.resolved_at = now_utc()
            resolved += 1
            continue
        if wrong_count == 0 and unanswered_count == 0:
            if row is not None:
                row.state = ReviewItemState.RESOLVED.value
                row.resolved_at = now_utc()
                resolved += 1
            continue
        priority = (
            "critical" if wrong_count >= critical_threshold else
            "high" if wrong_count == 1 and unanswered_count > 0 else
            "normal"
        )
        reason = (
            ReviewReason.CRITICAL.value if priority == "critical"
            else ReviewReason.WRONG.value if wrong_count
            else ReviewReason.UNANSWERED.value
        )
        # critical items return within 2 days, everything else within 3 (V2 rule)
        horizon = today + _dt.timedelta(days=critical_days if priority == "critical" else normal_days)
        if row is not None and row.scheduled_for:
            horizon = min(row.scheduled_for, horizon)
        if row is None:
            row = models.ReviewItem(
                user_id=user.id,
                question_id=question_id,
                topic_id=topic_id,
                reason=reason,
                priority=priority,
                wrong_count=wrong_count,
                unanswered_count=unanswered_count,
                state=ReviewItemState.OPEN.value,
                scheduled_for=horizon,
                source_session_id=last.session_id,
                last_attempt_id=last.id,
                evidence={"attempts": len(question_attempts)},
            )
            db.add(row)
            opened += 1
        else:
            row.reason = reason
            row.priority = priority
            row.wrong_count = wrong_count
            row.unanswered_count = unanswered_count
            row.topic_id = topic_id
            row.scheduled_for = min(row.scheduled_for or horizon, horizon) if row.scheduled_for else horizon
            row.last_attempt_id = last.id
            row.evidence = {"attempts": len(question_attempts)}
            updated += 1
    db.flush()
    return {"opened": opened, "resolved": resolved, "updated": updated}


def open_items(
    db: Session,
    user: models.User,
    *,
    topic_id: Optional[int] = None,
    include_descendants: bool = True,
    limit: Optional[int] = None,
) -> list[models.ReviewItem]:
    stmt = select(models.ReviewItem).where(
        models.ReviewItem.user_id == user.id, models.ReviewItem.state == ReviewItemState.OPEN.value
    )
    if topic_id:
        if include_descendants:
            topic = db.get(models.Topic, topic_id)
            if topic:
                ids = [topic.id] + list(
                    db.scalars(select(models.Topic.id).where(models.Topic.path.like(f"{topic.path}{topic.id}/%")))
                )
                stmt = stmt.where(models.ReviewItem.topic_id.in_(ids))
        else:
            stmt = stmt.where(models.ReviewItem.topic_id == topic_id)
    priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    items = list(db.scalars(stmt))
    items.sort(key=lambda item: (priority_order.get(item.priority, 3), item.scheduled_for or today_local()))
    return items[:limit] if limit else items


def queue_stats(db: Session, user: models.User) -> dict:
    rows = db.execute(
        select(models.ReviewItem.priority, func.count(models.ReviewItem.id))
        .where(models.ReviewItem.user_id == user.id, models.ReviewItem.state == ReviewItemState.OPEN.value)
        .group_by(models.ReviewItem.priority)
    ).all()
    by_priority = {priority: count for priority, count in rows}
    due_today = db.scalar(
        select(func.count(models.ReviewItem.id)).where(
            models.ReviewItem.user_id == user.id,
            models.ReviewItem.state == ReviewItemState.OPEN.value,
            models.ReviewItem.scheduled_for <= today_local(),
        )
    ) or 0
    return {
        "open": sum(by_priority.values()),
        "by_priority": by_priority,
        "due_today": due_today,
        "critical": by_priority.get("critical", 0),
    }


def build_review_session(
    db: Session,
    user: models.User,
    *,
    max_questions: Optional[int] = None,
    topic_id: Optional[int] = None,
    seed: Optional[int] = None,
    dry_run: bool = False,
) -> dict:
    """Construct the clustered + shuffled review selection (the mandatory V2 rule)."""
    max_questions = max_questions or config.value("review.max_questions_per_session")
    min_cluster = config.value("review.min_cluster_size")
    items = open_items(db, user, topic_id=topic_id, limit=max_questions)
    if not items:
        return {"questions": [], "session_available": False, "message": "صف مرور خالی است."}
    rng = random.Random(seed)
    # 1) cluster around the highest priority seed
    seeds = [item for item in items if item.priority in {"critical", "high"}] or items
    anchor = seeds[0]
    cluster = [item for item in items if topics_near(db, item.topic_id, anchor.topic_id)]
    if len(cluster) < min_cluster:
        # 2) top up with the nearest available topics (never silently empty)
        others = [item for item in items if item not in cluster]
        cluster.extend(others[: max(0, min_cluster - len(cluster))])
    cluster = cluster[:max_questions]
    rng.shuffle(cluster)  # 3) random presentation order
    question_ids = [item.question_id for item in cluster]
    payload = {
        "anchor_topic_id": anchor.topic_id,
        "cluster_size": len(cluster),
        "requested_max": max_questions,
        "min_cluster": min_cluster,
        "question_ids": question_ids,
        "items": [
            {
                "question_id": item.question_id,
                "topic_id": item.topic_id,
                "priority": item.priority,
                "reason": item.reason,
                "wrong_count": item.wrong_count,
                "unanswered_count": item.unanswered_count,
                "scheduled_for": common.jdate(item.scheduled_for),
            }
            for item in cluster
        ],
        "session_available": True,
        "ordering": "random",
        "parity_applied": False,
        "message": None,
    }
    if not dry_run:
        payload["intervention_type"] = InterventionType.ERROR_REVIEW.value if any(
            item.priority == "critical" for item in cluster
        ) else InterventionType.REVIEW.value
    return payload


def snooze_item(db: Session, user: models.User, item_id: int, days: int = 1) -> dict:
    item = db.get(models.ReviewItem, item_id)
    if not item or item.user_id != user.id:
        from ..core.errors import NotFoundError

        raise NotFoundError("آیتم مرور پیدا نشد.")
    item.scheduled_for = today_local() + _dt.timedelta(days=max(1, days))
    db.flush()
    return {"item_id": item_id, "scheduled_for": common.jdate(item.scheduled_for)}


def resolve_item(db: Session, user: models.User, item_id: int, reason: str = "manual") -> dict:
    item = db.get(models.ReviewItem, item_id)
    if not item or item.user_id != user.id:
        from ..core.errors import NotFoundError

        raise NotFoundError("آیتم مرور پیدا نشد.")
    item.state = ReviewItemState.RESOLVED.value
    item.resolved_at = now_utc()
    item.evidence = {**(item.evidence or {}), "resolved_reason": reason}
    db.flush()
    common.audit(db, "review_item_resolved", user_id=user.id, entity_type="review_item", entity_id=item_id, reason=reason)
    return {"item_id": item_id, "state": item.state}
