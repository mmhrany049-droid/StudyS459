"""Analytics response schemas (spec 14: progress + analytics)."""

from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.tests import TopicRef


class BookProgressOut(BaseModel):
    book_id: int
    title: str
    active: bool
    volume: int
    correct: int
    wrong: int
    unanswered: int
    pending: int
    accuracy: float | None
    coverage: float | None
    last_activity: datetime | None


class OverviewOut(BaseModel):
    user_id: int
    sessions_total: int
    sessions_completed: int
    volume: int
    correct: int
    wrong: int
    unanswered: int
    pending: int
    accuracy: float | None
    coverage: float | None
    books: list[BookProgressOut]


class TopicRowOut(BaseModel):
    node_id: int
    book_id: int
    parent_id: int | None
    node_type: str
    title: str
    code: str
    depth: int
    path: str
    is_leaf: bool
    total: int
    attempted: int
    volume: int
    correct: int
    wrong: int
    unanswered: int
    pending: int
    coverage: float | None
    accuracy: float | None
    last_activity: datetime | None
    last_parity: str | None


class BookTopicsOut(BaseModel):
    book_id: int
    topics: list[TopicRowOut]


class NodeProgressOut(BaseModel):
    node: TopicRowOut
    children: list[TopicRowOut]


class QuestionAttemptOut(BaseModel):
    session_id: int
    answer: str | None
    result: str | None
    answered_at: datetime
    response_time_seconds: int | None


class QuestionHistoryOut(BaseModel):
    question_id: int
    book_id: int
    test_set_id: int
    test_set_title: str
    sequence_no: int
    difficulty: str | None
    has_answer_key: bool
    topics: list[TopicRef]
    sessions_count: int
    attempt_count: int
    correct: int
    wrong: int
    unanswered: int
    pending: int
    last_answer: str | None
    last_result: str | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    attempts: list[QuestionAttemptOut]


class TrendPointOut(BaseModel):
    period_start: date
    sessions: int
    volume: int
    correct: int
    wrong: int
    unanswered: int
    accuracy: float | None


class TrendsOut(BaseModel):
    group_by: str
    days: int
    points: list[TrendPointOut]


class WeaknessOut(BaseModel):
    node_id: int
    book_id: int
    title: str
    path: str
    node_type: str
    is_leaf: bool
    volume: int
    correct: int
    wrong: int
    unanswered: int
    error_rate: float | None
    last_activity: datetime | None
    last_parity: str | None
    score: float


class WeaknessesOut(BaseModel):
    items: list[WeaknessOut]
