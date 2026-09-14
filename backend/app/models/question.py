from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint('book_id', 'stable_id', name='uq_question_stable'),
        Index('ix_question_book_testset', 'book_id', 'test_set_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    test_set_id = Column(Integer, ForeignKey("test_sets.id", ondelete="CASCADE"), nullable=True, index=True)
    stable_id = Column(String, nullable=False, index=True)
    
    question_text = Column(Text, nullable=True)
    question_text_fa = Column(Text, nullable=True)
    # For image-based questions
    image_url = Column(String, nullable=True)
    
    # Options - store as JSON text for flexibility, but also normalized if needed
    option_a = Column(Text, nullable=True)
    option_b = Column(Text, nullable=True)
    option_c = Column(Text, nullable=True)
    option_d = Column(Text, nullable=True)
    
    correct_option = Column(String, nullable=True)  # A,B,C,D or null if no answer key yet
    explanation = Column(Text, nullable=True)
    
    difficulty_level = Column(Integer, nullable=True)  # 1,2,3
    is_concours = Column(Boolean, default=False)  # for کنکور questions
    concours_year = Column(Integer, nullable=True)  # 1404 etc
    
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    book = relationship("Book", back_populates="questions")
    test_set = relationship("TestSet", back_populates="questions")
    topic_maps = relationship("QuestionTopicMap", back_populates="question", cascade="all, delete-orphan")
    attempts = relationship("QuestionAttempt", back_populates="question", cascade="all, delete-orphan")
    session_questions = relationship("TestSessionQuestion", back_populates="question")

class QuestionTopicMap(Base):
    __tablename__ = "question_topic_map"
    __table_args__ = (
        UniqueConstraint('question_id', 'book_node_id', name='uq_question_node'),
        Index('ix_qtm_node_question', 'book_node_id', 'question_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    book_node_id = Column(Integer, ForeignKey("book_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    question = relationship("Question", back_populates="topic_maps")
    book_node = relationship("BookNode")
