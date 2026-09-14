from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class QuestionAttempt(Base):
    """
    Durable historical record - never overwritten.
    Analytics should be rebuildable from this.
    """
    __tablename__ = "question_attempts"
    __table_args__ = (
        Index('ix_attempt_user_question', 'user_id', 'question_id'),
        Index('ix_attempt_user_book', 'user_id', 'book_id'),
        Index('ix_attempt_session', 'test_session_id'),
        Index('ix_attempt_created', 'created_at'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    test_session_id = Column(Integer, ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True, index=True)
    
    user_answer = Column(String, nullable=True)  # A,B,C,D or None for unanswered
    correct_answer = Column(String, nullable=True)  # snapshot of correct at time
    is_correct = Column(Boolean, nullable=True)  # True, False, None (unanswered)
    is_unanswered = Column(Boolean, default=False)
    
    time_spent_seconds = Column(Integer, nullable=True)
    attempt_number = Column(Integer, default=1)  # nth attempt for this question by this user
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    user = relationship("User")
    question = relationship("Question", back_populates="attempts")
    test_session = relationship("TestSession", back_populates="attempts")
    book = relationship("Book")
