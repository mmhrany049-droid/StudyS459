"""Question <-> Node mapping: one question may map to MANY topics (spec 05)."""

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class QuestionTopicMap(Base):
    __tablename__ = "question_topic_map"
    __table_args__ = (Index("ix_question_topic_map_node", "node_id"),)

    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("book_nodes.id"), primary_key=True)
