"""مسیرهای تست/مرور/وارد کردن — V1 + V2."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_user
from app.db import get_db
from app.domain import review as review_mod
from app.jalali import today_tehran
from app.models import TestSession, User
from app.services import sessions as sess

router = APIRouter()


class CreateSessionBody(BaseModel):
    test_set_id: int
    count: int = 10
    parity: str = "any"
    timed: bool = False
    time_limit_seconds: int | None = None
    sequence_from: int | None = None
    sequence_to: int | None = None
    task_id: int | None = None


class AnswerBody(BaseModel):
    question_id: int
    result: str  # correct | wrong | unanswered
    answer: str | None = None


class DurationBody(BaseModel):
    actual_duration_minutes: int


class ImportAnswerItem(BaseModel):
    question_id: int
    result: str
    answer: str | None = None


class ImportBody(BaseModel):
    test_set_id: int
    answers: list[ImportAnswerItem]
    date: str | None = None


@router.post("/test-sessions")
def create_test_session(body: CreateSessionBody, db: Session = Depends(get_db),
                        user: User = Depends(get_user)):
    ts = sess.create_session(db, user, body.model_dump())
    return sess.session_view(db, user, ts.id)


@router.get("/test-sessions")
def list_sessions(imported: bool | None = Query(None),
                  db: Session = Depends(get_db), user: User = Depends(get_user)):
    stmt = select(TestSession).where(TestSession.user_id == user.id)
    if imported is not None:
        stmt = stmt.where(TestSession.is_imported == imported)
    out = []
    for ts in db.scalars(stmt.order_by(TestSession.started_at.desc()).limit(50)):
        out.append({
            "id": ts.id, "session_type": ts.session_type, "status": ts.status,
            "timed": ts.timed, "parity": ts.parity, "is_imported": ts.is_imported,
            "actual_duration_minutes": ts.actual_duration_minutes,
            "started_at": ts.started_at.isoformat(),
            "ended_at": ts.ended_at.isoformat() if ts.ended_at else None,
            "session_date": ts.session_date.isoformat() if ts.session_date else None,
        })
    return out


@router.get("/test-sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_user)):
    return sess.session_view(db, user, session_id)


@router.get("/test-sessions/{session_id}/result")
def get_result(session_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_user)):
    ts = db.get(TestSession, session_id)
    if ts is None or ts.user_id != user.id:
        raise HTTPException(404, "جلسه پیدا نشد.")
    return sess._result_view(db, ts)


@router.post("/test-sessions/{session_id}/answers")
def submit_answer(session_id: int, body: AnswerBody, db: Session = Depends(get_db),
                  user: User = Depends(get_user)):
    return sess.answer_question(db, user, session_id, body.model_dump())


@router.post("/test-sessions/{session_id}/finish")
def finish(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    return sess.finish_session(db, user, session_id)


@router.patch("/test-sessions/{session_id}/duration")
def set_duration(session_id: int, body: DurationBody, db: Session = Depends(get_db),
                 user: User = Depends(get_user)):
    return sess.set_duration(db, user, session_id, body.actual_duration_minutes)


@router.post("/test-sessions/import")
def import_past(body: ImportBody, db: Session = Depends(get_db),
                user: User = Depends(get_user)):
    data = body.model_dump()
    data["answers"] = [a.model_dump() for a in body.answers]
    return sess.import_session(db, user, data)


# ------------------------------- Review --------------------------------------

@router.get("/review/summary")
def review_summary(db: Session = Depends(get_db), user: User = Depends(get_user)):
    from app.models import ReviewQueueItem
    from sqlalchemy import func
    today = today_tehran()
    pending = db.scalar(select(func.count(ReviewQueueItem.id)).where(
        ReviewQueueItem.user_id == user.id, ReviewQueueItem.status == "pending")) or 0
    due = db.scalar(select(func.count(ReviewQueueItem.id)).where(
        ReviewQueueItem.user_id == user.id, ReviewQueueItem.status == "pending",
        ReviewQueueItem.scheduled_for <= today)) or 0
    critical = db.scalar(select(func.count(ReviewQueueItem.id)).where(
        ReviewQueueItem.user_id == user.id, ReviewQueueItem.status == "pending",
        ReviewQueueItem.wrong_count >= 2)) or 0
    return {"pending": pending, "due": due, "critical": critical}


@router.post("/review-sessions")
def create_review(count: int | None = None, db: Session = Depends(get_db),
                  user: User = Depends(get_user)):
    return sess.create_review_session(db, user, count)


@router.post("/review-sessions/{session_id}/answers")
def review_answer(session_id: int, body: AnswerBody, db: Session = Depends(get_db),
                  user: User = Depends(get_user)):
    return sess.review_answer(db, user, session_id, body.model_dump())


@router.post("/review-sessions/{session_id}/finish")
def finish_review(session_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_user)):
    return sess.finish_review(db, user, session_id)
