from sqlalchemy.orm import Session
from typing import Dict, List
from datetime import datetime, timezone
from ..services.analytics_service import get_progress_detailed, get_weakest_topics
from ..models.task import Task
from ..models.goal import WeeklyGoal
from ..models.academic import Homework, Exam
from ..models.review import ReviewQueue
from ..models.schedule import Schedule
from ..planning.recommendation_engine import generate_system_suggestions
from ..planning.catchup import get_catchup_candidates

def get_student_state(db: Session, user_id: int) -> Dict:
    """
    Central integrated student-state layer
    Inputs: test analytics, review queue, weekly goals, homework, exams, schedules, taught lessons, unfinished tasks, capacity
    Outputs: priorities, recommendations, state changes
    
    Feedback loop: Weekly Goal -> Candidate Task -> Daily Placement -> Test Session -> Attempts -> Analytics -> Weakness/Review -> Student State -> New Recommendations
    """
    # Analytics
    progress = get_progress_detailed(db, user_id)
    
    # Weekly goals
    today = datetime.now(timezone.utc)
    # Current week Saturday
    from datetime import timedelta
    days_since_saturday = (today.weekday() - 5) % 7
    saturday = today - timedelta(days=days_since_saturday)
    week_start = saturday.strftime("%Y-%m-%d")
    
    weekly_goals = db.query(WeeklyGoal).filter(
        WeeklyGoal.user_id == user_id,
        WeeklyGoal.week_start_date == week_start
    ).all()
    
    # Review queue
    review_pending = db.query(ReviewQueue).filter(
        ReviewQueue.user_id == user_id,
        ReviewQueue.status == "pending"
    ).count()
    
    review_due = db.query(ReviewQueue).filter(
        ReviewQueue.user_id == user_id,
        ReviewQueue.status == "pending",
        ReviewQueue.next_review_date <= today.strftime("%Y-%m-%d")
    ).count()
    
    # Homework
    homework_pending = db.query(Homework).filter(
        Homework.user_id == user_id,
        Homework.status.in_(["pending", "in_progress"])
    ).count()
    
    homework_overdue = db.query(Homework).filter(
        Homework.user_id == user_id,
        Homework.status.in_(["pending", "in_progress"]),
        Homework.due_date < today.strftime("%Y-%m-%d")
    ).count()
    
    # Exams
    upcoming_exams = db.query(Exam).filter(
        Exam.user_id == user_id,
        Exam.exam_date >= today.strftime("%Y-%m-%d")
    ).count()
    
    # Unfinished tasks
    unfinished_tasks = db.query(Task).filter(
        Task.user_id == user_id,
        Task.status.in_(["pending", "in_progress", "overdue"])
    ).count()
    
    # Schedules
    schedules_count = db.query(Schedule).filter(Schedule.user_id == user_id).count()
    
    # Weaknesses
    weakest = get_weakest_topics(db, user_id, limit=5)
    
    # Recommendations
    suggestions = generate_system_suggestions(db, user_id, week_start)
    
    # Catchup candidates
    catchup = get_catchup_candidates(db, user_id, week_start)
    
    # Priorities - combine signals
    priorities = []
    
    if homework_overdue > 0:
        priorities.append({"type": "homework_overdue", "level": "high", "count": homework_overdue, "message": f"{homework_overdue} تکلیف عقب‌افتاده", "message_en": f"{homework_overdue} overdue homework"})
    
    if review_due > 0:
        priorities.append({"type": "review_due", "level": "high", "count": review_due, "message": f"{review_due} مرور نیاز", "message_en": f"{review_due} reviews due"})
    
    if weakest:
        priorities.append({"type": "weakness", "level": "medium", "count": len(weakest), "message": f"{len(weakest)} مبحث ضعیف", "message_en": f"{len(weakest)} weak topics", "details": weakest})
    
    if unfinished_tasks > 5:
        priorities.append({"type": "unfinished_tasks", "level": "medium", "count": unfinished_tasks, "message": f"{unfinished_tasks} کار ناتمام", "message_en": f"{unfinished_tasks} unfinished tasks"})
    
    if upcoming_exams > 0:
        priorities.append({"type": "upcoming_exam", "level": "high", "count": upcoming_exams, "message": f"{upcoming_exams} امتحان نزدیک", "message_en": f"{upcoming_exams} upcoming exams"})
    
    # State changes - detect improvements or deteriorations
    # For simplicity, compare last 7 days vs previous 7 days accuracy
    from ..models.attempt import QuestionAttempt
    last_7_days = today - timedelta(days=7)
    prev_7_days = today - timedelta(days=14)
    
    recent_attempts = db.query(QuestionAttempt).filter(
        QuestionAttempt.user_id == user_id,
        QuestionAttempt.created_at >= last_7_days
    ).all()
    
    prev_attempts = db.query(QuestionAttempt).filter(
        QuestionAttempt.user_id == user_id,
        QuestionAttempt.created_at >= prev_7_days,
        QuestionAttempt.created_at < last_7_days
    ).all()
    
    def calc_acc(attempts):
        correct = sum(1 for a in attempts if a.is_correct)
        wrong = sum(1 for a in attempts if a.is_correct is False)
        total = correct + wrong
        return (correct / total * 100) if total > 0 else 0
    
    recent_acc = calc_acc(recent_attempts)
    prev_acc = calc_acc(prev_attempts)
    
    state_changes = []
    if recent_acc > prev_acc + 5:
        state_changes.append({"type": "improvement", "message": f"دقت شما {recent_acc - prev_acc:.0f}% بهبود یافته", "message_en": f"Accuracy improved by {recent_acc - prev_acc:.0f}%"})
    elif recent_acc < prev_acc - 5:
        state_changes.append({"type": "decline", "message": f"دقت شما {prev_acc - recent_acc:.0f}% کاهش یافته", "message_en": f"Accuracy declined by {prev_acc - recent_acc:.0f}%"})
    
    return {
        "user_id": user_id,
        "week_start": week_start,
        "analytics_summary": {
            "overall_mastery": progress["overall"]["mastery"]["mastery_percent"],
            "overall_accuracy": progress["overall"]["accuracy"]["accuracy_percent"],
            "overall_coverage": progress["overall"]["coverage"]["coverage_percent"],
            "total_tests": progress["overall"]["volume"]["total_tests"],
            "total_questions": progress["overall"]["volume"]["total_questions"]
        },
        "counts": {
            "review_pending": review_pending,
            "review_due": review_due,
            "homework_pending": homework_pending,
            "homework_overdue": homework_overdue,
            "upcoming_exams": upcoming_exams,
            "unfinished_tasks": unfinished_tasks,
            "schedules": schedules_count
        },
        "priorities": priorities,
        "weakest_topics": weakest,
        "suggestions": suggestions["suggestions"][:5],
        "capacity_warnings": suggestions["capacity_warnings"],
        "catchup_candidates_count": len(catchup),
        "state_changes": state_changes,
        "feedback_loop": {
            "description": "Weekly Goal -> Candidate Task -> Daily Placement -> Test Session -> Attempts -> Analytics -> Weakness/Review -> Student State -> New Recommendations",
            "current_stage": "Student State aggregation"
        }
    }
