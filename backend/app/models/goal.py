from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class WeeklyGoal(Base):
    __tablename__ = "weekly_goals"
    __table_args__ = (
        Index('ix_weekly_goal_user_week', 'user_id', 'week_start_date'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    week_start_date = Column(String, nullable=False)  # ISO date Saturday start
    week_end_date = Column(String, nullable=False)
    
    # Two independent goal types
    test_count_goal = Column(Integer, nullable=True)  # number of tests
    topic_goal_enabled = Column(Boolean, default=False)
    
    status = Column(String, default="active")  # active, completed, archived
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="weekly_goals")
    items = relationship("WeeklyGoalItem", back_populates="weekly_goal", cascade="all, delete-orphan")

class WeeklyGoalItem(Base):
    __tablename__ = "weekly_goal_items"
    __table_args__ = (
        Index('ix_goal_item_goal_node', 'weekly_goal_id', 'book_node_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    weekly_goal_id = Column(Integer, ForeignKey("weekly_goals.id", ondelete="CASCADE"), nullable=False, index=True)
    
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    book_node_id = Column(Integer, ForeignKey("book_nodes.id", ondelete="CASCADE"), nullable=True, index=True)  # topic
    
    target_tests = Column(Integer, nullable=True, default=1)
    completed_tests = Column(Integer, default=0)
    
    priority = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    weekly_goal = relationship("WeeklyGoal", back_populates="items")
    book = relationship("Book")
    book_node = relationship("BookNode")
