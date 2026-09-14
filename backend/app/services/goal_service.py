from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from datetime import datetime, timezone
from ..models.goal import WeeklyGoal, WeeklyGoalItem
from ..models.book import Book
from ..models.book_node import BookNode
from ..models.test_session import TestSession
from ..models.task import Task
import json

def create_weekly_goal(
    db: Session,
    user_id: int,
    week_start_date: str,
    week_end_date: str,
    test_count_goal: Optional[int] = None,
    items: List[dict] = []
):
    # Check existing goal for same week
    existing = db.query(WeeklyGoal).filter(
        WeeklyGoal.user_id == user_id,
        WeeklyGoal.week_start_date == week_start_date
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Weekly goal already exists for this week")
    
    goal = WeeklyGoal(
        user_id=user_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        test_count_goal=test_count_goal,
        topic_goal_enabled=len(items) > 0
    )
    db.add(goal)
    db.flush()
    
    for item_data in items:
        book_id = item_data.get("book_id")
        book_node_id = item_data.get("book_node_id")
        target_tests = item_data.get("target_tests", 1)
        priority = item_data.get("priority", 0)
        
        # Validate book exists
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Invalid book_id {book_id}")
        
        if book_node_id:
            node = db.query(BookNode).filter(BookNode.id == book_node_id, BookNode.book_id == book_id).first()
            if not node:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"Invalid book_node_id {book_node_id} for book {book_id}")
        
        item = WeeklyGoalItem(
            weekly_goal_id=goal.id,
            book_id=book_id,
            book_node_id=book_node_id,
            target_tests=target_tests,
            priority=priority
        )
        db.add(item)
    
    db.commit()
    db.refresh(goal)
    return goal

def get_weekly_goals(db: Session, user_id: int, status: Optional[str] = None):
    q = db.query(WeeklyGoal).filter(WeeklyGoal.user_id == user_id)
    if status:
        q = q.filter(WeeklyGoal.status == status)
    q = q.order_by(WeeklyGoal.week_start_date.desc())
    return q.all()

def get_weekly_goal(db: Session, goal_id: int, user_id: int):
    goal = db.query(WeeklyGoal).filter(WeeklyGoal.id == goal_id, WeeklyGoal.user_id == user_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Weekly goal not found")
    return goal

def update_goal_progress(db: Session, goal_id: int, user_id: int):
    goal = get_weekly_goal(db, goal_id, user_id)
    
    # For each goal item, count completed tests in week that match book/node
    from datetime import datetime
    # Parse week dates
    try:
        week_start = datetime.fromisoformat(goal.week_start_date)
        week_end = datetime.fromisoformat(goal.week_end_date)
    except:
        # Assume YYYY-MM-DD
        from datetime import datetime
        week_start = datetime.strptime(goal.week_start_date, "%Y-%m-%d")
        week_end = datetime.strptime(goal.week_end_date, "%Y-%m-%d")
    
    # Make timezone aware
    if week_start.tzinfo is None:
        week_start = week_start.replace(tzinfo=timezone.utc)
    if week_end.tzinfo is None:
        week_end = week_end.replace(tzinfo=timezone.utc)
    
    for item in goal.items:
        # Count test sessions in week matching book and optionally node
        query = db.query(TestSession).filter(
            TestSession.user_id == user_id,
            TestSession.started_at >= week_start,
            TestSession.started_at <= week_end,
            TestSession.status == "finished"
        )
        if item.book_id:
            query = query.filter(TestSession.book_id == item.book_id)
        # For node filtering, need to check if session's questions map to node - simplified: if any question in session maps to node
        # For now, count all sessions for book if node specified? We'll do more precise later
        count = query.count()
        item.completed_tests = count
    
    db.commit()
    db.refresh(goal)
    return goal

def generate_candidate_tasks_from_goal(db: Session, weekly_goal_id: int, user_id: int) -> List[Task]:
    """
    Priority rule: If both exist, topic goals drive topic selection, test-count goal controls overall volume
    Task may satisfy both goals, progress must NOT double-count incorrectly
    """
    goal = get_weekly_goal(db, weekly_goal_id, user_id)
    
    tasks_created = []
    
    # If topic goals exist, they drive selection
    if goal.items:
        for item in goal.items:
            # How many tasks needed? target - completed
            needed = (item.target_tests or 1) - (item.completed_tests or 0)
            if needed <= 0:
                continue
            
            book = db.query(Book).filter(Book.id == item.book_id).first()
            node = db.query(BookNode).filter(BookNode.id == item.book_node_id).first() if item.book_node_id else None
            
            for i in range(needed):
                # Check if task already exists for this goal item
                existing = db.query(Task).filter(
                    Task.user_id == user_id,
                    Task.weekly_goal_id == goal.id,
                    Task.book_id == item.book_id,
                    Task.book_node_id == item.book_node_id,
                    Task.status.in_(["pending", "in_progress"])
                ).first()
                if existing and i == 0:
                    # Avoid duplicate if one already pending? But need needed count
                    # Let's check count
                    pending_count = db.query(Task).filter(
                        Task.user_id == user_id,
                        Task.weekly_goal_id == goal.id,
                        Task.book_id == item.book_id,
                        Task.book_node_id == item.book_node_id,
                        Task.status.in_(["pending", "in_progress"])
                    ).count()
                    if pending_count >= needed:
                        break
                
                title = f"تست {book.title_fa or book.title}"
                if node:
                    title += f" - {node.title_fa or node.title}"
                
                reason_structured = json.dumps([
                    {"type": "weekly_goal", "description": f"Weekly goal for {node.title if node else book.title}", "description_fa": f"هدف هفتگی: {node.title_fa or node.title if node else book.title_fa or book.title}", "weight": 1.0}
                ], ensure_ascii=False)
                
                task = Task(
                    user_id=user_id,
                    title=title,
                    title_fa=title,
                    source="weekly_goal",
                    source_id=item.id,
                    book_id=item.book_id,
                    book_node_id=item.book_node_id,
                    weekly_goal_id=goal.id,
                    task_type="test",
                    status="pending",
                    priority=item.priority,
                    estimated_duration_minutes=45,
                    reason=f"هدف هفتگی: {node.title if node else book.title}",
                    reason_structured=reason_structured
                )
                db.add(task)
                tasks_created.append(task)
    
    # If test_count_goal exists and no topic goals, or still need volume
    if goal.test_count_goal:
        # Count existing tasks for this goal
        existing_task_count = db.query(Task).filter(
            Task.user_id == user_id,
            Task.weekly_goal_id == goal.id,
            Task.status.in_(["pending", "in_progress", "completed"])
        ).count()
        
        # If topic goals exist, test_count_goal controls overall volume, but tasks already created from topics may satisfy both
        # So we should ensure total tasks >= test_count_goal
        total_needed = goal.test_count_goal - existing_task_count
        if total_needed > 0 and not goal.items:
            # Only count goal, no topic goals - create generic tasks
            for i in range(total_needed):
                task = Task(
                    user_id=user_id,
                    title=f"تست عمومی - هفته {goal.week_start_date}",
                    title_fa=f"تست عمومی - هفته {goal.week_start_date}",
                    source="weekly_goal",
                    source_id=goal.id,
                    weekly_goal_id=goal.id,
                    task_type="test",
                    status="pending",
                    priority=0,
                    estimated_duration_minutes=45,
                    reason="هدف هفتگی تعداد تست",
                    reason_structured=json.dumps([{"type": "weekly_goal", "description": "Test count goal", "description_fa": "هدف هفتگی تعداد تست", "weight": 1.0}], ensure_ascii=False)
                )
                db.add(task)
                tasks_created.append(task)
    
    db.commit()
    for t in tasks_created:
        db.refresh(t)
    return tasks_created

def get_goal_progress(db: Session, goal_id: int, user_id: int) -> dict:
    goal = get_weekly_goal(db, goal_id, user_id)
    update_goal_progress(db, goal_id, user_id)
    db.refresh(goal)
    
    total_completed = sum(item.completed_tests for item in goal.items)
    total_target = sum(item.target_tests or 0 for item in goal.items)
    
    progress = {
        "goal_id": goal.id,
        "test_count_progress": None,
        "topic_progress": []
    }
    
    if goal.test_count_goal:
        # Count finished test sessions in week
        from datetime import datetime
        try:
            week_start = datetime.fromisoformat(goal.week_start_date)
            week_end = datetime.fromisoformat(goal.week_end_date)
        except:
            week_start = datetime.strptime(goal.week_start_date, "%Y-%m-%d")
            week_end = datetime.strptime(goal.week_end_date, "%Y-%m-%d")
        if week_start.tzinfo is None:
            week_start = week_start.replace(tzinfo=timezone.utc)
        if week_end.tzinfo is None:
            week_end = week_end.replace(tzinfo=timezone.utc)
        
        completed = db.query(TestSession).filter(
            TestSession.user_id == user_id,
            TestSession.started_at >= week_start,
            TestSession.started_at <= week_end,
            TestSession.status == "finished"
        ).count()
        
        progress["test_count_progress"] = {
            "target": goal.test_count_goal,
            "completed": completed,
            "percent": (completed / goal.test_count_goal * 100) if goal.test_count_goal else 0
        }
    
    for item in goal.items:
        book = db.query(Book).filter(Book.id == item.book_id).first()
        node = db.query(BookNode).filter(BookNode.id == item.book_node_id).first() if item.book_node_id else None
        progress["topic_progress"].append({
            "item_id": item.id,
            "book_id": item.book_id,
            "book_title": book.title_fa or book.title if book else None,
            "node_id": item.book_node_id,
            "node_title": node.title_fa or node.title if node else None,
            "target": item.target_tests,
            "completed": item.completed_tests,
            "percent": (item.completed_tests / item.target_tests * 100) if item.target_tests else 0
        })
    
    return progress
