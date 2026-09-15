"""Test Engine request/response schemas (spec 14)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    node_id: int
    count: int = Field(ge=1)
    sequence_from: int | None = Field(default=None, ge=1)
    sequence_to: int | None = Field(default=None, ge=1)
    parity: Literal["odd", "even", "any"] = "any"
    timed: bool = False
    time_limit_seconds: int | None = Field(default=None, ge=1)
    task_id: int | None = None


class AnswerItem(BaseModel):
    question_id: int
    answer: str | None = Field(default=None, min_length=1)
    response_time_seconds: int | None = Field(default=None, ge=0)
    client_attempt_id: UUID


class AnswersIn(BaseModel):
    answers: list[AnswerItem] = Field(min_length=1)


class RecordedAttempt(BaseModel):
    question_id: int
    attempt_id: int
    duplicate: bool


class AnswersOut(BaseModel):
    attempts: list[RecordedAttempt]


class CorrectionItem(BaseModel):
    question_id: int
    result: Literal["correct", "wrong"]


class CorrectionsIn(BaseModel):
    corrections: list[CorrectionItem] = Field(min_length=1)


class CorrectionOut(BaseModel):
    session_id: int
    status: str
    pending_remaining: int


class TopicRef(BaseModel):
    node_id: int
    title: str


class SessionQuestionOut(BaseModel):
    question_id: int
    display_order: int
    sequence_no: int
    test_set_id: int
    test_set_title: str
    difficulty: str | None
    topics: list[TopicRef]
    answer: str | None
    result: str | None
    response_time_seconds: int | None
    has_answer_key: bool


class TopicBreakdown(BaseModel):
    node_id: int
    title: str
    total: int
    correct: int
    wrong: int
    unanswered: int
    pending: int


class DifficultyBreakdown(BaseModel):
    difficulty: str | None
    total: int
    correct: int
    wrong: int
    unanswered: int
    pending: int


class ResultOut(BaseModel):
    status: str
    total: int
    correct: int
    wrong: int
    unanswered: int
    pending: int
    points_earned: int | None = None  # set only by the finish call itself
    accuracy: float | None
    duration_seconds: int | None
    average_response_time_seconds: float | None
    topic_breakdown: list[TopicBreakdown]
    difficulty_breakdown: list[DifficultyBreakdown]
    parity: str
    sequence_from: int | None
    sequence_to: int | None
    timed: bool
    time_limit_seconds: int | None
    started_at: datetime
    ended_at: datetime | None


class SessionOut(BaseModel):
    id: int
    user_id: int
    task_id: int | None
    timed: bool
    time_limit_seconds: int | None
    sequence_from: int | None
    sequence_to: int | None
    parity: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    remaining_seconds: int | None
    expired: bool


class SessionView(BaseModel):
    session: SessionOut
    questions: list[SessionQuestionOut]
    result: ResultOut | None


class ParityStateOut(BaseModel):
    node_id: int
    last_parity: str | None
    last_used_at: datetime | None
    suggested_parity: str | None
