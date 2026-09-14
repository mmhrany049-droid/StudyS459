"""Academic request/response schemas (spec 14 academic + exams sections)."""

from datetime import date as Date, datetime, time  # Date: fields named `date` can't self-annotate
from typing import Any, Literal

from pydantic import BaseModel, Field

ScheduleType = Literal["school", "external"]
HomeworkSource = Literal["school", "external", "manual"]
HomeworkStatus = Literal["pending", "done", "cancelled"]
ExamQuestionResult = Literal["correct", "wrong", "unanswered"]


class ScheduleCreate(BaseModel):
    schedule_type: ScheduleType
    title: str = Field(min_length=1, max_length=256)
    day_of_week: int = Field(ge=0, le=6)  # Monday=0..Sunday=6
    start_time: time
    end_time: time
    recurring: bool = True
    date: Date | None = None  # one-offs only (recurring=false)
    subject_id: int | None = None
    node_id: int | None = None
    source: str | None = Field(default=None, max_length=32)


class ScheduleOut(BaseModel):
    id: int
    schedule_type: ScheduleType
    title: str
    day_of_week: int
    start_time: time
    end_time: time
    recurring: bool
    date: Date | None
    subject_id: int | None
    node_id: int | None
    source: str | None
    duration_minutes: int


class ClassSessionCreate(BaseModel):
    schedule_id: int | None = None
    date: Date
    subject_id: int
    attended: bool = True
    notes: str | None = None


class ClassSessionOut(BaseModel):
    id: int
    schedule_id: int | None
    date: Date
    subject_id: int
    subject_name: str
    attended: bool
    notes: str | None


class TaughtLessonCreate(BaseModel):
    class_session_id: int | None = None
    subject_id: int
    node_id: int | None = None
    taught_at: datetime
    duration_minutes: int = 0
    notes: str | None = None


class TaughtLessonOut(BaseModel):
    id: int
    class_session_id: int | None
    subject_id: int
    subject_name: str
    node_id: int | None
    node_title: str | None
    taught_at: datetime
    duration_minutes: int
    notes: str | None


class HomeworkCreate(BaseModel):
    source_type: HomeworkSource = "manual"
    title: str = Field(min_length=1, max_length=256)
    subject_id: int
    node_id: int | None = None
    due_at: datetime
    estimated_minutes: int = 0
    priority: float = 0.5
    create_task: bool = False


class HomeworkPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    node_id: int | None = None
    due_at: datetime | None = None
    estimated_minutes: int | None = None
    priority: float | None = None
    status: HomeworkStatus | None = None


class HomeworkOut(BaseModel):
    id: int
    source_type: HomeworkSource
    title: str
    subject_id: int
    subject_name: str
    node_id: int | None
    node_title: str | None
    due_at: datetime
    estimated_minutes: int
    priority: float
    status: HomeworkStatus
    task_id: int | None  # linked planner task, if any


class ExamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    exam_type: str = Field(default="custom", max_length=32)
    provider: str | None = Field(default=None, max_length=128)
    exam_date: Date
    total_questions: int | None = None
    total_score: float | None = None
    images_metadata: dict[str, Any] | None = None


class ExamQuestionIn(BaseModel):
    sequence_no: int = Field(ge=1)
    question_id: int | None = None
    topic_node_id: int | None = None
    answer_key: str | None = Field(default=None, max_length=8)
    user_answer: str | None = Field(default=None, max_length=8)
    result: ExamQuestionResult | None = None


class ExamQuestionsIn(BaseModel):
    questions: list[ExamQuestionIn] = Field(min_length=1)


class ExamQuestionOut(BaseModel):
    sequence_no: int
    question_id: int | None
    topic_node_id: int | None
    answer_key: str | None
    user_answer: str | None
    result: ExamQuestionResult | None


class ExamOut(BaseModel):
    id: int
    title: str
    exam_type: str
    provider: str | None
    exam_date: Date
    total_questions: int | None
    total_score: float | None
    images_metadata: dict[str, Any] | None
    questions: list[ExamQuestionOut]


class ExamSubjectRowOut(BaseModel):
    subject_id: int
    subject_name: str
    correct: int
    wrong: int
    unanswered: int


class ExamAnalyticsOut(BaseModel):
    exam_id: int
    correct: int
    wrong: int
    unanswered: int
    ungraded: int  # result is NULL
    unmapped: int  # graded but no subject resolvable
    subjects: list[ExamSubjectRowOut]
