from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class WeeklyGoalItemCreate(BaseModel):
    book_id: int
    book_node_id: Optional[int] = None
    target_tests: int = 1
    priority: int = 0

class WeeklyGoalCreate(BaseModel):
    week_start_date: str
    week_end_date: str
    test_count_goal: Optional[int] = None
    items: List[WeeklyGoalItemCreate] = []

class WeeklyGoalItemOut(BaseModel):
    id: int
    weekly_goal_id: int
    book_id: int
    book_node_id: Optional[int] = None
    target_tests: Optional[int] = None
    completed_tests: int
    priority: int
    book_title: Optional[str] = None
    node_title: Optional[str] = None
    
    class Config:
        from_attributes = True

class WeeklyGoalOut(BaseModel):
    id: int
    user_id: int
    week_start_date: str
    week_end_date: str
    test_count_goal: Optional[int] = None
    topic_goal_enabled: bool
    status: str
    items: List[WeeklyGoalItemOut] = []
    total_completed_tests: int = 0
    progress_percent: Optional[float] = None
    
    class Config:
        from_attributes = True

class GoalProgressOut(BaseModel):
    goal_id: int
    test_count_progress: Optional[dict] = None
    topic_progress: List[dict] = []
