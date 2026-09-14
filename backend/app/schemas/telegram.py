from pydantic import BaseModel
from typing import Optional

class TelegramConnectionCreate(BaseModel):
    telegram_user_id: Optional[str] = None
    telegram_username: Optional[str] = None
    chat_id: Optional[str] = None

class TelegramConnectionOut(BaseModel):
    id: int
    user_id: int
    telegram_user_id: Optional[str] = None
    telegram_username: Optional[str] = None
    chat_id: Optional[str] = None
    is_verified: bool
    morning_report_enabled: bool
    evening_report_enabled: bool
    weekly_goal_report_enabled: bool
    homework_reminder_enabled: bool
    review_reminder_enabled: bool
    exam_reminder_enabled: bool
    morning_report_time: str
    evening_report_time: str
    
    class Config:
        from_attributes = True

class TelegramConnectRequest(BaseModel):
    verification_code: str

class TelegramReportPreview(BaseModel):
    report_type: str
    content: str
    data: dict = {}
