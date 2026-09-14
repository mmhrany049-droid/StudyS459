from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class Book(Base):
    __tablename__ = "books"
    
    id = Column(Integer, primary_key=True, index=True)
    stable_id = Column(String, unique=True, index=True, nullable=False)  # stable across imports
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    title_fa = Column(String, nullable=True)
    publisher = Column(String, nullable=True)
    edition = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    hierarchy_config = Column(JSON, nullable=True)  # e.g., {"levels": ["فصل", "عنوان", "زیرعنوان"]}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    subject = relationship("Subject", back_populates="books")
    nodes = relationship("BookNode", back_populates="book", cascade="all, delete-orphan")
    test_sets = relationship("TestSet", back_populates="book", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="book", cascade="all, delete-orphan")
    activations = relationship("UserBookActivation", back_populates="book", cascade="all, delete-orphan")

class UserBookActivation(Base):
    __tablename__ = "user_book_activations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    activated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="book_activations")
    book = relationship("Book", back_populates="activations")
    
    __table_args__ = (
        # unique constraint
        {"sqlite_autoincrement": True},
    )
