from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        Index('ix_schedule_user_day', 'user_id', 'day_of_week'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String, nullable=False)
    schedule_type = Column(String, nullable=False, default="school")  # school, external_class, busy, study_block
    
    day_of_week = Column(String, nullable=False, index=True)  # saturday, sunday, monday, tuesday, wednesday, thursday, friday
    
    start_time = Column(String, nullable=False)  # HH:MM
    end_time = Column(String, nullable=False)  # HH:MM
    
    is_recurring = Column(Boolean, default=True)
    specific_date = Column(String, nullable=True)  # for non-recurring
    
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True)
    
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="schedules")
    subject = relationship("Subject")
    book = relationship("Book")

class ClassSession(Base):
    __tablename__ = "class_sessions"
    __table_args__ = (
        Index('ix_class_session_user_date', 'user_id', 'date'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True, index=True)
    
    date = Column(String, nullable=False, index=True)  # ISO date
    title = Column(String, nullable=True)
    
    attended = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="class_sessions")
    schedule = relationship("Schedule")
    taught_lessons = relationship("TaughtLesson", back_populates="class_session", cascade="all, delete-orphan")
