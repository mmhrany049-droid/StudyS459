from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class TestSession(Base):
    __tablename__ = "test_sessions"
    __table_args__ = (
        Index('ix_test_session_user_status', 'user_id', 'status'),
        Index('ix_test_session_user_book', 'user_id', 'book_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True, index=True)
    test_set_id = Column(Integer, ForeignKey("test_sets.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    
    title = Column(String, nullable=True)
    test_type = Column(String, nullable=False, default="normal")  # normal, checkup, chapter_exam, etc
    
    status = Column(String, nullable=False, default="in_progress")  # in_progress, finished, pending_correction, cancelled
    mode = Column(String, nullable=False, default="timed")  # timed, untimed -> "بدون زمان"
    
    time_limit_seconds = Column(Integer, nullable=True)  # null for untimed
    elapsed_seconds = Column(Integer, nullable=True)  # actual elapsed, even for untimed for analytics
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    
    total_questions = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    
    # For idempotency and concurrent safety
    finish_token = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="test_sessions")
    book = relationship("Book")
    test_set = relationship("TestSet")
    task = relationship("Task")
    
    session_questions = relationship("TestSessionQuestion", back_populates="test_session", cascade="all, delete-orphan", order_by="TestSessionQuestion.order_index")
    attempts = relationship("QuestionAttempt", back_populates="test_session", cascade="all, delete-orphan")

class TestSessionQuestion(Base):
    __tablename__ = "test_session_questions"
    __table_args__ = (
        UniqueConstraint('test_session_id', 'question_id', name='uq_session_question'),
        UniqueConstraint('test_session_id', 'order_index', name='uq_session_order'),
        Index('ix_tsq_session_question', 'test_session_id', 'question_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    test_session_id = Column(Integer, ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    
    # Snapshot of user answer at time of session
    user_answer = Column(String, nullable=True)  # A,B,C,D or None
    is_correct = Column(Boolean, nullable=True)  # null if not corrected yet or unanswered
    is_answered = Column(Boolean, default=False)
    
    answered_at = Column(DateTime, nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    test_session = relationship("TestSession", back_populates="session_questions")
    question = relationship("Question", back_populates="session_questions")
