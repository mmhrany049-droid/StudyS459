from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import json
from ..models.task import Task, DailyTaskPlacement
from ..models.book import Book
from ..models.book_node import BookNode
from ..planning.recommendation_engine import generate_system_suggestions
from ..planning.capacity import check_over_capacity, calculate_available_capacity, calculate_planned_minutes
from ..planning.catchup import get_catchup_candidates, assign_catchup_tasks

def create_task(db: Session, user_id: int, task_data: dict) -> Task:
    book_id = task_data.get("book_id")
    book_node_id = task_data.get("book_node_id")
    
    if book_id:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise HTTPException(status_code=400, detail=f"Invalid book_id {book_id}")
    if book_node_id:
        node = db.query(BookNode).filter(BookNode.id == book_node_id).first()
        if not node:
            raise HTTPException(status_code=400, detail=f"Invalid book_node_id {book_node_id}")
    
    task = Task(
        user_id=user_id,
        title=task_data.get("title"),
        title_fa=task_data.get("title_fa"),
        description=task_data.get("description"),
        source=task_data.get("source", "manual"),
        source_id=task_data.get("source_id"),
        book_id=book_id,
        book_node_id=book_node_id,
        test_set_id=task_data.get("test_set_id"),
        weekly_goal_id=task_data.get("weekly_goal_id"),
        task_type=task_data.get("task_type", "test"),
        priority=task_data.get("priority", 0),
        estimated_duration_minutes=task_data.get("estimated_duration_minutes", 30),
        reason=task_data.get("reason"),
        reason_structured=task_data.get("reason_structured"),
        due_date=task_data.get("due_date")
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def get_tasks(db: Session, user_id: int, status: Optional[str] = None, weekly_goal_id: Optional[int] = None):
    q = db.query(Task).filter(Task.user_id == user_id)
    if status:
        q = q.filter(Task.status == status)
    if weekly_goal_id:
        q = q.filter(Task.weekly_goal_id == weekly_goal_id)
    q = q.order_by(Task.priority.desc(), Task.created_at.asc())
    return q.all()

def get_task(db: Session, task_id: int, user_id: int):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

def update_task(db: Session, task_id: int, user_id: int, updates: dict):
    task = get_task(db, task_id, user_id)
    for key, value in updates.items():
        if hasattr(task, key):
            setattr(task, key, value)
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task

def delete_task(db: Session, task_id: int, user_id: int):
    task = get_task(db, task_id, user_id)
    db.delete(task)
    db.commit()
    return True

def create_placement(db: Session, user_id: int, task_id: int, date: str, day_of_week: Optional[str] = None, order_index: int = 0, is_catchup: bool = False):
    task = get_task(db, task_id, user_id)
    
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")
    
    # Determine day_of_week if not provided
    if not day_of_week:
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            weekday_map = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
            day_of_week = weekday_map[dt.weekday()]
        except:
            day_of_week = "saturday"
    
    # Check if placement already exists for same task and date
    existing = db.query(DailyTaskPlacement).filter(
        DailyTaskPlacement.user_id == user_id,
        DailyTaskPlacement.task_id == task_id,
        DailyTaskPlacement.date == date
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Task already placed on this date")
    
    placement = DailyTaskPlacement(
        user_id=user_id,
        task_id=task_id,
        date=date,
        day_of_week=day_of_week,
        order_index=order_index,
        is_catchup=is_catchup
    )
    db.add(placement)
    db.commit()
    db.refresh(placement)
    
    # Check over-capacity warning, but do NOT silently delete
    cap_check = check_over_capacity(db, user_id, date, day_of_week)
    # Return placement with warning info if over capacity
    
    return placement

def get_planner_week(db: Session, user_id: int, week_start: str):
    """
    week_start: Saturday YYYY-MM-DD
    Returns week with days Sat-Fri
    """
    try:
        start_dt = datetime.strptime(week_start, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid week_start format")
    
    days = []
    for i in range(7):
        curr_dt = start_dt + timedelta(days=i)
        date_str = curr_dt.strftime("%Y-%m-%d")
        weekday_map = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
        # Adjust mapping: Saturday is start
        # Our week: 0=Saturday, 1=Sunday, 2=Monday, 3=Tuesday, 4=Wednesday, 5=Thursday, 6=Friday
        persian_week = ["saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
        day_of_week = persian_week[i]
        is_catchup = day_of_week in ["thursday", "friday"]
        
        placements = db.query(DailyTaskPlacement).filter(
            DailyTaskPlacement.user_id == user_id,
            DailyTaskPlacement.date == date_str
        ).order_by(DailyTaskPlacement.order_index.asc()).all()
        
        available = calculate_available_capacity(db, user_id, date_str, day_of_week)
        planned = calculate_planned_minutes(db, user_id, date_str)
        
        days.append({
            "date": date_str,
            "day_of_week": day_of_week,
            "is_catchup_day": is_catchup,
            "available_capacity_minutes": available,
            "planned_minutes": planned,
            "is_over_capacity": planned > available,
            "placements": placements
        })
    
    # Unplaced tasks
    # Tasks that are pending and not placed in this week
    week_end = (start_dt + timedelta(days=6)).strftime("%Y-%m-%d")
    placed_task_ids = db.query(DailyTaskPlacement.task_id).filter(
        DailyTaskPlacement.user_id == user_id,
        DailyTaskPlacement.date >= week_start,
        DailyTaskPlacement.date <= week_end
    ).distinct()
    
    unplaced = db.query(Task).filter(
        Task.user_id == user_id,
        Task.status.in_(["pending", "in_progress"]),
        ~Task.id.in_(placed_task_ids)
    ).all()
    
    return {
        "week_start": week_start,
        "week_end": week_end,
        "days": days,
        "unplaced_tasks": unplaced
    }

def reorder_placements(db: Session, user_id: int, reorder_data: List[Dict]):
    """
    Support drag and drop, moving tasks between days, manual reordering
    """
    for item in reorder_data:
        placement_id = item.get("placement_id")
        new_order = item.get("order_index")
        new_date = item.get("date")
        
        placement = db.query(DailyTaskPlacement).filter(
            DailyTaskPlacement.id == placement_id,
            DailyTaskPlacement.user_id == user_id
        ).first()
        if not placement:
            raise HTTPException(status_code=404, detail=f"Placement {placement_id} not found")
        
        if new_order is not None:
            placement.order_index = new_order
        if new_date:
            try:
                datetime.strptime(new_date, "%Y-%m-%d")
                placement.date = new_date
                # Update day_of_week
                dt = datetime.strptime(new_date, "%Y-%m-%d")
                persian_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                # Map to our week: need proper mapping
                # For simplicity, use weekday
                weekday_map = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
                placement.day_of_week = weekday_map[dt.weekday()]
            except:
                raise HTTPException(status_code=400, detail=f"Invalid date {new_date}")
    
    db.commit()
    return True

def get_system_suggestions(db: Session, user_id: int, week_start: Optional[str] = None):
    return generate_system_suggestions(db, user_id, week_start)

def get_catchup_info(db: Session, user_id: int, week_start: str):
    try:
        start_dt = datetime.strptime(week_start, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid week_start")
    
    thursday_date = (start_dt + timedelta(days=5)).strftime("%Y-%m-%d")
    friday_date = (start_dt + timedelta(days=6)).strftime("%Y-%m-%d")
    
    return assign_catchup_tasks(db, user_id, thursday_date, friday_date)
