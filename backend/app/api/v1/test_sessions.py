"""Test Engine routes (spec 14). Routes only — logic lives in services."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db import get_db
from app.schemas.tests import (
    AnswersIn,
    AnswersOut,
    CorrectionOut,
    CorrectionsIn,
    SessionCreate,
    SessionView,
)
from app.services import test_engine as engine

router = APIRouter(tags=["tests"])


@router.post("/test-sessions", response_model=SessionView, status_code=201)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> SessionView:
    return engine.create_session(
        db,
        user_id=user_id,
        node_id=payload.node_id,
        count=payload.count,
        sequence_from=payload.sequence_from,
        sequence_to=payload.sequence_to,
        parity=payload.parity,
        timed=payload.timed,
        time_limit_seconds=payload.time_limit_seconds,
        task_id=payload.task_id,
    )


@router.get("/test-sessions/{session_id}", response_model=SessionView)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> SessionView:
    return engine.get_session_view(db, user_id=user_id, session_id=session_id)


@router.post("/test-sessions/{session_id}/answers", response_model=AnswersOut)
def submit_answers(
    session_id: int,
    payload: AnswersIn,
    response: Response,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> AnswersOut:
    response.status_code = 201
    return engine.submit_answers(db, user_id=user_id, session_id=session_id, answers=payload.answers)


@router.post("/test-sessions/{session_id}/finish", response_model=SessionView)
def finish_session(
    session_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> SessionView:
    return engine.finish_session(db, user_id=user_id, session_id=session_id)


@router.post("/test-sessions/{session_id}/corrections", response_model=CorrectionOut)
def submit_corrections(
    session_id: int,
    payload: CorrectionsIn,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> CorrectionOut:
    return engine.submit_corrections(
        db, user_id=user_id, session_id=session_id, corrections=payload.corrections
    )
