from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index('ix_task_user_status', 'user_id', 'status'),
        Index('ix_task_user_week', 'user_id', 'weekly_goal_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String, nullable=False)
    title_fa = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    # Source of task
    source = Column(String, nullable=False, default="manual")  # weekly_goal, homework, review, exam, manual, system
    source_id = Column(Integer, nullable=True)  # id of source entity (goal item, homework, etc)
    
    # What it refers to
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True, index=True)
    book_node_id = Column(Integer, ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    test_set_id = Column(Integer, ForeignKey("test_sets.id", ondelete="SET NULL"), nullable=True, index=True)
    
    weekly_goal_id = Column(Integer, ForeignKey("weekly_goals.id", ondelete="SET NULL"), nullable=True, index=True)
    
    task_type = Column(String, nullable=False, default="test")  # test, review, homework, reading, exam_prep
    
    status = Column(String, default="pending")  # pending, in_progress, completed, cancelled, overdue
    priority = Column(Integer, default=0)  # higher = higher priority, vertical stacking
    estimated_duration_minutes = Column(Integer, default=30)
    
    # Recommendation reason (structured)
    reason = Column(Text, nullable=True)  # human readable
    reason_structured = Column(Text, nullable=True)  # JSON string of reasons
    
    # Dates
    due_date = Column(String, nullable=True)  # ISO date
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="tasks")
    book = relationship("Book")
    book_node = relationship("BookNode")
    test_set = relationship("TestSet")
    weekly_goal = relationship("WeeklyGoal")
    
    placements = relationship("DailyTaskPlacement", back_populates="task", cascade="all, delete-orphan")

class DailyTaskPlacement(Base):
    __tablename__ = "daily_task_placements"
    __table_args__ = (
        Index('ix_placement_user_date', 'user_id', 'date'),
        Index('ix_placement_task', 'task_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    
    date = Column(String, nullable=False, index=True)  # ISO date YYYY-MM-DD
    day_of_week = Column(String, nullable=True)  # saturday, sunday, etc
    
    order_index = Column(Integer, default=0)  # vertical position - higher priority = lower index? Let's define 0 top
    is_catchup = Column(Boolean, default=False)  # if this is catch-up placement
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User")
    task = relationship("Task", back_populates="placements")
