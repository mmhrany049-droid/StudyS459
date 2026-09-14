"""Goal request/response schemas (spec 14 goals section)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

GoalType = Literal["count", "topic"]
CandidateKind = Literal["test", "review"]


class GoalItemIn(BaseModel):
    goal_type: GoalType
    target_value: float
    subject_id: int | None = None
    book_id: int | None = None
    node_id: int | None = None


class WeekGoalCreate(BaseModel):
    items: list[GoalItemIn] = Field(min_length=1)
    active: bool = True


class WeekGoalPatch(BaseModel):
    items: list[GoalItemIn] | None = Field(default=None, min_length=1)
    active: bool | None = None


class ItemProgressOut(BaseModel):
    volume: int  # finalized instances in the week within scope
    attempted: int  # distinct questions seen in the week within scope
    pool_total: int
    coverage: float | None
    target: float  # count: questions; topic: coverage fraction
    remaining: float  # count: questions left; topic: questions left to target
    done: bool


class GoalItemOut(BaseModel):
    id: int
    goal_type: GoalType
    target_value: float
    subject_id: int | None
    book_id: int | None
    node_id: int | None
    title: str  # resolved scope label
    progress: ItemProgressOut


class WeekGoalOut(BaseModel):
    id: int
    week_start: date  # Saturday
    week_end: date  # Friday
    active: bool
    items: list[GoalItemOut]
    sessions_in_week: int
    week_volume_unique: int  # every instance counted ONCE (no double-count)
    week_attempted_unique: int


class CandidateTaskOut(BaseModel):
    kind: CandidateKind
    sources: list[str]  # goal_topic | goal_count | weakness | review
    source_item_ids: list[int]
    node_id: int
    book_id: int
    title: str
    path: str
    suggested_count: int
    suggested_parity: Literal["odd", "even", "any"]
    priority_score: float
    recommendation_reason: str
    pool_total: int
    remaining_never: int
    remaining_week: int
    volume_week: int
    weakness_score: float


class CandidateTasksOut(BaseModel):
    goal_id: int
    items: list[CandidateTaskOut]
