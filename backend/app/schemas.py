from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

Choice = Literal[1, 2, 3, 4]


# ---------------- Question bank (V2.2 / سند 02) ----------------
class RangeCreate(BaseModel):
    from_no: int = Field(ge=1, alias="from")
    to_no: int = Field(ge=1, alias="to")
    difficulty_level: int | None = None
    question_tag: str | None = None

    model_config = {"populate_by_name": True}


class AnswerKeyItem(BaseModel):
    sequence_no: int
    answer_key: int | None = None
    difficulty_level: int | None = None
    question_tag: str | None = None


class BulkAnswerKey(BaseModel):
    items: list[AnswerKeyItem] = []
    compact: str | None = None  # "1:2, 2:3, 3:1"


class QuestionPatch(BaseModel):
    answer_key: int | None = None
    difficulty_level: int | None = None
    question_tag: str | None = None
    archived: bool | None = None


# ---------------- Past import (سند 03) ----------------
class ImportAnswer(BaseModel):
    """سند ۰۹: هر پاسخ با question_id یا sequence_ref مشخص می‌شود."""
    question_id: int | None = None
    # sequence_ref: شماره سوال؛ همراه node_id یکتا می‌شود
    sequence_ref: int | None = None
    node_id: int | None = None
    choice: int | None = None       # None = نزده
    uncertain: bool = False         # S13


class ImportByBook(BaseModel):
    book_id: int
    session_date: date | None = None
    answers: list[ImportAnswer]
    notes: str = ""


# ---------------- Taught topics (سند 04) ----------------
class TaughtTopicIn(BaseModel):
    node_id: int
    taught_at: date | None = None
    source_type: str = "school"
    source_id: int | None = None
    notes: str = ""


# ---------------- Exams (سند 05/06) ----------------
class ExamIn(BaseModel):
    title: str
    exam_kind: Literal["school", "mock", "other"] = "school"
    exam_type: str = "مدرسه‌ای"
    provider: str = ""
    subject_id: int | None = None
    exam_date: date | None = None
    total_questions: int = 0
    notes: str = ""


class ExamAnswerKeyIn(BaseModel):
    items: list[AnswerKeyItem] = []
    compact: str | None = None


class ExamAttemptAnswerIn(BaseModel):
    sequence_no: int
    user_answer: int | None = None


class ExamAttemptIn(BaseModel):
    label: str = ""
    attempted_at: date | None = None
    duration_minutes: int = Field(default=0, ge=0)
    notes: str = ""
    answers: list[ExamAttemptAnswerIn] = []


class ExamSectionIn(BaseModel):
    subject_id: int
    sequence_from: int
    sequence_to: int
    duration_minutes: int | None = None


class ExamSectionsIn(BaseModel):
    sections: list[ExamSectionIn]


class TopicMapItem(BaseModel):
    sequence_from: int
    sequence_to: int
    node_id: int


class ExamTopicMapIn(BaseModel):
    items: list[TopicMapItem]


# ---------------- Readiness (سند 07) ----------------
class UpcomingExamIn(BaseModel):
    title: str
    exam_date: date
    node_ids: list[int] = []
    notes: str = ""


# ---------------- Tasks / planning ----------------
class TaskIn(BaseModel):
    title: str
    task_type: str = "test"
    subject_id: int | None = None
    book_id: int | None = None
    node_id: int | None = None
    quantity: int = 10
    estimated_minutes: int = 30
    parity: str = "any"
    priority: int = 50
    planned_date: date | None = None
    planned_time: str | None = None
    due_at: date | None = None
    source_type: str = "manual"
    source_id: int | None = None
    recommendation_reason: str = ""
    evidence_json: dict[str, Any] = {}


class TaskPatch(BaseModel):
    title: str | None = None
    quantity: int | None = None
    estimated_minutes: int | None = None
    priority: int | None = None
    planned_date: date | None = None
    planned_time: str | None = None
    status: str | None = None
    parity: str | None = None
    override_reason: str | None = None


class TaskMove(BaseModel):
    planned_date: date
    override_reason: str | None = None


class TaskSplit(BaseModel):
    parts: int = Field(default=2, ge=2, le=6)


# ---------------- Test engine ----------------
class SessionCreate(BaseModel):
    node_id: int
    count: int = Field(ge=1)
    sequence_from: int | None = None
    sequence_to: int | None = None
    parity: Literal["odd", "even", "any"] = "any"
    timed: bool = False
    time_limit_seconds: int | None = None
    task_id: int | None = None


class AnswerIn(BaseModel):
    question_id: int
    answer: int | None = None
    response_time_seconds: int | None = None


class FinishIn(BaseModel):
    answers: list[AnswerIn] = []
    actual_duration_minutes: int | None = None


# ---------------- State / interview / drafts ----------------
class StateCheckIn(BaseModel):
    energy: float = 0.5
    focus: float = 0.5
    motivation: float = 0.5
    stress: float = 0.5
    fatigue: float = 0.5
    sleep_hours: float | None = None


class InterviewAnswers(BaseModel):
    week_start: date | None = None
    answers: dict[str, Any] = {}
    complete: bool = False


class OnboardingAnswerIn(BaseModel):
    question_code: str
    answer_value: str


class DraftIn(BaseModel):
    scope: str
    payload: dict[str, Any]


class WakeUpIn(BaseModel):
    time: str | None = None        # "06:40"
    day: date | None = None        # پیش‌فرض: امروز
