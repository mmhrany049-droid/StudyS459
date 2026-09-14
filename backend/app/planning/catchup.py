from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime, timezone, timedelta
from ..models.task import Task, DailyTaskPlacement
from ..models.academic import Homework

def get_catchup_candidates(db: Session, user_id: int, week_start: str = None) -> List[Task]:
    """
    Unfinished Saturday-Wednesday tasks should become eligible for Thursday/Friday catch-up
    Prioritize:
    1. overdue/deadline-sensitive
    2. homework
    3. goal-critical
    4. review-critical
    5. other unfinished tasks
    """
    if not week_start:
        today = datetime.now(timezone.utc)
        days_since_saturday = (today.weekday() - 5) % 7
        saturday = today - timedelta(days=days_since_saturday)
        week_start = saturday.strftime("%Y-%m-%d")
    
    # Get unfinished tasks from Sat-Wed
    # For simplicity, get all pending tasks that have placements before Thursday
    # Or tasks with due_date in past or no placement
    
    # All pending tasks
    pending_tasks = db.query(Task).filter(
        Task.user_id == user_id,
        Task.status.in_(["pending", "in_progress", "overdue"])
    ).all()
    
    # Filter: tasks that were supposed to be done Sat-Wed but not completed
    # For now, consider tasks created before today and not completed
    
    # Prioritize
    def priority_score(task: Task) -> int:
        score = 0
        # Overdue / deadline-sensitive
        if task.due_date:
            try:
                due = datetime.strptime(task.due_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if due < datetime.now(timezone.utc):
                    score += 100  # overdue highest
                elif (due - datetime.now(timezone.utc)).days <= 2:
                    score += 80  # deadline near
            except:
                pass
        
        # Homework
        if task.source == "homework" or task.task_type == "homework":
            score += 70
        
        # Goal-critical
        if task.weekly_goal_id:
            score += 60
        
        # Review-critical
        if task.source == "review":
            score += 50
        
        # Other: by priority field
        score += task.priority
        
        return score
    
    # Sort by priority score descending
    pending_tasks.sort(key=lambda t: priority_score(t), reverse=True)
    
    return pending_tasks

def assign_catchup_tasks(
    db: Session,
    user_id: int,
    thursday_date: str,
    friday_date: str
) -> Dict:
    """
    Do NOT blindly dump everything into catch-up days
    """
    candidates = get_catchup_candidates(db, user_id)
    
    # For now, return candidates with suggested placement
    # Real assignment would check capacity of Thursday/Friday
    
    from .capacity import calculate_available_capacity, calculate_planned_minutes
    
    thursday_cap = calculate_available_capacity(db, user_id, thursday_date, "thursday")
    friday_cap = calculate_available_capacity(db, user_id, friday_date, "friday")
    
    thursday_planned = calculate_planned_minutes(db, user_id, thursday_date)
    friday_planned = calculate_planned_minutes(db, user_id, friday_date)
    
    thursday_remaining = thursday_cap - thursday_planned
    friday_remaining = friday_cap - friday_planned
    
    assigned = []
    unassigned = []
    
    for task in candidates:
        if thursday_remaining >= task.estimated_duration_minutes:
            assigned.append({"task": task, "suggested_date": thursday_date, "day": "thursday"})
            thursday_remaining -= task.estimated_duration_minutes
        elif friday_remaining >= task.estimated_duration_minutes:
            assigned.append({"task": task, "suggested_date": friday_date, "day": "friday"})
            friday_remaining -= task.estimated_duration_minutes
        else:
            unassigned.append(task)
    
    return {
        "candidates": candidates,
        "assigned": assigned,
        "unassigned": unassigned,
        "thursday_capacity": {"total": thursday_cap, "planned": thursday_planned, "remaining": thursday_remaining},
        "friday_capacity": {"total": friday_cap, "planned": friday_planned, "remaining": friday_remaining}
    }
