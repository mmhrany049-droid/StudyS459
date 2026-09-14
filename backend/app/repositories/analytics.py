"""Analytics read queries. Attempts are the source of truth (spec 07)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Question,
    QuestionAttempt,
    ReviewQueue,
    TestSession,
    TestSessionQuestion,
)


def finished_sessions(db: Session, user_id: int) -> list[TestSession]:
    stmt = (
        select(TestSession)
        .where(TestSession.user_id == user_id, TestSession.status != "in_progress")
        .order_by(TestSession.started_at, TestSession.id)
    )
    return list(db.execute(stmt).scalars().all())


def finals_rows(db: Session, user_id: int) -> list[tuple]:
    """Latest attempt per (finished session, question), with keys + session times.

    Returns (session_id, question_id, answer, result, answered_at,
             answer_key, difficulty, book_id, started_at, ended_at).
    """
    latest = (
        select(
            QuestionAttempt.session_id,
            QuestionAttempt.question_id,
            func.max(QuestionAttempt.id).label("max_id"),
        )
        .join(TestSession, TestSession.id == QuestionAttempt.session_id)
        .where(QuestionAttempt.user_id == user_id, TestSession.status != "in_progress")
        .group_by(QuestionAttempt.session_id, QuestionAttempt.question_id)
        .subquery()
    )
    stmt = (
        select(
            QuestionAttempt.session_id,
            QuestionAttempt.question_id,
            QuestionAttempt.answer,
            QuestionAttempt.result,
            QuestionAttempt.answered_at,
            Question.answer_key,
            Question.difficulty_level,
            Question.book_id,
            TestSession.started_at,
            TestSession.ended_at,
        )
        .join(latest, QuestionAttempt.id == latest.c.max_id)
        .join(Question, Question.id == QuestionAttempt.question_id)
        .join(TestSession, TestSession.id == QuestionAttempt.session_id)
    )
    return list(db.execute(stmt).all())


def finished_members(db: Session, user_id: int) -> list[tuple[int, int]]:
    """(session_id, question_id) pairs of finished sessions (coverage base)."""
    stmt = (
        select(TestSessionQuestion.session_id, TestSessionQuestion.question_id)
        .join(TestSession, TestSession.id == TestSessionQuestion.session_id)
        .where(TestSession.user_id == user_id, TestSession.status != "in_progress")
    )
    return [(s, q) for s, q in db.execute(stmt).all()]


def question_attempts(
    db: Session, *, user_id: int, question_id: int
) -> list[QuestionAttempt]:
    stmt = (
        select(QuestionAttempt)
        .where(QuestionAttempt.user_id == user_id, QuestionAttempt.question_id == question_id)
        .order_by(QuestionAttempt.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


# -- review queue ------------------------------------------------------
def open_review_exists(
    db: Session, *, user_id: int, entity_type: str, entity_id: int, reason: str
) -> bool:
    stmt = select(func.count(ReviewQueue.id)).where(
        ReviewQueue.user_id == user_id,
        ReviewQueue.entity_type == entity_type,
        ReviewQueue.entity_id == entity_id,
        ReviewQueue.reason == reason,
        ReviewQueue.status == "pending",
    )
    return bool(db.execute(stmt).scalar())


def add_review(
    db: Session,
    *,
    user_id: int,
    entity_type: str,
    entity_id: int,
    reason: str,
    priority: str,
) -> ReviewQueue:
    row = ReviewQueue(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        priority=priority,
        scheduled_for=None,  # no spaced repetition in v1 (spec 18 #3)
        status="pending",
    )
    db.add(row)
    db.flush()
    return row


def pending_reviews(db: Session, user_id: int) -> list[ReviewQueue]:
    stmt = (
        select(ReviewQueue)
        .where(ReviewQueue.user_id == user_id, ReviewQueue.status == "pending")
        .order_by(ReviewQueue.id)
    )
    return list(db.execute(stmt).scalars().all())


def mark_review_done(db: Session, review_id: int) -> None:
    row = db.get(ReviewQueue, review_id)
    if row is not None:
        row.status = "done"
        db.flush()
