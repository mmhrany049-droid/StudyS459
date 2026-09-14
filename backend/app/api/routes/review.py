from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...services import review_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/review", tags=["Review"])

@router.get("/")
def get_queue(status: str = Query("pending"), limit: int = Query(50, le=200), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = review_service.get_review_queue(db, current_user.id, status=status, limit=limit)
    return [
        {
            "id": item.id,
            "user_id": item.user_id,
            "question_id": item.question_id,
            "book_id": item.book_id,
            "reason": item.reason,
            "status": item.status,
            "priority": item.priority,
            "repetition_count": item.repetition_count,
            "ease_factor": item.ease_factor,
            "interval_days": item.interval_days,
            "next_review_date": item.next_review_date,
            "last_reviewed_at": item.last_reviewed_at.isoformat() if item.last_reviewed_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "question_text": item.question.question_text_fa or item.question.question_text if item.question else None,
            "stable_id": item.question.stable_id if item.question else None
        } for item in items
    ]

@router.get("/due")
def get_due(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = review_service.get_due_reviews(db, current_user.id)
    return [{"id": i.id, "question_id": i.question_id, "book_id": i.book_id, "reason": i.reason, "next_review_date": i.next_review_date} for i in items]

@router.post("/{review_id}/update")
def update_review(review_id: int, status: str, ease_factor: Optional[float] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = review_service.update_review_item(db, current_user.id, review_id, status=status, ease_factor=ease_factor)
    return {"id": item.id, "status": item.status, "repetition_count": item.repetition_count, "next_review_date": item.next_review_date}

@router.post("/add")
def add_to_queue(question_id: int, book_id: Optional[int] = None, reason: str = "manual", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = review_service.add_to_review_queue(db, user_id=current_user.id, question_id=question_id, book_id=book_id, reason=reason)
    return {"id": item.id, "question_id": item.question_id, "status": item.status}
