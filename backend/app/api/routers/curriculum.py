"""Curriculum router: books, topic tree, taught checkboxes, dependencies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.timeutil import today_local
from ...db.base import get_db
from ...db import models
from ...db.curriculum_outline import curriculum_overview
from ...services import common, curriculum, learning
from ..deps import current_user

router = APIRouter(tags=["curriculum"])


class TaughtPayload(BaseModel):
    taught: bool = True
    cascade: bool = True
    source: str = "manual"


class TopicPayload(BaseModel):
    title: str
    parent_id: int | None = None
    node_type: str = "topic"
    metadata: dict | None = None


class DependencyPayload(BaseModel):
    prerequisite_topic_id: int
    dependent_topic_id: int
    strength: float = 0.5
    note: str | None = None


class MappingPayload(BaseModel):
    topic_ids: list[int]
    relation: str = "related"
    reason: str | None = None


@router.get("/curriculum/overview")
def overview(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Grades ۱۰–۱۲ with the visible/plannable split (V3.1 doc 04)."""
    return curriculum_overview(db, user)


@router.get("/books")
def list_books(
    include_inactive: bool = False,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    books = curriculum.list_books(db, user, include_inactive=include_inactive)
    for book in books:
        book["stats"] = curriculum.book_stats(db, book["id"], user)
    return {"books": books}


@router.get("/books/{book_id}")
def book_detail(book_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    book = db.get(models.Book, book_id)
    if not book:
        from ...core.errors import NotFoundError

        raise NotFoundError("کتاب پیدا نشد.")
    return {
        "id": book.id,
        "title": book.title,
        "publisher": book.publisher,
        "subject": book.subject.name if book.subject else None,
        "hierarchy_note": book.hierarchy_note,
        "stats": curriculum.book_stats(db, book_id, user),
        "question_bank": question_bank_summary(db, book_id),
    }


def question_bank_summary(db: Session, book_id: int) -> dict:
    from sqlalchemy import func, select

    rows = db.execute(
        select(
            models.Question.primary_topic_id,
            func.count(models.Question.id),
            func.count(models.Question.current_answer_key),
        )
        .where(models.Question.book_id == book_id, models.Question.active.is_(True))
        .group_by(models.Question.primary_topic_id)
    ).all()
    return {
        "by_topic": [
            {"topic_id": topic_id, "questions": total, "with_answer_key": with_key}
            for topic_id, total, with_key in rows
        ],
        "total": sum(total for _, total, _ in rows),
        "note": "بانک تست هر مبحث در همان صفحه کتاب مدیریت می‌شود، نه در تنظیمات.",
    }


@router.get("/books/{book_id}/tree")
def tree(book_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    payload = curriculum.topic_tree(db, book_id, user)
    db.commit()
    return payload


@router.get("/books/{book_id}/test-sets")
def test_sets(book_id: int, db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import select

    rows = db.scalars(select(models.TestSet).where(models.TestSet.book_id == book_id).order_by(models.TestSet.topic_id))
    return {
        "test_sets": [
            {
                "id": row.id,
                "topic_id": row.topic_id,
                "title": row.title,
                "test_type": row.test_type,
                "difficulty_level": row.difficulty_level,
            }
            for row in rows
        ]
    }


@router.post("/books/{book_id}/topics")
def create_topic(
    book_id: int,
    payload: TopicPayload,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
) -> dict:
    topic = curriculum.create_topic(
        db, book_id, payload.title, parent_id=payload.parent_id, node_type=payload.node_type, metadata=payload.metadata
    )
    db.commit()
    return {"id": topic.id, "title": topic.title, "node_type": topic.node_type, "path": topic.path}


@router.get("/topics/{topic_id}")
def topic_detail(topic_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    payload = curriculum.topic_detail(db, topic_id, user)
    db.commit()
    return payload


@router.post("/topics/{topic_id}/taught")
def set_taught(
    topic_id: int,
    payload: TaughtPayload,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = curriculum.set_taught(
        db, user, topic_id, payload.taught, cascade=payload.cascade, source=payload.source
    )
    db.commit()
    return result


@router.get("/topics/{topic_id}/history")
def topic_history(topic_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    from ...services import analytics

    return analytics.topic_history(db, user, topic_id)


@router.get("/topic-dependencies")
def dependencies(book_id: int | None = None, db: Session = Depends(get_db)) -> dict:
    return curriculum.dependency_graph(db, book_id)


@router.post("/topic-dependencies")
def add_dependency(payload: DependencyPayload, db: Session = Depends(get_db)) -> dict:
    dependency = curriculum.add_dependency(
        db,
        payload.prerequisite_topic_id,
        payload.dependent_topic_id,
        strength=payload.strength,
        note=payload.note,
    )
    db.commit()
    return {
        "id": dependency.id,
        "prerequisite_topic_id": dependency.prerequisite_topic_id,
        "dependent_topic_id": dependency.dependent_topic_id,
        "note": "حلقه‌ها رد می‌شوند و گراف پیش‌نیاز جدا از درخت محتوا نگه داشته می‌شود.",
    }


@router.post("/users/me/books/{book_id}/activate")
def activate(book_id: int, active: bool = True, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = curriculum.activate_book(db, user, book_id, active)
    db.commit()
    return result


@router.get("/learning/state/{topic_id}")
def topic_state(topic_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    learning.compute_state_for_topic(db, user, topic_id)
    db.commit()
    from sqlalchemy import select

    state = db.scalars(
        select(models.LearningState).where(
            models.LearningState.user_id == user.id, models.LearningState.topic_id == topic_id
        )
    ).first()
    return curriculum.learning_state_payload(state) or {"topic_id": topic_id, "message": "شواهدی ثبت نشده است."}
