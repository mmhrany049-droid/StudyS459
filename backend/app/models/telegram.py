from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base

class TelegramConnection(Base):
    __tablename__ = "telegram_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    telegram_user_id = Column(String, nullable=True, index=True)
    telegram_username = Column(String, nullable=True)
    chat_id = Column(String, nullable=True)
    
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    
    # Preferences - configurable timing
    morning_report_enabled = Column(Boolean, default=True)
    evening_report_enabled = Column(Boolean, default=True)
    weekly_goal_report_enabled = Column(Boolean, default=True)
    homework_reminder_enabled = Column(Boolean, default=True)
    review_reminder_enabled = Column(Boolean, default=True)
    exam_reminder_enabled = Column(Boolean, default=True)
    
    morning_report_time = Column(String, default="08:00")
    evening_report_time = Column(String, default="20:00")
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="telegram_connection")
