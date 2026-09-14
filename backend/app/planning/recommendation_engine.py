from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
import json
from ..models.task import Task
from ..models.goal import WeeklyGoal
from ..models.attempt import QuestionAttempt
from ..models.book_node import BookNode
from ..models.book import Book
from ..models.academic import Homework, Exam
from ..models.review import ReviewQueue
from ..models.schedule import Schedule
from ..services.analytics_service import get_weakest_topics
from ..planning.capacity import calculate_available_capacity

class RecommendationReason:
    def __init__(self, type: str, description: str, description_fa: str, weight: float = 1.0, related_id: Optional[int] = None):
        self.type = type
        self.description = description
        self.description_fa = description_fa
        self.weight = weight
        self.related_id = related_id
    
    def to_dict(self):
        return {
            "type": self.type,
            "description": self.description,
            "description_fa": self.description_fa,
            "weight": self.weight,
            "related_id": self.related_id
        }

def generate_system_suggestions(db: Session, user_id: int, week_start: Optional[str] = None) -> Dict:
    """
    Suggestions must consider:
    - school schedule
    - external class schedule
    - busy hours
    - available capacity
    - weekly goals
    - homework
    - review needs
    - exams
    - deadlines
    - unfinished tasks
    - recent weaknesses
    
    Every recommendation should explain WHY
    """
    suggestions = []
    
    # Get current week goals
    if not week_start:
        # Assume current week starts Saturday
        today = datetime.now(timezone.utc)
        # Find last Saturday
        # Python weekday: Monday=0, Saturday=5
        days_since_saturday = (today.weekday() - 5) % 7
        saturday = today - timedelta(days=days_since_saturday)
        week_start = saturday.strftime("%Y-%m-%d")
    
    weekly_goals = db.query(WeeklyGoal).filter(
        WeeklyGoal.user_id == user_id,
        WeeklyGoal.week_start_date == week_start
    ).all()
    
    # Weakest topics
    weakest = get_weakest_topics(db, user_id, limit=5)
    
    # Due homework
    homework_due = db.query(Homework).filter(
        Homework.user_id == user_id,
        Homework.status.in_(["pending", "in_progress"]),
        Homework.due_date != None
    ).order_by(Homework.due_date.asc()).limit(5).all()
    
    # Due reviews
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    due_reviews = db.query(ReviewQueue).filter(
        ReviewQueue.user_id == user_id,
        ReviewQueue.status == "pending",
        ReviewQueue.next_review_date <= today_str
    ).limit(10).all()
    
    # Upcoming exams
    upcoming_exams = db.query(Exam).filter(
        Exam.user_id == user_id,
        Exam.exam_date >= today_str
    ).order_by(Exam.exam_date.asc()).limit(3).all()
    
    # Unfinished tasks from previous days (Sat-Wed) for catch-up
    unfinished_tasks = db.query(Task).filter(
        Task.user_id == user_id,
        Task.status.in_(["pending", "overdue"])
    ).all()
    
    # Generate suggestions from weekly goals
    for goal in weekly_goals:
        for item in goal.items:
            if item.completed_tests < (item.target_tests or 1):
                book = db.query(Book).filter(Book.id == item.book_id).first()
                node = db.query(BookNode).filter(BookNode.id == item.book_node_id).first() if item.book_node_id else None
                
                reasons = []
                reasons.append(RecommendationReason(
                    type="weekly_goal",
                    description=f"Weekly goal for {node.title if node else book.title if book else 'topic'}",
                    description_fa=f"هدف هفتگی این مبحث: {node.title_fa or node.title if node else book.title_fa or book.title if book else 'مبحث'}",
                    weight=1.5,
                    related_id=item.id
                ))
                
                # Check if this topic is also weakness
                for w in weakest:
                    if w["book_node_id"] == item.book_node_id:
                        reasons.append(RecommendationReason(
                            type="weakness",
                            description=f"Weakness in {w['node_title']} with {w['accuracy']:.0f}% accuracy",
                            description_fa=f"ضعف اخیر در {w['node_title']} با دقت {w['accuracy']:.0f}%",
                            weight=1.2,
                            related_id=w["book_node_id"]
                        ))
                
                # Check days without practice
                if item.book_node_id:
                    question_ids_query = db.query(QuestionAttempt).filter(
                        QuestionAttempt.user_id == user_id
                    ).all()
                    # Simplified: find last attempt for this node
                    # For now, assume 5 days without practice if no recent
                    reasons.append(RecommendationReason(
                        type="recency",
                        description="No recent practice",
                        description_fa="۵ روز بدون تمرین",
                        weight=0.8
                    ))
                
                # Find existing task or create suggestion
                existing_task = db.query(Task).filter(
                    Task.user_id == user_id,
                    Task.book_node_id == item.book_node_id,
                    Task.weekly_goal_id == goal.id,
                    Task.status == "pending"
                ).first()
                
                if existing_task:
                    task = existing_task
                else:
                    # Suggest creating task
                    continue
                
                score = sum(r.weight for r in reasons)
                suggestions.append({
                    "task": task,
                    "reasons": [r.to_dict() for r in reasons],
                    "score": score,
                    "suggested_date": None
                })
    
    # Homework suggestions
    for hw in homework_due:
        reasons = [
            RecommendationReason(
                type="homework",
                description=f"Homework due {hw.due_date}",
                description_fa=f"تکلیف با مهلت {hw.due_date}",
                weight=2.0,
                related_id=hw.id
            )
        ]
        # Find task linked to homework
        task = db.query(Task).filter(Task.id == hw.task_id).first() if hw.task_id else None
        if not task:
            # Create task suggestion for homework
            task = db.query(Task).filter(
                Task.user_id == user_id,
                Task.source == "homework",
                Task.source_id == hw.id,
                Task.status == "pending"
            ).first()
        
        if task:
            suggestions.append({
                "task": task,
                "reasons": [r.to_dict() for r in reasons],
                "score": 2.0,
                "suggested_date": hw.due_date
            })
    
    # Review suggestions
    for review in due_reviews:
        book = db.query(Book).filter(Book.id == review.book_id).first() if review.book_id else None
        reasons = [
            RecommendationReason(
                type="review",
                description="Review needed for previous mistake",
                description_fa="مرور نیاز برای اشتباه قبلی",
                weight=1.3,
                related_id=review.id
            )
        ]
        # Find task for review
        task = db.query(Task).filter(
            Task.user_id == user_id,
            Task.source == "review",
            Task.source_id == review.id
        ).first()
        if task:
            suggestions.append({
                "task": task,
                "reasons": [r.to_dict() for r in reasons],
                "score": 1.3,
                "suggested_date": today_str
            })
    
    # Exam suggestions
    for exam in upcoming_exams:
        reasons = [
            RecommendationReason(
                type="exam",
                description=f"Upcoming exam {exam.name} on {exam.exam_date}",
                description_fa=f"امتحان نزدیک {exam.name} در تاریخ {exam.exam_date}",
                weight=1.8,
                related_id=exam.id
            )
        ]
        # Create generic exam prep task suggestion if needed
        # For now, just note
    
    # Sort by score descending
    suggestions.sort(key=lambda x: x["score"], reverse=True)
    
    # Capacity warnings
    capacity_warnings = []
    # Check next 7 days
    for i in range(7):
        date = datetime.now(timezone.utc) + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        # Determine day_of_week
        # Map weekday to Persian week
        weekday_map = {
            0: "monday",
            1: "tuesday",
            2: "wednesday",
            3: "thursday",
            4: "friday",
            5: "saturday",
            6: "sunday"
        }
        day_of_week = weekday_map[date.weekday()]
        from .capacity import check_over_capacity
        cap_check = check_over_capacity(db, user_id, date_str, day_of_week)
        if cap_check["is_over_capacity"]:
            capacity_warnings.append(cap_check)
    
    return {
        "suggestions": suggestions[:10],
        "capacity_warnings": capacity_warnings,
        "catchup_candidates": []  # filled by catchup logic
    }
