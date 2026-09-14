from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # relationships
    book_activations = relationship("UserBookActivation", back_populates="user", cascade="all, delete-orphan")
    test_sessions = relationship("TestSession", back_populates="user", cascade="all, delete-orphan")
    weekly_goals = relationship("WeeklyGoal", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")
    class_sessions = relationship("ClassSession", back_populates="user", cascade="all, delete-orphan")
    taught_lessons = relationship("TaughtLesson", back_populates="user", cascade="all, delete-orphan")
    homework_items = relationship("Homework", back_populates="user", cascade="all, delete-orphan")
    exams = relationship("Exam", back_populates="user", cascade="all, delete-orphan")
    review_items = relationship("ReviewQueue", back_populates="user", cascade="all, delete-orphan")
    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
    sharing_permissions = relationship("SharingPermission", back_populates="user", cascade="all, delete-orphan")
    telegram_connection = relationship("TelegramConnection", back_populates="user", uselist=False, cascade="all, delete-orphan")
