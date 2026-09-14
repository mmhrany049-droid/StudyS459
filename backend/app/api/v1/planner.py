"""Planner routes (spec 14). Routes only."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db import get_db
from app.errors import AppError
from app.schemas.planner import (
    DayPlanOut,
    OverrideIn,
    OverrideOut,
    PlacementsPut,
    TaskCreate,
    TaskOut,
    TaskPatch,
    WeekPlanOut,
)
from app.services import planner as service

router = APIRouter(tags=["planner"])


@router.post("/tasks", response_model=TaskOut)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TaskOut:
    return service.create_task(db, user_id=user_id, payload=payload)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def patch_task(
    task_id: int,
    payload: TaskPatch,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TaskOut:
    return service.patch_task(db, user_id=user_id, task_id=task_id, payload=payload)


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TaskOut:
    return service.complete_task(db, user_id=user_id, task_id=task_id)


@router.put("/planner/placements", response_model=list[DayPlanOut])
def put_placements(
    payload: PlacementsPut,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[DayPlanOut]:
    return service.put_placements(
        db, user_id=user_id, items=payload.placements, extra_dates=payload.dates)


@router.get("/planner/day/{day}", response_model=DayPlanOut)
def get_day(
    day: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> DayPlanOut:
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise AppError("invalid_date", "قالب تاریخ باید YYYY-MM-DD باشد.", status_code=422)
    return service.day_plan(db, user_id=user_id, day=parsed)


@router.get("/planner/week/{week}", response_model=WeekPlanOut)
def get_week(
    week: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> WeekPlanOut:
    return service.week_plan(db, user_id=user_id, week=week)


# Owned by capacity (Phase 5); lives with Academic in the contract.
@router.post("/school-day-overrides", response_model=OverrideOut)
def set_override(
    payload: OverrideIn,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> OverrideOut:
    return service.set_override(db, user_id=user_id, payload=payload)
