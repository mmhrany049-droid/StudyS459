"""Weekly goal routes (spec 14). Routes only."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db import get_db
from app.schemas.goals import CandidateTasksOut, WeekGoalCreate, WeekGoalOut, WeekGoalPatch
from app.services import goals as service

router = APIRouter(tags=["goals"])


@router.get("/goals/weeks/{week}", response_model=WeekGoalOut)
def get_week_goal(
    week: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> WeekGoalOut:
    return service.get_week_goal(db, user_id=user_id, week=week)


@router.post("/goals/weeks/{week}", response_model=WeekGoalOut)
def create_week_goal(
    week: str,
    payload: WeekGoalCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> WeekGoalOut:
    return service.create_week_goal(db, user_id=user_id, week=week, payload=payload)


@router.patch("/goals/{goal_id}", response_model=WeekGoalOut)
def update_goal(
    goal_id: int,
    payload: WeekGoalPatch,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> WeekGoalOut:
    return service.update_goal(db, user_id=user_id, goal_id=goal_id, payload=payload)


@router.get("/goals/{goal_id}/candidate-tasks", response_model=CandidateTasksOut)
def get_candidates(
    goal_id: int,
    limit: int = Query(default=20),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> CandidateTasksOut:
    return service.candidate_tasks(db, user_id=user_id, goal_id=goal_id, limit=limit)
