"""
مدل داده SS459 — نسخه ۲.۲
V1 core (users/books/nodes/questions/sessions/attempts/tasks/goals/rewards)
+ V2 (import, wake-up, jalali/classes, review)
+ V2.1 (profile, behavior, state, interview, task planning metadata)
+ V2.2 (question bank, taught topics, exams+files+attempts, mock map, readiness)
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.utcnow()


# =====================================================================
# Core — V1
# =====================================================================
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    grade: Mapped[str] = mapped_column(String(32), default="یازدهم")
    track: Mapped[str] = mapped_column(String(32), default="ریاضی")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tehran")
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_streak_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    season_mode: Mapped[str] = mapped_column(String(16), default="school_term")
    sleep_hour: Mapped[int] = mapped_column(Integer, default=23)
    sleep_minute: Mapped[int] = mapped_column(Integer, default=30)
    auto_time_adjust: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    grade: Mapped[str] = mapped_column(String(32), default="یازدهم")
    track: Mapped[str] = mapped_column(String(32), default="ریاضی")
    color: Mapped[str] = mapped_column(String(16), default="#6366f1")


class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(primary_key=True)
    stable_key: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    publisher: Mapped[str] = mapped_column(String(80), default="")
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    grade: Mapped[str] = mapped_column(String(32), default="یازدهم")
    track: Mapped[str] = mapped_column(String(32), default="ریاضی")
    edition: Mapped[str] = mapped_column(String(32), default="")
    config_version: Mapped[str] = mapped_column(String(16), default="2.2")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    has_difficulty_levels: Mapped[bool] = mapped_column(Boolean, default=False)

    subject: Mapped[Subject] = relationship()


class BookNode(Base):
    """درخت کتاب: chapter / lesson / section / leaf"""
    __tablename__ = "book_nodes"
    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True)
    node_type: Mapped[str] = mapped_column(String(32), default="section")
    title: Mapped[str] = mapped_column(String(400))
    code: Mapped[str] = mapped_column(String(64), default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    book: Mapped[Book] = relationship()
    children: Mapped[list["BookNode"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped["BookNode"] = relationship(back_populates="children", remote_side=[id])


Index("ix_nodes_book", BookNode.book_id, BookNode.parent_id)


class TestSet(Base):
    __tablename__ = "test_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    node_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    test_type: Mapped[str] = mapped_column(String(32), default="normal")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Question(Base):
    """
    V2.2: answer_key می‌تواند null باشد (ورود تدریجی پاسخ‌نامه).
    حذف سوال دارای history فقط soft (archived=True) — S9.
    """
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    test_set_id: Mapped[int] = mapped_column(ForeignKey("test_sets.id"))
    stable_key: Mapped[str] = mapped_column(String(120), unique=True)
    sequence_no: Mapped[int] = mapped_column(Integer)
    difficulty_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1/2/3
    answer_type: Mapped[str] = mapped_column(String(16), default="four_choice")
    answer_key: Mapped[int | None] = mapped_column(Integer, nullable=True)        # 1..4
    question_tag: Mapped[str | None] = mapped_column(String(32), nullable=True)   # S7
    archived: Mapped[bool] = mapped_column(Boolean, default=False)                # S9
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (UniqueConstraint("test_set_id", "sequence_no", name="uq_set_seq"),)


class QuestionTopicMap(Base):
    __tablename__ = "question_topic_map"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    node_id: Mapped[int] = mapped_column(ForeignKey("book_nodes.id"))
    __table_args__ = (UniqueConstraint("question_id", "node_id", name="uq_q_node"),)


class NodeParityState(Base):
    __tablename__ = "node_parity_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    node_id: Mapped[int] = mapped_column(ForeignKey("book_nodes.id"))
    last_parity: Mapped[str] = mapped_column(String(8), default="odd")
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("user_id", "node_id", name="uq_user_node_parity"),)


class TestSession(Base):
    __tablename__ = "test_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    node_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True)
    session_kind: Mapped[str] = mapped_column(String(16), default="normal")  # normal|review|import
    timed: Mapped[bool] = mapped_column(Boolean, default=False)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parity: Mapped[str] = mapped_column(String(8), default="any")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_date: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    is_imported: Mapped[bool] = mapped_column(Boolean, default=False)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_time_adjust_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)


class TestSessionQuestion(Base):
    __tablename__ = "test_session_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class QuestionAttempt(Base):
    """append-only — هرگز overwrite نشود."""
    __tablename__ = "question_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    answer: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..4 یا None=نزده
    result: Mapped[str] = mapped_column(String(16))  # correct|wrong|unanswered
    is_imported: Mapped[bool] = mapped_column(Boolean, default=False)
    uncertain: Mapped[bool] = mapped_column(Boolean, default=False)     # S13 «شک دارم»
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    response_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)


Index("ix_attempt_q", QuestionAttempt.question_id, QuestionAttempt.user_id)


class ReviewQueue(Base):
    __tablename__ = "review_queue"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    reason: Mapped[str] = mapped_column(String(24))  # wrong|unanswered
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    unanswered_count: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    scheduled_for: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_review_q"),)


# =====================================================================
# Planning — V1/V2/V2.1
# =====================================================================
class WeeklyGoal(Base):
    __tablename__ = "weekly_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    week_start: Mapped[date] = mapped_column(Date)
    week_end: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class WeeklyGoalItem(Base):
    __tablename__ = "weekly_goal_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("weekly_goals.id"))
    goal_type: Mapped[str] = mapped_column(String(16))  # count|topic
    target_value: Mapped[int] = mapped_column(Integer, default=0)
    progress_value: Mapped[int] = mapped_column(Integer, default=0)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True)
    node_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_type: Mapped[str] = mapped_column(String(24), default="test")  # test|review|study|exam_prep
    title: Mapped[str] = mapped_column(String(300))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True)
    node_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(24), default="manual")  # manual|planner|imported|recurring
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    quantity: Mapped[int] = mapped_column(Integer, default=10)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30)
    parity: Mapped[str] = mapped_column(String(8), default="any")
    planned_date: Mapped[date] = mapped_column(Date, default=date.today)
    planned_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|completed|skipped
    recommendation_reason: Mapped[str] = mapped_column(Text, default="")
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    planner_version: Mapped[str] = mapped_column(String(16), default="2.2")
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    schedule_type: Mapped[str] = mapped_column(String(24), default="external_class")
    title: Mapped[str] = mapped_column(String(160))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=شنبه
    start_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    recurring: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")


class SchoolDayOverride(Base):
    __tablename__ = "school_day_overrides"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date)
    is_school_day: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(200), default="")
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_override_date"),)


# =====================================================================
# Reward — V1/V2
# =====================================================================
class RewardEvent(Base):
    __tablename__ = "reward_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(48))
    points: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(300), default="")
    related_entity_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    event_date: Mapped[date] = mapped_column(Date, default=date.today)


class WakeUpEvent(Base):
    __tablename__ = "wake_up_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    recorded_time: Mapped[str] = mapped_column(String(8), default="07:00")
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_wakeup_day"),)


class Badge(Base):
    __tablename__ = "badges"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(300), default="")
    condition_type: Mapped[str] = mapped_column(String(48), default="manual")
    condition_value: Mapped[int] = mapped_column(Integer, default=0)


class UserBadge(Base):
    __tablename__ = "user_badges"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    badge_id: Mapped[int] = mapped_column(ForeignKey("badges.id"))
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)


# =====================================================================
# V2.1 — Behavioral Intelligence Layer
# =====================================================================
class UserProfile(Base):
    __tablename__ = "user_profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    personality_json: Mapped[dict] = mapped_column(JSON, default=dict)
    preferences_json: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[str] = mapped_column(String(16), default="2.1")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class BehaviorEvent(Base):
    __tablename__ = "behavior_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(48))
    event_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(24), default="app")


class UserStateSnapshot(Base):
    __tablename__ = "user_state_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    energy: Mapped[float] = mapped_column(Float, default=0.5)
    focus: Mapped[float] = mapped_column(Float, default=0.5)
    motivation: Mapped[float] = mapped_column(Float, default=0.5)
    stress: Mapped[float] = mapped_column(Float, default=0.5)
    fatigue: Mapped[float] = mapped_column(Float, default=0.5)
    readiness: Mapped[float] = mapped_column(Float, default=0.5)
    confidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(24), default="self_report")


class OnboardingAnswer(Base):
    __tablename__ = "onboarding_answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    question_code: Mapped[str] = mapped_column(String(48))
    answer_value: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PlanningInterview(Base):
    __tablename__ = "planning_interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    week_start: Mapped[date] = mapped_column(Date)
    answers_json: Mapped[dict] = mapped_column(JSON, default=dict)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    model_version: Mapped[str] = mapped_column(String(16), default="2.1")
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_interview_week"),)


# =====================================================================
# V2.2 — Taught topics
# =====================================================================
class TaughtTopic(Base):
    __tablename__ = "taught_topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    node_id: Mapped[int] = mapped_column(ForeignKey("book_nodes.id"))
    taught_at: Mapped[date] = mapped_column(Date, default=date.today)
    source_type: Mapped[str] = mapped_column(String(32), default="school")  # school|external_class|other
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# =====================================================================
# V2.2 — Exams
# =====================================================================
class Exam(Base):
    __tablename__ = "exams"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    exam_kind: Mapped[str] = mapped_column(String(16), default="school")  # school|mock|other
    exam_type: Mapped[str] = mapped_column(String(32), default="مدرسه‌ای")
    provider: Mapped[str] = mapped_column(String(80), default="")
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    exam_date: Mapped[date] = mapped_column(Date, default=date.today)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ExamFile(Base):
    __tablename__ = "exam_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    file_path: Mapped[str] = mapped_column(String(400))
    original_name: Mapped[str] = mapped_column(String(300), default="")
    file_type: Mapped[str] = mapped_column(String(16), default="pdf")  # pdf|image
    file_kind: Mapped[str] = mapped_column(String(24), default="exam_paper")  # S8
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ExamAnswerKey(Base):
    __tablename__ = "exam_answer_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    sequence_no: Mapped[int] = mapped_column(Integer)
    answer_key: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("exam_id", "sequence_no", name="uq_exam_key_seq"),)


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    label: Mapped[str] = mapped_column(String(120), default="")
    attempted_at: Mapped[date] = mapped_column(Date, default=date.today)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    unanswered_count: Mapped[int] = mapped_column(Integer, default=0)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ExamAttemptAnswer(Base):
    __tablename__ = "exam_attempt_answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id"))
    sequence_no: Mapped[int] = mapped_column(Integer)
    user_answer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(String(16), default="unanswered")


class ExamSubjectSection(Base):
    """آزمون آزمایشی چنددرسه: بازه شماره سوال ← درس"""
    __tablename__ = "exam_subject_sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    sequence_from: Mapped[int] = mapped_column(Integer)
    sequence_to: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ExamQuestionTopicMap(Base):
    __tablename__ = "exam_question_topic_map"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    sequence_no: Mapped[int] = mapped_column(Integer)
    node_id: Mapped[int] = mapped_column(ForeignKey("book_nodes.id"))
    __table_args__ = (UniqueConstraint("exam_id", "sequence_no", name="uq_exam_topic_seq"),)


# =====================================================================
# V2.2 — Exam readiness
# =====================================================================
class UpcomingExam(Base):
    __tablename__ = "upcoming_exams"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    exam_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class UpcomingExamTopic(Base):
    __tablename__ = "upcoming_exam_topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    upcoming_exam_id: Mapped[int] = mapped_column(ForeignKey("upcoming_exams.id"))
    node_id: Mapped[int] = mapped_column(ForeignKey("book_nodes.id"))
    __table_args__ = (UniqueConstraint("upcoming_exam_id", "node_id", name="uq_upcoming_node"),)


# =====================================================================
# V2.2 — Draft autosave (S2)
# =====================================================================
class AnswerDraft(Base):
    __tablename__ = "answer_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    scope: Mapped[str] = mapped_column(String(48))     # import_book:3 / exam_attempt:9 / bank:12
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    __table_args__ = (UniqueConstraint("user_id", "scope", name="uq_draft_scope"),)
