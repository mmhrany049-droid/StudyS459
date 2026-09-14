from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class TaskCreate(BaseModel):
    title: str
    title_fa: Optional[str] = None
    description: Optional[str] = None
    source: str = "manual"
    source_id: Optional[int] = None
    book_id: Optional[int] = None
    book_node_id: Optional[int] = None
    test_set_id: Optional[int] = None
    weekly_goal_id: Optional[int] = None
    task_type: str = "test"
    priority: int = 0
    estimated_duration_minutes: int = 30
    reason: Optional[str] = None
    due_date: Optional[str] = None

class TaskOut(BaseModel):
    id: int
    user_id: int
    title: str
    title_fa: Optional[str] = None
    description: Optional[str] = None
    source: str
    source_id: Optional[int] = None
    book_id: Optional[int] = None
    book_node_id: Optional[int] = None
    test_set_id: Optional[int] = None
    weekly_goal_id: Optional[int] = None
    task_type: str
    status: str
    priority: int
    estimated_duration_minutes: int
    reason: Optional[str] = None
    reason_structured: Optional[str] = None
    due_date: Optional[str] = None
    completed_at: Optional[datetime] = None
    book_title: Optional[str] = None
    node_title: Optional[str] = None
    
    class Config:
        from_attributes = True

class DailyPlacementCreate(BaseModel):
    task_id: int
    date: str
    day_of_week: Optional[str] = None
    order_index: int = 0
    is_catchup: bool = False

class DailyPlacementOut(BaseModel):
    id: int
    user_id: int
    task_id: int
    date: str
    day_of_week: Optional[str] = None
    order_index: int
    is_catchup: bool
    task: Optional[TaskOut] = None
    
    class Config:
        from_attributes = True

class PlannerDayOut(BaseModel):
    date: str
    day_of_week: str
    is_catchup_day: bool
    available_capacity_minutes: int
    planned_minutes: int
    is_over_capacity: bool
    placements: List[DailyPlacementOut] = []

class PlannerWeekOut(BaseModel):
    week_start: str
    week_end: str
    days: List[PlannerDayOut] = []
    unplaced_tasks: List[TaskOut] = []

class RecommendationReason(BaseModel):
    type: str  # weekly_goal, weakness, review, homework, exam, capacity, deadline
    description: str
    description_fa: str
    weight: float = 1.0
    related_id: Optional[int] = None

class SystemSuggestionOut(BaseModel):
    task: TaskOut
    reasons: List[RecommendationReason]
    score: float
    suggested_date: Optional[str] = None

class PlannerSuggestionsOut(BaseModel):
    suggestions: List[SystemSuggestionOut] = []
    capacity_warnings: List[Dict[str, Any]] = []
    catchup_candidates: List[TaskOut] = []

class ReorderRequest(BaseModel):
    placements: List[Dict[str, Any]]  # [{"placement_id": 1, "order_index": 0, "date": "2024-..."}]

class CandidateTaskGenerationRequest(BaseModel):
    weekly_goal_id: int
