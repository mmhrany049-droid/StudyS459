from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class BookNode(Base):
    __tablename__ = "book_nodes"
    __table_args__ = (
        UniqueConstraint('book_id', 'stable_id', name='uq_book_node_stable'),
        Index('ix_book_node_book_parent', 'book_id', 'parent_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    stable_id = Column(String, nullable=False, index=True)  # stable identifier
    parent_id = Column(Integer, ForeignKey("book_nodes.id", ondelete="CASCADE"), nullable=True, index=True)
    
    node_type = Column(String, nullable=False)  # e.g., فصل, عنوان, درس, بخش, زیرعنوان, etc - flexible
    title = Column(String, nullable=False)
    title_fa = Column(String, nullable=True)
    order_index = Column(Integer, default=0)
    level = Column(Integer, default=0)  # depth level for quick queries
    
    # For extensibility - extra metadata as JSON text if needed
    extra_data = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    book = relationship("Book", back_populates="nodes")
    parent = relationship("BookNode", remote_side=[id], backref="children")
    
    # Relationships for mapping questions to topics (many-to-many via question_topic_map)
    # Note: question_topic_map defined in question model file
