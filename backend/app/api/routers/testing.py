"""Test engine router: selection, sessions, response sheets, results, review."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.errors import NotFoundError
from ...db import models
from ...db.base import get_db
from ...services import common, review, selection, sessions
from ..deps import current_user, parse_day

router = APIRouter(tags=["test-engine"])


class EntryPayload(BaseModel):
    question_id: int
    state: Optional[str] = None
    selected_choice: Optional[str] = None
    unanswered: Optional[bool] = None
    not_entered: Optional[bool] = None
    response_time_seconds: Optional[int] = None


class SessionCreatePayload(BaseModel):
    book_id: Optional[int] = None
    topic_id: Optional[int] = None
    count: int = 20
    sequence_from: Optional[int] = None
    sequence_to: Optional[int] = None
    parity: str = "any"
    difficulty_level: Optional[int] = None
    timed: bool = False
    time_limit_seconds: Optional[int] = None
    session_type: str = "practice"
    intervention_type: Optional[str] = None
    task_id: Optional[int] = None
    exam_id: Optional[int] = None
    planned_date: Optional[str] = None
    include_descendants: bool = False
    seed: Optional[int] = None
    start_now: bool = True


class FinishPayload(BaseModel):
    actual_duration_minutes: Optional[int] = None
    entries: list[EntryPayload] = []


class ReviewBuildPayload(BaseModel):
    max_questions: Optional[int] = None
    topic_id: Optional[int] = None
    create_session: bool = False
    task_id: Optional[int] = None
    seed: Optional[int] = None


@router.get("/test-engine/pool")
def pool_preview(
    book_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    sequence_from: Optional[int] = None,
    sequence_to: Optional[int] = None,
    parity: str = "any",
    include_descendants: bool = False,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    payload = sessions.preview_selection(
        db,
        user,
        book_id=book_id,
        topic_id=topic_id,
        include_descendants=include_descendants,
        seq_from=sequence_from,
        seq_to=sequence_to,
        parity=parity,
    )
    if topic_id:
        payload["suggested_parity"] = sessions.suggested_parity(db, user, topic_id)
        payload["selection_stats"] = selection.selection_stats(db, user, topic_id)
    return payload


@router.post("/test-sessions")
def create_session(
    payload: SessionCreatePayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    session = sessions.create_session(db, user, payload.model_dump())
    db.commit()
    return sessions.session_payload(db, session.id)


@router.get("/test-sessions")
def list_sessions(
    limit: int = Query(50, le=200), offset: int = 0, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    return {"sessions": sessions.session_history(db, user, limit=limit, offset=offset)}


def _owned_session(db: Session, user: models.User, session_id: int) -> models.TestSession:
    """Every session endpoint goes through this: no cross-user reads."""
    session = db.get(models.TestSession, session_id)
    if not session or session.user_id != user.id:
        raise NotFoundError("جلسه آزمون پیدا نشد.")
    return session


@router.get("/test-sessions/{session_id}")
def get_session(session_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    _owned_session(db, user, session_id)
    return sessions.session_payload(db, session_id)


@router.post("/test-sessions/{session_id}/start")
def start_session(session_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    _owned_session(db, user, session_id)
    result = sessions.start_session(db, session_id)
    db.commit()
    return result


@router.post("/test-sessions/{session_id}/entries")
def save_entries(
    session_id: int,
    entries: list[EntryPayload],
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = sessions.save_entries(db, user, session_id, [entry.model_dump() for entry in entries])
    db.commit()
    return result


@router.post("/test-sessions/{session_id}/submit")
def submit_session(
    session_id: int,
    payload: FinishPayload,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.entries:
        sessions.save_entries(db, user, session_id, [entry.model_dump() for entry in payload.entries])
    result = sessions.finish_session(
        db, user, session_id, actual_duration_minutes=payload.actual_duration_minutes
    )
    db.commit()
    return result


@router.post("/test-sessions/{session_id}/duration")
def record_duration(
    session_id: int,
    actual_duration_minutes: int = Query(..., gt=0),
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Answered *after* completion — the user is never asked to predict duration."""
    session = db.get(models.TestSession, session_id)
    if not session:
        from ...core.errors import NotFoundError

        raise NotFoundError("جلسه تست پیدا نشد.")
    session.actual_duration_minutes = actual_duration_minutes
    from ...services import duration as duration_service

    duration_service.record_observation(
        db,
        user,
        actual_minutes=actual_duration_minutes,
        task_type=session.session_type,
        question_count=session.planned_question_count,
        topic_id=session.topic_id,
        book_id=session.book_id,
        session_id=session.id,
        predicted_low=session.planned_duration_low,
        predicted_high=session.planned_duration_high,
    )
    db.commit()
    return {"session_id": session_id, "actual_duration_minutes": actual_duration_minutes, "recorded": True}


@router.get("/test-sessions/{session_id}/result")
def session_result(session_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    _owned_session(db, user, session_id)
    return sessions.session_result(db, session_id)


@router.post("/questions/{question_id}/reevaluate")
def reevaluate(question_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = sessions.reevaluate_question(db, user, question_id)
    db.commit()
    return result


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------


@router.get("/review/queue")
def review_queue(
    topic_id: Optional[int] = None,
    limit: int = Query(50, le=200),
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = review.open_items(db, user, topic_id=topic_id, limit=limit)
    questions = {
        question.id: question.sequence_no
        for question in db.query(models.Question).filter(models.Question.id.in_([item.question_id for item in items] or [0]))
    }
    topics = {
        topic.id: topic.title
        for topic in db.query(models.Topic).filter(models.Topic.id.in_([item.topic_id for item in items] or [0]))
    }
    return {
        "stats": review.queue_stats(db, user),
        "items": [
            {
                "id": item.id,
                "question_id": item.question_id,
                "sequence_no": questions.get(item.question_id),
                "topic_id": item.topic_id,
                "topic_title": topics.get(item.topic_id),
                "reason": item.reason,
                "priority": item.priority,
                "wrong_count": item.wrong_count,
                "unanswered_count": item.unanswered_count,
                "scheduled_for": common.jdate(item.scheduled_for),
                "evidence": item.evidence,
            }
            for item in items
        ],
    }


@router.post("/review/build")
def build_review(
    payload: ReviewBuildPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    plan = review.build_review_session(
        db, user, max_questions=payload.max_questions, topic_id=payload.topic_id, seed=payload.seed
    )
    if not payload.create_session or not plan.get("question_ids"):
        db.commit()
        return plan
    from ...core.timeutil import today_local

    session = models.TestSession(
        user_id=user.id,
        session_type="review",
        topic_id=plan["anchor_topic_id"],
        intervention_type=plan["intervention_type"],
        planned_question_count=len(plan["question_ids"]),
        planned_date=today_local(),
        status="in_progress",
        task_id=payload.task_id,
        source="review_engine",
    )
    db.add(session)
    db.flush()
    for order, question_id in enumerate(plan["question_ids"]):
        db.add(models.SessionQuestion(session_id=session.id, question_id=question_id, display_order=order, selection_reason="review"))
    sheet = models.ResponseSheet(session_id=session.id, user_id=user.id, status="open", entry_mode="live")
    db.add(sheet)
    db.flush()
    for question_id in plan["question_ids"]:
        db.add(models.ResponseEntry(response_sheet_id=sheet.id, question_id=question_id, state="UNANSWERED", entry_source="live"))
    db.commit()
    return {**plan, "session_id": session.id, "session": sessions.session_payload(db, session.id)}


@router.post("/review/items/{item_id}/resolve")
def resolve_item(item_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = review.resolve_item(db, user, item_id)
    db.commit()
    return result


@router.post("/review/items/{item_id}/snooze")
def snooze_item(item_id: int, days: int = 1, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = review.snooze_item(db, user, item_id, days)
    db.commit()
    return result


@router.get("/questions/{question_id}/history")
def question_history(question_id: int, db: Session = Depends(get_db)) -> dict:
    from ...services import questions

    return questions.question_history(db, question_id)
