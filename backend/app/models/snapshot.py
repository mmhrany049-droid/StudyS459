from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, Index, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class PerformanceSnapshot(Base):
    """
    Snapshots for trends, but raw attempts remain source of truth
    """
    __tablename__ = "performance_snapshots"
    __table_args__ = (
        Index('ix_snapshot_user_date', 'user_id', 'snapshot_date'),
        Index('ix_snapshot_user_book', 'user_id', 'book_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True, index=True)
    book_node_id = Column(Integer, ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True)
    
    snapshot_date = Column(String, nullable=False, index=True)  # ISO date
    snapshot_type = Column(String, nullable=False, default="daily")  # daily, weekly
    
    total_tests = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    wrong = Column(Integer, default=0)
    unanswered = Column(Integer, default=0)
    
    accuracy = Column(Float, nullable=True)
    coverage = Column(Float, nullable=True)
    mastery = Column(Float, nullable=True)
    volume = Column(Integer, default=0)
    
    extra_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User")
    book = relationship("Book")
    book_node = relationship("BookNode")
