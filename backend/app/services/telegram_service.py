from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Dict, Optional
import secrets
from datetime import datetime, timezone
from ..models.telegram import TelegramConnection
from ..models.user import User
from ..services.student_state_service import get_student_state
from ..services.analytics_service import get_progress_detailed
from ..planning.recommendation_engine import generate_system_suggestions
from ..config.settings import settings
from ..integrations.telegram_client import TelegramClient

def get_telegram_connection(db: Session, user_id: int) -> Optional[TelegramConnection]:
    return db.query(TelegramConnection).filter(TelegramConnection.user_id == user_id).first()

def create_or_update_connection(db: Session, user_id: int, telegram_user_id: Optional[str] = None, telegram_username: Optional[str] = None, chat_id: Optional[str] = None):
    conn = get_telegram_connection(db, user_id)
    if conn:
        if telegram_user_id:
            conn.telegram_user_id = telegram_user_id
        if telegram_username:
            conn.telegram_username = telegram_username
        if chat_id:
            conn.chat_id = chat_id
        conn.updated_at = datetime.now(timezone.utc)
    else:
        conn = TelegramConnection(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            chat_id=chat_id,
            is_verified=False,
            verification_code=secrets.token_hex(4)
        )
        db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn

def verify_connection(db: Session, user_id: int, verification_code: str):
    conn = get_telegram_connection(db, user_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Telegram connection not found")
    if conn.verification_code != verification_code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    conn.is_verified = True
    db.commit()
    db.refresh(conn)
    return conn

def update_preferences(db: Session, user_id: int, prefs: dict):
    conn = get_telegram_connection(db, user_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Telegram connection not found")
    for key, value in prefs.items():
        if hasattr(conn, key):
            setattr(conn, key, value)
    db.commit()
    db.refresh(conn)
    return conn

def generate_morning_report(db: Session, user_id: int) -> Dict:
    """
    Telegram must consume core application services, NOT duplicate business logic
    """
    state = get_student_state(db, user_id)
    suggestions = generate_system_suggestions(db, user_id)
    
    # Build report content
    lines = []
    lines.append("🌅 گزارش صبح - برنامه امروز")
    lines.append("")
    lines.append(f"📊 تسلط کلی: {state['analytics_summary']['overall_mastery']:.0f}%")
    lines.append(f"🎯 کارهای ناتمام: {state['counts']['unfinished_tasks']}")
    lines.append(f"📚 تکالیف: {state['counts']['homework_pending']}")
    lines.append(f"🔁 مرورهای امروز: {state['counts']['review_due']}")
    lines.append("")
    if suggestions["suggestions"]:
        lines.append("💡 پیشنهادهای سیستم:")
        for sug in suggestions["suggestions"][:3]:
            task = sug["task"]
            reasons_fa = " + ".join([r["description_fa"] for r in sug["reasons"]])
            lines.append(f"  - {task.title_fa or task.title}: {reasons_fa}")
    lines.append("")
    lines.append("موفق باشی! 💪")
    
    content = "\n".join(lines)
    return {
        "report_type": "morning_daily_plan",
        "content": content,
        "data": state
    }

def generate_evening_report(db: Session, user_id: int) -> Dict:
    from ..models.test_session import TestSession
    from ..models.attempt import QuestionAttempt
    from datetime import timedelta
    
    today = datetime.now(timezone.utc)
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    
    sessions_today = db.query(TestSession).filter(
        TestSession.user_id == user_id,
        TestSession.started_at >= today_start,
        TestSession.status == "finished"
    ).all()
    
    attempts_today = db.query(QuestionAttempt).filter(
        QuestionAttempt.user_id == user_id,
        QuestionAttempt.created_at >= today_start
    ).all()
    
    correct = sum(1 for a in attempts_today if a.is_correct)
    wrong = sum(1 for a in attempts_today if a.is_correct is False)
    
    lines = []
    lines.append("🌙 گزارش شب - عملکرد امروز")
    lines.append("")
    lines.append(f"📝 تست‌های امروز: {len(sessions_today)}")
    lines.append(f"❓ سوالات: {len(attempts_today)}")
    lines.append(f"✅ درست: {correct} | ❌ غلط: {wrong}")
    if correct + wrong > 0:
        acc = correct / (correct + wrong) * 100
        lines.append(f"📈 دقت امروز: {acc:.0f}%")
    lines.append("")
    lines.append("فردا می‌بینمت! 🌟")
    
    content = "\n".join(lines)
    return {
        "report_type": "evening_report",
        "content": content,
        "data": {
            "sessions_today": len(sessions_today),
            "questions_today": len(attempts_today),
            "correct": correct,
            "wrong": wrong
        }
    }

def generate_weekly_goal_report(db: Session, user_id: int) -> Dict:
    from ..models.goal import WeeklyGoal
    from datetime import timedelta
    
    today = datetime.now(timezone.utc)
    days_since_saturday = (today.weekday() - 5) % 7
    saturday = today - timedelta(days=days_since_saturday)
    week_start = saturday.strftime("%Y-%m-%d")
    
    goal = db.query(WeeklyGoal).filter(
        WeeklyGoal.user_id == user_id,
        WeeklyGoal.week_start_date == week_start
    ).first()
    
    if not goal:
        content = "📅 هدف هفتگی برای این هفته ثبت نشده است."
        return {"report_type": "weekly_goal_status", "content": content, "data": {}}
    
    lines = []
    lines.append("🎯 وضعیت اهداف هفتگی")
    lines.append("")
    if goal.test_count_goal:
        from ..models.test_session import TestSession
        week_start_dt = saturday
        week_end_dt = saturday + timedelta(days=6)
        completed = db.query(TestSession).filter(
            TestSession.user_id == user_id,
            TestSession.started_at >= week_start_dt,
            TestSession.started_at <= week_end_dt,
            TestSession.status == "finished"
        ).count()
        lines.append(f"📊 تعداد تست: {completed}/{goal.test_count_goal} ({completed/goal.test_count_goal*100:.0f}%)")
    
    for item in goal.items:
        from ..models.book import Book
        from ..models.book_node import BookNode
        book = db.query(Book).filter(Book.id == item.book_id).first()
        node = db.query(BookNode).filter(BookNode.id == item.book_node_id).first() if item.book_node_id else None
        title = node.title_fa if node and node.title_fa else node.title if node else book.title_fa if book and book.title_fa else "مبحث"
        lines.append(f"  - {title}: {item.completed_tests}/{item.target_tests}")
    
    content = "\n".join(lines)
    return {
        "report_type": "weekly_goal_status",
        "content": content,
        "data": {"goal_id": goal.id}
    }

def send_telegram_message(db: Session, user_id: int, message: str) -> bool:
    conn = get_telegram_connection(db, user_id)
    if not conn or not conn.is_verified or not conn.chat_id:
        raise HTTPException(status_code=400, detail="Telegram not connected or not verified")
    
    if not settings.telegram_bot_token:
        # If no token configured, simulate success but log
        print(f"[TELEGRAM SIMULATED] To {conn.chat_id}: {message}")
        return True
    
    client = TelegramClient(token=settings.telegram_bot_token)
    try:
        client.send_message(chat_id=conn.chat_id, text=message)
        return True
    except Exception as e:
        print(f"Telegram send failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send Telegram message: {str(e)}")

def preview_report(db: Session, user_id: int, report_type: str) -> Dict:
    if report_type == "morning":
        return generate_morning_report(db, user_id)
    elif report_type == "evening":
        return generate_evening_report(db, user_id)
    elif report_type == "weekly":
        return generate_weekly_goal_report(db, user_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid report type")
