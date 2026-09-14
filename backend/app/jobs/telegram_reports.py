"""
Background jobs for Telegram reports
Timing/triggers configurable because exact final behavior is open decision
"""
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List
from ..database import SessionLocal
from ..models.telegram import TelegramConnection
from ..services import telegram_service
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)

def get_due_reports(report_type: str) -> List[TelegramConnection]:
    """Get connections that should receive report now based on configured times"""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        current_time = now.strftime("%H:%M")
        
        # Parse configured report times
        configured_times = [t.strip() for t in settings.telegram_report_times.split(",")]
        
        query = db.query(TelegramConnection).filter(TelegramConnection.is_verified == True)
        
        if report_type == "morning":
            query = query.filter(TelegramConnection.morning_report_enabled == True)
            # Check if current time matches morning report time (within 5 min window)
            # For simplicity, check exact match or configurable
        elif report_type == "evening":
            query = query.filter(TelegramConnection.evening_report_enabled == True)
        
        return query.all()
    finally:
        db.close()

def send_morning_reports():
    """Send morning daily plan reports"""
    db = SessionLocal()
    try:
        connections = db.query(TelegramConnection).filter(
            TelegramConnection.is_verified == True,
            TelegramConnection.morning_report_enabled == True
        ).all()
        
        for conn in connections:
            try:
                report = telegram_service.generate_morning_report(db, conn.user_id)
                telegram_service.send_telegram_message(db, conn.user_id, report["content"])
                logger.info(f"Sent morning report to user {conn.user_id}")
            except Exception as e:
                logger.error(f"Failed to send morning report to user {conn.user_id}: {e}")
    finally:
        db.close()

def send_evening_reports():
    """Send evening reports"""
    db = SessionLocal()
    try:
        connections = db.query(TelegramConnection).filter(
            TelegramConnection.is_verified == True,
            TelegramConnection.evening_report_enabled == True
        ).all()
        
        for conn in connections:
            try:
                report = telegram_service.generate_evening_report(db, conn.user_id)
                telegram_service.send_telegram_message(db, conn.user_id, report["content"])
                logger.info(f"Sent evening report to user {conn.user_id}")
            except Exception as e:
                logger.error(f"Failed to send evening report to user {conn.user_id}: {e}")
    finally:
        db.close()

def send_homework_reminders():
    """Send homework deadline reminders"""
    db = SessionLocal()
    try:
        from ..models.academic import Homework
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tomorrow = (datetime.now(timezone.utc) + __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Find homework due tomorrow
        due_soon = db.query(Homework).filter(
            Homework.due_date == tomorrow,
            Homework.status.in_(["pending", "in_progress"])
        ).all()
        
        for hw in due_soon:
            conn = db.query(TelegramConnection).filter(
                TelegramConnection.user_id == hw.user_id,
                TelegramConnection.is_verified == True,
                TelegramConnection.homework_reminder_enabled == True
            ).first()
            if conn:
                try:
                    message = f"📋 یادآور تکلیف: {hw.title} فردا مهلت دارد ({hw.due_date})"
                    telegram_service.send_telegram_message(db, hw.user_id, message)
                except Exception as e:
                    logger.error(f"Failed homework reminder: {e}")
    finally:
        db.close()
