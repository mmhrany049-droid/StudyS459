"""Planner request/response schemas (spec 14 planner section)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal["test", "review", "study"]
TaskSource = Literal["goal", "review", "weakness", "manual", "homework", "exam"]
TaskStatus = Literal["planned", "in_progress", "completed", "cancelled"]


class TaskCreate(BaseModel):
    task_type: TaskType
    title: str = Field(min_length=1, max_length=256)
    source_type: TaskSource = "manual"
    source_id: int | None = None
    node_id: int | None = None
    question_count: int | None = None
    sequence_from: int | None = None
    sequence_to: int | None = None
    parity: Literal["odd", "even", "any"] | None = None
    priority: float = 0.5
    estimated_minutes: int = 0
    due_at: datetime | None = None
    recommendation_reason: str | None = None


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    status: TaskStatus | None = None
    priority: float | None = None
    estimated_minutes: int | None = None
    due_at: datetime | None = None
    recommendation_reason: str | None = None


class TaskOut(BaseModel):
    id: int
    task_type: TaskType
    title: str
    source_type: TaskSource
    source_id: int | None
    node_id: int | None
    question_count: int | None
    sequence_from: int | None
    sequence_to: int | None
    parity: str | None
    priority: float
    estimated_minutes: int
    due_at: datetime | None
    status: TaskStatus
    is_overdue: bool
    recommendation_reason: str | None
    created_at: datetime
    completed_at: datetime | None
    placed_on: date | None


class PlacedTaskOut(BaseModel):
    position: int
    task: TaskOut


class WorkloadRowOut(BaseModel):
    task_id: int
    title: str
    estimated_minutes: int


class DayPlanOut(BaseModel):
    date: date
    weekday: int  # Monday=0..Sunday=6
    is_school_day: bool
    override: bool  # an explicit override set this day's kind
    capacity_minutes: int
    workload_minutes: int
    over_capacity: bool
    workload: list[WorkloadRowOut]
    placements: list[PlacedTaskOut]


class WeekPlanOut(BaseModel):
    week_start: date
    week_end: date
    days: list[DayPlanOut]
    unplaced: list[TaskOut]  # open tasks with no placement
    catch_up: list[TaskOut]  # open tasks, catch-up priority order


class PlacementIn(BaseModel):
    task_id: int
    date: date
    position: int = 0


class PlacementsPut(BaseModel):
    placements: list[PlacementIn]
    # Extra dates to replace wholesale (e.g. to clear a day: no rows for it).
    dates: list[date] = []


class OverrideIn(BaseModel):
    date: date
    is_school_day: bool
    reason: str | None = Field(default=None, max_length=256)


class OverrideOut(BaseModel):
    date: date
    is_school_day: bool
    reason: str | None
