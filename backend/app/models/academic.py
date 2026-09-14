from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class TaughtLesson(Base):
    """
    Critical: TAUGHT != LEARNED
    This records that teacher taught something, not that student learned it.
    """
    __tablename__ = "taught_lessons"
    __table_args__ = (
        Index('ix_taught_lesson_user_book', 'user_id', 'book_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_session_id = Column(Integer, ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True, index=True)
    book_node_id = Column(Integer, ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    
    title = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    
    taught_date = Column(String, nullable=False, index=True)  # ISO date
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="taught_lessons")
    class_session = relationship("ClassSession", back_populates="taught_lessons")
    book = relationship("Book")
    book_node = relationship("BookNode")

class Homework(Base):
    __tablename__ = "homework"
    __table_args__ = (
        Index('ix_homework_user_due', 'user_id', 'due_date'),
        Index('ix_homework_user_status', 'user_id', 'status'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    source = Column(String, nullable=False, default="manual")  # school, external_class, manual
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True, index=True)
    book_node_id = Column(Integer, ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    
    due_date = Column(String, nullable=True, index=True)  # ISO date
    estimated_time_minutes = Column(Integer, default=30)
    priority = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, in_progress, completed, overdue
    
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)  # linked planner task
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="homework_items")
    subject = relationship("Subject")
    book = relationship("Book")
    book_node = relationship("BookNode")
    task = relationship("Task")

class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        Index('ix_exam_user_date', 'user_id', 'exam_date'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String, nullable=False)
    exam_type = Column(String, nullable=False, default="school")  # school, external, mock, diagnostic
    provider = Column(String, nullable=True)  # institute name
    exam_date = Column(String, nullable=False, index=True)  # ISO date
    
    total_questions = Column(Integer, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    
    # Overall results
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    percentage = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="exams")
    questions = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan")
    subject_results = relationship("ExamSubjectResult", back_populates="exam", cascade="all, delete-orphan")

class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    __table_args__ = (
        Index('ix_exam_question_exam', 'exam_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    
    question_number = Column(Integer, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True)
    book_node_id = Column(Integer, ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True)  # topic mapping where possible
    
    question_image_url = Column(String, nullable=True)
    correct_answer = Column(String, nullable=True)
    user_answer = Column(String, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    is_unanswered = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    exam = relationship("Exam", back_populates="questions")
    subject = relationship("Subject")
    book = relationship("Book")
    book_node = relationship("BookNode")

class ExamSubjectResult(Base):
    __tablename__ = "exam_subject_results"
    
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    
    correct = Column(Integer, default=0)
    wrong = Column(Integer, default=0)
    unanswered = Column(Integer, default=0)
    percentage = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    
    exam = relationship("Exam", back_populates="subject_results")
    subject = relationship("Subject")
