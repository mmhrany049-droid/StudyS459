from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...database import get_db
from ...services.student_state_service import get_student_state
from ...services.analytics_service import get_progress_detailed
from ...services.planner_service import get_system_suggestions, get_planner_week
from ...models.task import Task
from ...models.academic import Homework, Exam
from ...models.review import ReviewQueue
from ..deps import get_current_user
from ...models.user import User
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/")
def dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Today's work
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    
    # Find Saturday for week
    days_since_saturday = (today.weekday() - 5) % 7
    saturday = today - timedelta(days=days_since_saturday)
    week_start = saturday.strftime("%Y-%m-%d")
    
    student_state = get_student_state(db, current_user.id)
    progress = get_progress_detailed(db, current_user.id)
    suggestions = get_system_suggestions(db, current_user.id, week_start)
    
    # Today's tasks
    from ...models.task import DailyTaskPlacement
    todays_placements = db.query(DailyTaskPlacement).filter(
        DailyTaskPlacement.user_id == current_user.id,
        DailyTaskPlacement.date == today_str
    ).all()
    
    todays_tasks = []
    for pl in todays_placements:
        task = db.query(Task).filter(Task.id == pl.task_id).first()
        if task:
            todays_tasks.append({
                "placement_id": pl.id,
                "task_id": task.id,
                "title": task.title_fa or task.title,
                "status": task.status,
                "priority": task.priority,
                "estimated_duration": task.estimated_duration_minutes,
                "order_index": pl.order_index
            })
    
    # Weekly progress
    from ...models.goal import WeeklyGoal
    weekly_goal = db.query(WeeklyGoal).filter(
        WeeklyGoal.user_id == current_user.id,
        WeeklyGoal.week_start_date == week_start
    ).first()
    
    # Deadlines
    upcoming_homework = db.query(Homework).filter(
        Homework.user_id == current_user.id,
        Homework.status.in_(["pending", "in_progress"]),
        Homework.due_date != None
    ).order_by(Homework.due_date.asc()).limit(5).all()
    
    upcoming_exams = db.query(Exam).filter(
        Exam.user_id == current_user.id,
        Exam.exam_date >= today_str
    ).order_by(Exam.exam_date.asc()).limit(3).all()
    
    # Recent activity
    from ...models.test_session import TestSession
    recent_sessions = db.query(TestSession).filter(
        TestSession.user_id == current_user.id,
        TestSession.status == "finished"
    ).order_by(TestSession.finished_at.desc()).limit(5).all()
    
    return {
        "today": {
            "date": today_str,
            "tasks": todays_tasks,
            "task_count": len(todays_tasks)
        },
        "weekly_progress": {
            "week_start": week_start,
            "goal": {
                "id": weekly_goal.id if weekly_goal else None,
                "test_count_goal": weekly_goal.test_count_goal if weekly_goal else None,
                "items_count": len(weekly_goal.items) if weekly_goal else 0
            } if weekly_goal else None,
            "progress": progress["overall"]
        },
        "student_state": student_state,
        "suggestions": suggestions["suggestions"][:3],
        "capacity_warnings": suggestions["capacity_warnings"],
        "deadlines": {
            "homework": [{"id": hw.id, "title": hw.title, "due_date": hw.due_date, "priority": hw.priority} for hw in upcoming_homework],
            "exams": [{"id": ex.id, "name": ex.name, "exam_date": ex.exam_date} for ex in upcoming_exams]
        },
        "recent_activity": [
            {
                "id": s.id,
                "title": s.title or f"Test {s.id}",
                "test_type": s.test_type,
                "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                "correct": s.correct_count,
                "wrong": s.wrong_count,
                "total": s.total_questions
            } for s in recent_sessions
        ],
        "weakest_topics": progress["weakest_topics"][:3]
    }
