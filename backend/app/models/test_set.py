from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class TestSet(Base):
    __tablename__ = "test_sets"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    stable_id = Column(String, nullable=False, index=True)
    node_id = Column(Integer, ForeignKey("book_nodes.id", ondelete="SET NULL"), nullable=True, index=True)  # optional association to node
    
    title = Column(String, nullable=False)
    title_fa = Column(String, nullable=True)
    test_type = Column(String, nullable=False, index=True)  # normal, checkup, chapter_exam, comprehensive, concours, mock, custom
    difficulty_level = Column(Integer, nullable=True)  # 1,2,3 for calculus etc
    order_index = Column(Integer, default=0)
    
    is_comprehensive = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    book = relationship("Book", back_populates="test_sets")
    node = relationship("BookNode")
    questions = relationship("Question", back_populates="test_set", cascade="all, delete-orphan")
