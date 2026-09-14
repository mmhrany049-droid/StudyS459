from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...database import get_db
from ...schemas.telegram import TelegramConnectionCreate, TelegramConnectionOut, TelegramConnectRequest, TelegramReportPreview
from ...services import telegram_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/telegram", tags=["Telegram"])

@router.get("/connection", response_model=TelegramConnectionOut)
def get_connection(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conn = telegram_service.get_telegram_connection(db, current_user.id)
    if not conn:
        # Create empty connection with verification code
        conn = telegram_service.create_or_update_connection(db, current_user.id)
    return conn

@router.post("/connection", response_model=TelegramConnectionOut)
def create_connection(data: TelegramConnectionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conn = telegram_service.create_or_update_connection(
        db, current_user.id,
        telegram_user_id=data.telegram_user_id,
        telegram_username=data.telegram_username,
        chat_id=data.chat_id
    )
    return conn

@router.post("/verify", response_model=TelegramConnectionOut)
def verify(data: TelegramConnectRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return telegram_service.verify_connection(db, current_user.id, data.verification_code)

@router.patch("/preferences", response_model=TelegramConnectionOut)
def update_prefs(prefs: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return telegram_service.update_preferences(db, current_user.id, prefs)

@router.get("/preview/{report_type}", response_model=TelegramReportPreview)
def preview_report(report_type: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return telegram_service.preview_report(db, current_user.id, report_type)

@router.post("/send/{report_type}")
def send_report(report_type: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = telegram_service.preview_report(db, current_user.id, report_type)
    success = telegram_service.send_telegram_message(db, current_user.id, report["content"])
    return {"status": "sent" if success else "failed", "report": report}
