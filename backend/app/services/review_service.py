from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from ..models.review import ReviewQueue
from ..models.question import Question
from ..config.settings import settings
import json

def get_review_queue(db: Session, user_id: int, status: str = "pending", limit: int = 50):
    q = db.query(ReviewQueue).filter(ReviewQueue.user_id == user_id)
    if status:
        q = q.filter(ReviewQueue.status == status)
    q = q.order_by(ReviewQueue.priority.desc(), ReviewQueue.next_review_date.asc())
    return q.limit(limit).all()

def add_to_review_queue(db: Session, user_id: int, question_id: int, book_id: Optional[int] = None, reason: str = "wrong_answer", source_attempt_id: Optional[int] = None):
    # Check if already in queue pending
    existing = db.query(ReviewQueue).filter(
        ReviewQueue.user_id == user_id,
        ReviewQueue.question_id == question_id,
        ReviewQueue.status == "pending"
    ).first()
    if existing:
        # Update priority or reason
        existing.priority += 1
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        return existing
    
    # Determine next review date based on configurable strategy
    intervals = settings.get_review_intervals()
    next_review = datetime.now(timezone.utc) + timedelta(days=intervals[0] if intervals else 1)
    
    review_item = ReviewQueue(
        user_id=user_id,
        question_id=question_id,
        book_id=book_id,
        reason=reason,
        source_attempt_id=source_attempt_id,
        status="pending",
        priority=1,
        repetition_count=0,
        ease_factor=2.5,
        interval_days=intervals[0] if intervals else 1,
        next_review_date=next_review.strftime("%Y-%m-%d")
    )
    db.add(review_item)
    db.commit()
    db.refresh(review_item)
    return review_item

def update_review_item(db: Session, user_id: int, review_id: int, status: str, ease_factor: Optional[float] = None):
    item = db.query(ReviewQueue).filter(ReviewQueue.id == review_id, ReviewQueue.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    
    item.status = status
    item.last_reviewed_at = datetime.now(timezone.utc)
    
    if status == "reviewed":
        # Simple spaced repetition - configurable
        strategy = settings.spaced_repetition_strategy
        intervals = settings.get_review_intervals()
        
        if strategy == "simple":
            item.repetition_count += 1
            if item.repetition_count < len(intervals):
                item.interval_days = intervals[item.repetition_count]
            else:
                item.interval_days = intervals[-1] * 2  # extend
            next_date = datetime.now(timezone.utc) + timedelta(days=item.interval_days)
            item.next_review_date = next_date.strftime("%Y-%m-%d")
            # If repeated enough, mark as mastered
            if item.repetition_count >= 3:
                item.status = "mastered"
        elif strategy == "sm2":
            # Simplified SM2
            if ease_factor is not None:
                item.ease_factor = ease_factor
            # Update interval
            if item.repetition_count == 0:
                item.interval_days = 1
            elif item.repetition_count == 1:
                item.interval_days = 6
            else:
                item.interval_days = int(item.interval_days * item.ease_factor)
            item.repetition_count += 1
            next_date = datetime.now(timezone.utc) + timedelta(days=item.interval_days)
            item.next_review_date = next_date.strftime("%Y-%m-%d")
        else:
            # configurable fallback
            item.repetition_count += 1
            item.interval_days = intervals[0] if intervals else 1
            next_date = datetime.now(timezone.utc) + timedelta(days=item.interval_days)
            item.next_review_date = next_date.strftime("%Y-%m-%d")
    
    db.commit()
    db.refresh(item)
    return item

def get_due_reviews(db: Session, user_id: int):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return db.query(ReviewQueue).filter(
        ReviewQueue.user_id == user_id,
        ReviewQueue.status == "pending",
        ReviewQueue.next_review_date <= today
    ).all()
