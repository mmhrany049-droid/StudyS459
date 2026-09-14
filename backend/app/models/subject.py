from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class Subject(Base):
    __tablename__ = "subjects"
    
    id = Column(Integer, primary_key=True, index=True)
    stable_id = Column(String, unique=True, index=True, nullable=False)  # e.g., "chem", "calc", "physics"
    name = Column(String, nullable=False)
    name_fa = Column(String, nullable=True)
    color = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    books = relationship("Book", back_populates="subject")
