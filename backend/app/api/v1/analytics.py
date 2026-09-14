"""Progress + analytics routes (spec 14). Routes only."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db import get_db
from app.schemas.analytics import (
    BookTopicsOut,
    NodeProgressOut,
    OverviewOut,
    QuestionHistoryOut,
    TrendsOut,
    WeaknessesOut,
)
from app.services import analytics as service

router = APIRouter(tags=["analytics"])


@router.get("/progress/overview", response_model=OverviewOut)
def progress_overview(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> OverviewOut:
    return service.overview(db, user_id=user_id)


@router.get("/progress/books/{book_id}", response_model=BookTopicsOut)
def progress_book(
    book_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> BookTopicsOut:
    return service.book_topics(db, user_id=user_id, book_id=book_id)


@router.get("/progress/nodes/{node_id}", response_model=NodeProgressOut)
def progress_node(
    node_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> NodeProgressOut:
    return service.node_progress(db, user_id=user_id, node_id=node_id)


@router.get("/progress/questions/{question_id}", response_model=QuestionHistoryOut)
def progress_question(
    question_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> QuestionHistoryOut:
    return service.question_history(db, user_id=user_id, question_id=question_id)


@router.get("/analytics/trends", response_model=TrendsOut)
def analytics_trends(
    days: int = Query(default=30),
    group_by: str = Query(default="day"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TrendsOut:
    return service.trends(db, user_id=user_id, days=days, group_by=group_by)


@router.get("/analytics/weaknesses", response_model=WeaknessesOut)
def analytics_weaknesses(
    limit: int = Query(default=20),
    min_volume: int = Query(default=3),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> WeaknessesOut:
    return service.weaknesses(db, user_id=user_id, limit=limit, min_volume=min_volume)
