from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...schemas.planner import TaskCreate, TaskOut, DailyPlacementCreate, DailyPlacementOut, PlannerWeekOut, PlannerDayOut, PlannerSuggestionsOut, ReorderRequest, CandidateTaskGenerationRequest
from ...services import planner_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/planner", tags=["Planner"])

@router.post("/tasks", response_model=TaskOut)
def create_task(data: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = planner_service.create_task(db, current_user.id, data.model_dump())
    return build_task_out(db, task)

@router.get("/tasks", response_model=List[TaskOut])
def list_tasks(status: Optional[str] = None, weekly_goal_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tasks = planner_service.get_tasks(db, current_user.id, status=status, weekly_goal_id=weekly_goal_id)
    return [build_task_out(db, t) for t in tasks]

@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = planner_service.get_task(db, task_id, current_user.id)
    return build_task_out(db, task)

@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, updates: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = planner_service.update_task(db, task_id, current_user.id, updates)
    return build_task_out(db, task)

@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    planner_service.delete_task(db, task_id, current_user.id)
    return {"status": "deleted"}

@router.post("/placements", response_model=DailyPlacementOut)
def create_placement(data: DailyPlacementCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    placement = planner_service.create_placement(db, current_user.id, data.task_id, data.date, data.day_of_week, data.order_index, data.is_catchup)
    return build_placement_out(db, placement)

@router.get("/week", response_model=PlannerWeekOut)
def get_week(week_start: str = Query(..., description="Saturday YYYY-MM-DD"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    week_data = planner_service.get_planner_week(db, current_user.id, week_start)
    # Build response
    days_out = []
    for day in week_data["days"]:
        placements_out = [build_placement_out(db, p) for p in day["placements"]]
        days_out.append(PlannerDayOut(
            date=day["date"],
            day_of_week=day["day_of_week"],
            is_catchup_day=day["is_catchup_day"],
            available_capacity_minutes=day["available_capacity_minutes"],
            planned_minutes=day["planned_minutes"],
            is_over_capacity=day["is_over_capacity"],
            placements=placements_out
        ))
    
    unplaced_out = [build_task_out(db, t) for t in week_data["unplaced_tasks"]]
    
    return PlannerWeekOut(
        week_start=week_data["week_start"],
        week_end=week_data["week_end"],
        days=days_out,
        unplaced_tasks=unplaced_out
    )

@router.post("/reorder")
def reorder(data: ReorderRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    planner_service.reorder_placements(db, current_user.id, data.placements)
    return {"status": "ok"}

@router.get("/suggestions")
def suggestions(week_start: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = planner_service.get_system_suggestions(db, current_user.id, week_start)
    # Build task out for suggestions
    suggestions_out = []
    for sug in result["suggestions"]:
        task_out = build_task_out(db, sug["task"])
        suggestions_out.append({
            "task": task_out,
            "reasons": sug["reasons"],
            "score": sug["score"],
            "suggested_date": sug.get("suggested_date")
        })
    return {
        "suggestions": suggestions_out,
        "capacity_warnings": result["capacity_warnings"],
        "catchup_candidates": []
    }

@router.get("/catchup")
def catchup(week_start: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    info = planner_service.get_catchup_info(db, current_user.id, week_start)
    # Convert tasks
    candidates_out = [build_task_out(db, t) for t in info["candidates"]]
    assigned_out = [{"task": build_task_out(db, a["task"]), "suggested_date": a["suggested_date"], "day": a["day"]} for a in info["assigned"]]
    return {
        "candidates": candidates_out,
        "assigned": assigned_out,
        "unassigned": [build_task_out(db, t) for t in info["unassigned"]],
        "thursday_capacity": info["thursday_capacity"],
        "friday_capacity": info["friday_capacity"]
    }

def build_task_out(db, task):
    from ...models.book import Book
    from ...models.book_node import BookNode
    book_title = None
    node_title = None
    if task.book_id:
        book = db.query(Book).filter(Book.id == task.book_id).first()
        if book:
            book_title = book.title_fa or book.title
    if task.book_node_id:
        node = db.query(BookNode).filter(BookNode.id == task.book_node_id).first()
        if node:
            node_title = node.title_fa or node.title
    return TaskOut(
        id=task.id,
        user_id=task.user_id,
        title=task.title,
        title_fa=task.title_fa,
        description=task.description,
        source=task.source,
        source_id=task.source_id,
        book_id=task.book_id,
        book_node_id=task.book_node_id,
        test_set_id=task.test_set_id,
        weekly_goal_id=task.weekly_goal_id,
        task_type=task.task_type,
        status=task.status,
        priority=task.priority,
        estimated_duration_minutes=task.estimated_duration_minutes,
        reason=task.reason,
        reason_structured=task.reason_structured,
        due_date=task.due_date,
        completed_at=task.completed_at,
        book_title=book_title,
        node_title=node_title
    )

def build_placement_out(db, placement):
    task = db.query(planner_service.Task).filter(planner_service.Task.id == placement.task_id).first()
    task_out = build_task_out(db, task) if task else None
    return DailyPlacementOut(
        id=placement.id,
        user_id=placement.user_id,
        task_id=placement.task_id,
        date=placement.date,
        day_of_week=placement.day_of_week,
        order_index=placement.order_index,
        is_catchup=placement.is_catchup,
        task=task_out
    )
