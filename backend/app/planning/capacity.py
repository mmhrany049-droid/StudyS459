from typing import List, Dict
from datetime import datetime, time
from sqlalchemy.orm import Session
from ..models.schedule import Schedule
from ..models.task import Task, DailyTaskPlacement

def parse_time_str(t_str: str) -> time:
    try:
        h, m = map(int, t_str.split(":"))
        return time(hour=h, minute=m)
    except:
        return time(hour=0, minute=0)

def calculate_available_capacity(
    db: Session,
    user_id: int,
    date_str: str,
    day_of_week: str
) -> int:
    """
    Use explicit school/class schedules to calculate available capacity
    Do not assume commute time unless configured
    Returns available minutes
    """
    # Get schedules for this day
    schedules = db.query(Schedule).filter(
        Schedule.user_id == user_id,
        Schedule.day_of_week == day_of_week
    ).all()
    
    # Assume day has 16 waking hours = 960 minutes baseline, or configurable
    # But better: assume study can happen 06:00-23:00 = 17h = 1020 minutes
    # Subtract busy hours from schedules
    total_busy_minutes = 0
    for sched in schedules:
        if sched.schedule_type in ["school", "external_class", "busy"]:
            start = parse_time_str(sched.start_time)
            end = parse_time_str(sched.end_time)
            # Calculate duration
            start_minutes = start.hour * 60 + start.minute
            end_minutes = end.hour * 60 + end.minute
            if end_minutes < start_minutes:
                end_minutes += 24*60
            duration = end_minutes - start_minutes
            total_busy_minutes += duration
    
    # Available capacity: baseline minus busy, minus buffer
    baseline = 10 * 60  # 10 hours study capacity max per day default
    # For catch-up days (Thursday, Friday), more capacity
    if day_of_week in ["thursday", "friday", "پنجشنبه", "جمعه"]:
        baseline = 12 * 60
    
    available = baseline - total_busy_minutes
    # But ensure at least 0, and not negative
    available = max(0, available)
    
    # Also consider already planned tasks? That's separate for warning
    return available

def calculate_planned_minutes(
    db: Session,
    user_id: int,
    date_str: str
) -> int:
    placements = db.query(DailyTaskPlacement).filter(
        DailyTaskPlacement.user_id == user_id,
        DailyTaskPlacement.date == date_str
    ).all()
    
    total = 0
    for pl in placements:
        task = db.query(Task).filter(Task.id == pl.task_id).first()
        if task:
            total += task.estimated_duration_minutes
    return total

def check_over_capacity(
    db: Session,
    user_id: int,
    date_str: str,
    day_of_week: str
) -> Dict:
    available = calculate_available_capacity(db, user_id, date_str, day_of_week)
    planned = calculate_planned_minutes(db, user_id, date_str)
    
    return {
        "date": date_str,
        "day_of_week": day_of_week,
        "available_capacity_minutes": available,
        "planned_minutes": planned,
        "is_over_capacity": planned > available,
        "over_by": max(0, planned - available)
    }
