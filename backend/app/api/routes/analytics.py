from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from ...database import get_db
from ...services import analytics_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/overview")
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return analytics_service.get_overall_analytics(db, current_user.id)

@router.get("/progress")
def progress_detailed(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return analytics_service.get_progress_detailed(db, current_user.id)

@router.get("/books/{book_id}")
def book_analytics(book_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return analytics_service.get_book_analytics(db, current_user.id, book_id)

@router.get("/weakest")
def weakest_topics(limit: int = Query(10, le=50), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return analytics_service.get_weakest_topics(db, current_user.id, limit=limit)

@router.get("/recent-mistakes")
def recent_mistakes(limit: int = Query(20, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return analytics_service.get_recent_mistakes(db, current_user.id, limit=limit)

@router.get("/questions/{question_id}/history")
def question_history(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return analytics_service.get_question_history(db, current_user.id, question_id)
