from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...schemas.goal import WeeklyGoalCreate, WeeklyGoalOut, GoalProgressOut
from ...services import goal_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/goals", tags=["Goals"])

@router.post("/", response_model=WeeklyGoalOut)
def create_goal(data: WeeklyGoalCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    goal = goal_service.create_weekly_goal(
        db=db,
        user_id=current_user.id,
        week_start_date=data.week_start_date,
        week_end_date=data.week_end_date,
        test_count_goal=data.test_count_goal,
        items=[item.model_dump() for item in data.items]
    )
    # Build out response
    return build_goal_out(db, goal)

@router.get("/", response_model=List[WeeklyGoalOut])
def list_goals(status: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    goals = goal_service.get_weekly_goals(db, current_user.id, status=status)
    return [build_goal_out(db, g) for g in goals]

@router.get("/{goal_id}", response_model=WeeklyGoalOut)
def get_goal(goal_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    goal = goal_service.get_weekly_goal(db, goal_id, current_user.id)
    return build_goal_out(db, goal)

@router.get("/{goal_id}/progress")
def goal_progress(goal_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return goal_service.get_goal_progress(db, goal_id, current_user.id)

@router.post("/{goal_id}/generate-tasks")
def generate_tasks(goal_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tasks = goal_service.generate_candidate_tasks_from_goal(db, goal_id, current_user.id)
    return {"created": len(tasks), "tasks": [{"id": t.id, "title": t.title} for t in tasks]}

def build_goal_out(db, goal):
    from ...models.book import Book
    from ...models.book_node import BookNode
    items_out = []
    total_completed = 0
    for item in goal.items:
        book = db.query(Book).filter(Book.id == item.book_id).first()
        node = db.query(BookNode).filter(BookNode.id == item.book_node_id).first() if item.book_node_id else None
        total_completed += item.completed_tests
        items_out.append({
            "id": item.id,
            "weekly_goal_id": item.weekly_goal_id,
            "book_id": item.book_id,
            "book_node_id": item.book_node_id,
            "target_tests": item.target_tests,
            "completed_tests": item.completed_tests,
            "priority": item.priority,
            "book_title": book.title_fa or book.title if book else None,
            "node_title": node.title_fa or node.title if node else None
        })
    
    total_target = sum(item.target_tests or 0 for item in goal.items) or goal.test_count_goal or 1
    progress_percent = (total_completed / total_target * 100) if total_target else 0
    
    return WeeklyGoalOut(
        id=goal.id,
        user_id=goal.user_id,
        week_start_date=goal.week_start_date,
        week_end_date=goal.week_end_date,
        test_count_goal=goal.test_count_goal,
        topic_goal_enabled=goal.topic_goal_enabled,
        status=goal.status,
        items=items_out,
        total_completed_tests=total_completed,
        progress_percent=progress_percent
    )
