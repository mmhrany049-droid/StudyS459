"""Curriculum: books, topic tree, taught checkboxes, prerequisite graph.

Key V3 rules implemented here:

* taught ≠ learned: ``taught_topics`` only records exposure;
* taught state cascades through the hierarchy (checking a chapter checks every
  descendant, unchecking clears them) while parents can be *indeterminate*;
* the dependency graph is a separate structure and cycles are rejected;
* question → topic mapping is correctable (audited, and it triggers recalculation).
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import CycleError, NotFoundError, ValidationError
from ..core.timeutil import now_utc, today_local
from ..db import models
from . import common

# ---------------------------------------------------------------------------
# Books & topics
# ---------------------------------------------------------------------------


def list_books(db: Session, user: models.User, include_inactive: bool = False) -> list[dict]:
    stmt = select(models.Book).order_by(models.Book.id)
    books = list(db.scalars(stmt))
    activations = {
        row.book_id: row.active
        for row in db.scalars(select(models.UserBookActivation).where(models.UserBookActivation.user_id == user.id))
    }
    result = []
    for book in books:
        active = activations.get(book.id, True)
        if not active and not include_inactive:
            continue
        result.append(
            {
                "id": book.id,
                "stable_key": book.stable_key,
                "title": book.title,
                "publisher": book.publisher,
                "subject_id": book.subject_id,
                "subject": book.subject.name if book.subject else None,
                "grade": book.grade,
                "active": active,
                "hierarchy_note": book.hierarchy_note,
                "topic_count": db.scalar(
                    select(func.count(models.Topic.id)).where(models.Topic.book_id == book.id)
                ),
                "plannable_topic_count": plannable_topic_count(db, book.id)["plannable"],
            }
        )
    return result


def topic_tree(db: Session, book_id: int, user: Optional[models.User] = None, with_stats: bool = True) -> dict:
    book = db.get(models.Book, book_id)
    if not book:
        raise NotFoundError("کتاب پیدا نشد.")
    topics = list(
        db.scalars(select(models.Topic).where(models.Topic.book_id == book_id).order_by(models.Topic.path, models.Topic.order_index))
    )
    taught_map: dict[int, bool] = {}
    if user:
        taught_map = {
            row.topic_id: row.taught
            for row in db.scalars(select(models.TaughtTopic).where(models.TaughtTopic.user_id == user.id))
        }
    question_counts = dict(
        db.execute(
            select(models.Question.primary_topic_id, func.count(models.Question.id))
            .where(models.Question.book_id == book_id, models.Question.active.is_(True))
            .group_by(models.Question.primary_topic_id)
        ).all()
    )
    children: dict[Optional[int], list[models.Topic]] = {}
    for topic in topics:
        children.setdefault(topic.parent_id, []).append(topic)

    def build(node: models.Topic) -> dict:
        kids = [build(child) for child in children.get(node.id, [])]
        direct_questions = question_counts.get(node.id, 0)
        total_questions = direct_questions + sum(k["total_questions"] for k in kids)
        if kids:
            taught_states = [k["taught_state"] for k in kids]
            if all(state == "checked" for state in taught_states):
                taught_state = "checked"
            elif all(state == "unchecked" for state in taught_states):
                taught_state = taught_map.get(node.id, False) and "checked" or "unchecked"
            else:
                taught_state = "indeterminate"
            if taught_map.get(node.id) and taught_state != "checked":
                taught_state = "indeterminate"
        else:
            taught_state = "checked" if taught_map.get(node.id) else "unchecked"
        return {
            "id": node.id,
            "title": node.title,
            "node_type": node.node_type,
            "parent_id": node.parent_id,
            "depth": node.depth,
            "order_index": node.order_index,
            "is_leaf": node.is_leaf,
            "direct_question_count": direct_questions,
            "total_questions": total_questions,
            # V3.1 doc 04: every topic is visible, only topics with a question bank
            # are plannable (time estimation, test suggestions, planner).
            "plannable": total_questions > 0,
            "plannable_reason": (
                f"{total_questions} سؤال در بانک این مبحث/زیرمباحث"
                if total_questions
                else "بانک تست ندارد؛ فقط در درخت آموزشی دیده می‌شود"
            ),
            "metadata": node.metadata_json or {},
            "taught_state": taught_state,
            "taught": bool(taught_map.get(node.id)),
            "children": kids,
        }

    roots = [build(topic) for topic in children.get(None, [])]
    payload = {
        "book": {
            "id": book.id,
            "title": book.title,
            "publisher": book.publisher,
            "hierarchy_note": book.hierarchy_note,
            "subject": book.subject.name if book.subject else None,
        },
        "topics": roots,
    }
    if with_stats:
        payload["stats"] = book_stats(db, book_id, user)
    return payload



def plannable_topic_ids(db: Session, topic_ids: Optional[Iterable[int]] = None) -> set[int]:
    """Topic ids whose *subtree* holds at least one active question.

    V3.1 doc 04: «همه مباحث میتوانند دیده شوند؛ همه plannable نیستند». Anything that
    estimates time, suggests a test or schedules work goes through this filter.
    """
    stmt = (
        select(models.Question.primary_topic_id)
        .where(models.Question.active.is_(True), models.Question.primary_topic_id.is_not(None))
        .distinct()
    )
    direct = {row for row in db.scalars(stmt) if row is not None}
    if not direct:
        return set()
    ancestors: set[int] = set()
    for topic_id in direct:
        topic = db.get(models.Topic, topic_id)
        if topic is None:
            continue
        ancestors.add(topic.id)
        parent_id = topic.parent_id
        guard = 0
        while parent_id and guard < 32:
            ancestors.add(parent_id)
            parent = db.get(models.Topic, parent_id)
            parent_id = parent.parent_id if parent else None
            guard += 1
    if topic_ids is not None:
        return ancestors & set(topic_ids)
    return ancestors


def plannable_topic_count(db: Session, book_id: int) -> dict:
    ids = plannable_topic_ids(db, [row for row in db.scalars(select(models.Topic.id).where(models.Topic.book_id == book_id))])
    total = db.scalar(select(func.count(models.Topic.id)).where(models.Topic.book_id == book_id)) or 0
    return {"plannable": len(ids), "total": total, "visible_only": total - len(ids)}


def book_stats(db: Session, book_id: int, user: Optional[models.User] = None) -> dict:
    total_questions = db.scalar(
        select(func.count(models.Question.id)).where(models.Question.book_id == book_id, models.Question.active.is_(True))
    ) or 0
    with_key = db.scalar(
        select(func.count(models.Question.id)).where(
            models.Question.book_id == book_id,
            models.Question.active.is_(True),
            models.Question.current_answer_key.is_not(None),
        )
    ) or 0
    taught = 0
    if user:
        taught = db.scalar(
            select(func.count(models.TaughtTopic.id))
            .join(models.Topic, models.Topic.id == models.TaughtTopic.topic_id)
            .where(models.TaughtTopic.user_id == user.id, models.Topic.book_id == book_id, models.TaughtTopic.taught.is_(True))
        ) or 0
    topic_count = db.scalar(select(func.count(models.Topic.id)).where(models.Topic.book_id == book_id)) or 0
    split = plannable_topic_count(db, book_id)
    return {
        "topic_count": topic_count,
        "question_count": total_questions,
        "questions_with_answer_key": with_key,
        "questions_missing_answer_key": total_questions - with_key,
        "taught_topics": taught,
        "plannable_topic_count": split["plannable"],
        "visible_only_topic_count": split["visible_only"],
        "plannable_rule": "فقط مبحثی که بانک تست دارد وارد تخمین زمان و برنامه می‌شود.",
    }


def topic_detail(db: Session, topic_id: int, user: models.User) -> dict:
    topic = db.get(models.Topic, topic_id)
    if not topic:
        raise NotFoundError("مبحث پیدا نشد.")
    taught = db.scalars(
        select(models.TaughtTopic).where(models.TaughtTopic.user_id == user.id, models.TaughtTopic.topic_id == topic_id)
    ).first()
    state = db.scalars(
        select(models.LearningState).where(models.LearningState.user_id == user.id, models.LearningState.topic_id == topic_id)
    ).first()
    prerequisites = list(
        db.scalars(
            select(models.Topic)
            .join(models.TopicDependency, models.TopicDependency.prerequisite_topic_id == models.Topic.id)
            .where(models.TopicDependency.dependent_topic_id == topic_id)
        )
    )
    dependents = list(
        db.scalars(
            select(models.Topic)
            .join(models.TopicDependency, models.TopicDependency.dependent_topic_id == models.Topic.id)
            .where(models.TopicDependency.prerequisite_topic_id == topic_id)
        )
    )

    def topic_brief(item: models.Topic) -> dict:
        return {"id": item.id, "title": item.title, "node_type": item.node_type, "book_id": item.book_id}

    return {
        "id": topic.id,
        "title": topic.title,
        "node_type": topic.node_type,
        "book_id": topic.book_id,
        "path": topic.path,
        "metadata": topic.metadata_json or {},
        "taught": {
            "taught": bool(taught and taught.taught),
            "taught_at": common.jdatetime(taught.taught_at) if taught else None,
            "source": taught.source if taught else None,
            "meaning": "تدریس‌شده یعنی دیده/خوانده شده؛ به معنی یادگرفته‌شده نیست.",
        },
        "learning_state": learning_state_payload(state),
        "prerequisites": [topic_brief(item) for item in prerequisites],
        "dependents": [topic_brief(item) for item in dependents],
        "question_count": db.scalar(
            select(func.count(models.Question.id)).where(
                models.Question.primary_topic_id == topic_id, models.Question.active.is_(True)
            )
        ) or 0,
    }


def learning_state_payload(state: Optional[models.LearningState]) -> Optional[dict]:
    if not state:
        return None
    return {
        "accuracy": state.accuracy,
        "coverage": state.coverage,
        "attempts": state.attempts,
        "answered": state.answered,
        "correct": state.correct,
        "wrong": state.wrong,
        "unanswered": state.unanswered,
        "not_entered": state.not_entered,
        "retention_estimate": state.retention_estimate,
        "confidence": state.confidence,
        "uncertainty": state.uncertainty,
        "recency_days": state.recency_days,
        "difficulty_adjusted": state.difficulty_adjusted,
        "repeated_error_signal": state.repeated_error_signal,
        "time_performance": state.time_performance,
        "exam_readiness": state.exam_readiness,
        "prerequisite_health": state.prerequisite_health,
        "evidence": state.evidence or {},
        "computed_at": common.jdatetime(state.computed_at),
        "model_version": state.model_version,
    }


# ---------------------------------------------------------------------------
# Taught topics (hierarchical checkbox with indeterminate parents)
# ---------------------------------------------------------------------------


def descendant_ids(db: Session, topic_id: int) -> list[int]:
    topic = db.get(models.Topic, topic_id)
    if not topic:
        raise NotFoundError("مبحث پیدا نشد.")
    prefix = f"{topic.path}{topic.id}/%"
    rows = db.scalars(
        select(models.Topic.id).where(
            models.Topic.id != topic_id,
            (models.Topic.path.like(prefix)) | (models.Topic.parent_id == topic_id),
        )
    )
    return list(rows)


def set_taught(
    db: Session,
    user: models.User,
    topic_id: int,
    taught: bool,
    *,
    cascade: bool = True,
    source: str = "manual",
    class_id: Optional[int] = None,
) -> dict:
    """Set the taught checkbox. Cascade is mandatory in the UI contract, but the
    service keeps it explicit so that single-leaf toggles stay possible."""
    topic = db.get(models.Topic, topic_id)
    if not topic:
        raise NotFoundError("مبحث پیدا نشد.")
    targets = [topic_id]
    if cascade:
        targets.extend(descendant_ids(db, topic_id))
    now = now_utc()
    existing = {
        row.topic_id: row
        for row in db.scalars(select(models.TaughtTopic).where(models.TaughtTopic.user_id == user.id))
    }
    changed = []
    for target_id in targets:
        row = existing.get(target_id)
        if row is None:
            row = models.TaughtTopic(
                user_id=user.id, topic_id=target_id, taught=taught, source=source,
                taught_at=now if taught else None, class_id=class_id,
            )
            db.add(row)
        else:
            if row.taught == taught and source != "cascade":
                continue
            row.taught = taught
            row.source = source
            row.taught_at = now if taught else None
            row.class_id = class_id
        changed.append(target_id)
    db.flush()
    common.audit(
        db,
        "taught_topic_changed",
        user_id=user.id,
        entity_type="topic",
        entity_id=topic_id,
        reason=f"taught={taught} cascade={cascade}",
        after={"topic_ids": changed, "taught": taught},
    )
    common.observe(db, user.id, "taught_toggle", payload={"topic_id": topic_id, "taught": taught, "cascade": cascade}, source="user")
    return {
        "topic_id": topic_id,
        "taught": taught,
        "affected": changed,
        "cascade": cascade,
        "note": "تدریس‌شده فقط نشان‌دهنده پوشش/تدریس است، نه تسلط.",
    }


def taught_summary(db: Session, user: models.User) -> dict:
    rows = list(
        db.execute(
            select(models.Topic.book_id, func.count(models.TaughtTopic.id))
            .join(models.Topic, models.Topic.id == models.TaughtTopic.topic_id)
            .where(models.TaughtTopic.user_id == user.id, models.TaughtTopic.taught.is_(True))
            .group_by(models.Topic.book_id)
        ).all()
    )
    return {"by_book": [{"book_id": book_id, "count": count} for book_id, count in rows]}


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def add_dependency(
    db: Session,
    prerequisite_topic_id: int,
    dependent_topic_id: int,
    *,
    strength: float = 0.5,
    source: str = "user",
    note: Optional[str] = None,
) -> models.TopicDependency:
    if prerequisite_topic_id == dependent_topic_id:
        raise CycleError("یک مبحث نمی‌تواند پیش‌نیاز خودش باشد.")
    for topic_id in (prerequisite_topic_id, dependent_topic_id):
        if not db.get(models.Topic, topic_id):
            raise NotFoundError("مبحث پیدا نشد.")
    if _would_cycle(db, prerequisite_topic_id, dependent_topic_id):
        raise CycleError("این رابطه باعث حلقه در گراف پیش‌نیازها می‌شود.")
    existing = db.scalars(
        select(models.TopicDependency).where(
            models.TopicDependency.prerequisite_topic_id == prerequisite_topic_id,
            models.TopicDependency.dependent_topic_id == dependent_topic_id,
        )
    ).first()
    if existing:
        existing.strength = strength
        existing.note = note
        db.flush()
        return existing
    dependency = models.TopicDependency(
        prerequisite_topic_id=prerequisite_topic_id,
        dependent_topic_id=dependent_topic_id,
        strength=strength,
        source=source,
        note=note,
    )
    db.add(dependency)
    db.flush()
    common.audit(
        db,
        "dependency_added",
        entity_type="topic_dependency",
        entity_id=dependency.id,
        after={"prerequisite": prerequisite_topic_id, "dependent": dependent_topic_id},
    )
    return dependency


def _would_cycle(db: Session, prerequisite_topic_id: int, dependent_topic_id: int) -> bool:
    """Adding prereq→dependent is a cycle if prerequisite is reachable from dependent."""
    edges = db.execute(
        select(models.TopicDependency.prerequisite_topic_id, models.TopicDependency.dependent_topic_id)
    ).all()
    adjacency: dict[int, list[int]] = {}
    for src, dst in edges:
        adjacency.setdefault(src, []).append(dst)
    stack = [dependent_topic_id]
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        if node == prerequisite_topic_id:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, []))
    return False


def prerequisites_of(db: Session, topic_id: int) -> list[models.Topic]:
    return list(
        db.scalars(
            select(models.Topic)
            .join(models.TopicDependency, models.TopicDependency.prerequisite_topic_id == models.Topic.id)
            .where(models.TopicDependency.dependent_topic_id == topic_id)
        )
    )


def dependency_graph(db: Session, book_id: Optional[int] = None) -> dict:
    stmt = select(models.TopicDependency)
    deps = list(db.scalars(stmt))
    if book_id is not None:
        topic_ids = {
            row for row in db.scalars(select(models.Topic.id).where(models.Topic.book_id == book_id))
        }
        deps = [d for d in deps if d.prerequisite_topic_id in topic_ids and d.dependent_topic_id in topic_ids]
    return {
        "edges": [
            {
                "id": dep.id,
                "prerequisite_topic_id": dep.prerequisite_topic_id,
                "dependent_topic_id": dep.dependent_topic_id,
                "strength": dep.strength,
                "source": dep.source,
            }
            for dep in deps
        ]
    }


def activate_book(db: Session, user: models.User, book_id: int, active: bool) -> dict:
    book = db.get(models.Book, book_id)
    if not book:
        raise NotFoundError("کتاب پیدا نشد.")
    row = db.scalars(
        select(models.UserBookActivation).where(
            models.UserBookActivation.user_id == user.id, models.UserBookActivation.book_id == book_id
        )
    ).first()
    if row is None:
        row = models.UserBookActivation(user_id=user.id, book_id=book_id, active=active, activated_at=now_utc())
        db.add(row)
    else:
        row.active = active
    db.flush()
    common.audit(
        db, "book_activation_changed", user_id=user.id, entity_type="book", entity_id=book_id,
        after={"active": active},
    )
    return {"book_id": book_id, "active": active, "history_preserved": True}


def create_topic(
    db: Session,
    book_id: int,
    title: str,
    *,
    parent_id: Optional[int] = None,
    node_type: str = "topic",
    order_index: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> models.Topic:
    book = db.get(models.Book, book_id)
    if not book:
        raise NotFoundError("کتاب پیدا نشد.")
    parent = None
    if parent_id:
        parent = db.get(models.Topic, parent_id)
        if not parent:
            raise NotFoundError("مبحث والد پیدا نشد.")
        if parent.book_id != book_id:
            raise ValidationError("والد باید از همان کتاب باشد.")
    siblings = db.scalar(
        select(func.count(models.Topic.id)).where(models.Topic.book_id == book_id, models.Topic.parent_id == parent_id)
    ) or 0
    topic = models.Topic(
        book_id=book_id,
        parent_id=parent_id,
        node_type=node_type,
        title=title,
        order_index=order_index if order_index is not None else siblings,
        depth=(parent.depth + 1) if parent else 0,
        metadata_json=metadata or {},
    )
    db.add(topic)
    db.flush()
    topic.path = (parent.path + f"{parent.id}/") if parent else "/"
    if parent:
        parent.is_leaf = False
    db.flush()
    return topic


def update_question_mapping(
    db: Session, question_id: int, topic_ids: Iterable[int], relation: str = "related", reason: Optional[str] = None
) -> dict:
    """Topic mapping is correctable; the correction is audited and triggers a rebuild."""
    question = db.get(models.Question, question_id)
    if not question:
        raise NotFoundError("سؤال پیدا نشد.")
    before = [
        {"topic_id": row.topic_id, "relation": row.relation}
        for row in db.scalars(select(models.QuestionTopic).where(models.QuestionTopic.question_id == question_id))
    ]
    for topic_id in topic_ids:
        if not db.get(models.Topic, topic_id):
            raise NotFoundError(f"مبحث {topic_id} پیدا نشد.")
        exists = db.scalars(
            select(models.QuestionTopic).where(
                models.QuestionTopic.question_id == question_id,
                models.QuestionTopic.topic_id == topic_id,
                models.QuestionTopic.relation == relation,
            )
        ).first()
        if not exists:
            db.add(models.QuestionTopic(question_id=question_id, topic_id=topic_id, relation=relation, source="manual"))
    db.flush()
    common.audit(
        db,
        "question_topic_mapping_corrected",
        entity_type="question",
        entity_id=question_id,
        reason=reason,
        before={"mappings": before},
        after={"added": list(topic_ids), "relation": relation},
    )
    return {"question_id": question_id, "added": list(topic_ids), "relation": relation, "recalc_required": True}


def ensure_seeded(db: Session, user: models.User) -> dict:
    """Idempotently load the repository book content + V2 default classes."""
    from ..db.seed import seed_all

    return seed_all(db, user)
