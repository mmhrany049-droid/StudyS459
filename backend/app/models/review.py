from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class ReviewQueue(Base):
    """
    Extensible review system - spaced repetition strategy is configurable
    """
    __tablename__ = "review_queue"
    __table_args__ = (
        Index('ix_review_user_status', 'user_id', 'status'),
        Index('ix_review_user_question', 'user_id', 'question_id'),
        Index('ix_review_next_review', 'next_review_date'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Why in review
    reason = Column(String, nullable=False, default="wrong_answer")  # wrong_answer, unanswered, manual, exam_weakness
    source_attempt_id = Column(Integer, ForeignKey("question_attempts.id", ondelete="SET NULL"), nullable=True)
    
    status = Column(String, default="pending")  # pending, reviewed, mastered, postponed
    priority = Column(Integer, default=0)
    
    # Spaced repetition fields - strategy agnostic
    repetition_count = Column(Integer, default=0)
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)
    next_review_date = Column(String, nullable=True, index=True)  # ISO date
    last_reviewed_at = Column(DateTime, nullable=True)
    
    # Configurable metadata
    extra_data = Column(Text, nullable=True)  # JSON for strategy-specific data
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="review_items")
    question = relationship("Question")
    book = relationship("Book")
    source_attempt = relationship("QuestionAttempt")
