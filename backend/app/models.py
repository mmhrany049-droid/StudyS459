"""مدل‌های دیتابیس SS459 — نسخه ۲.۱

بر اساس:
- 04_DATABASE_SPEC_V1.md
- 10_DATABASE_DELTA_V2.md
- 24_DATABASE_DELTA_V2_1.md
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


# ------------------------------- Core ---------------------------------------

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    grade: Mapped[str] = mapped_column(String(32), default="11")
    track: Mapped[str] = mapped_column(String(32), default="mathematics")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tehran")
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    grade: Mapped[str] = mapped_column(String(16), default="11")
    track: Mapped[str] = mapped_column(String(32), default="mathematics")
    type: Mapped[str] = mapped_column(String(32), default="specialized")


class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(primary_key=True)
    stable_key: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(128))
    publisher: Mapped[str] = mapped_column(String(64), default="")
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    grade: Mapped[str] = mapped_column(String(16), default="11")
    track: Mapped[str] = mapped_column(String(32), default="mathematics")
    edition: Mapped[str] = mapped_column(String(32), default="")
    config_version: Mapped[str] = mapped_column(String(16), default="1")


class UserBookActivation(Base):
    __tablename__ = "user_book_activations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    activated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    __table_args__ = (UniqueConstraint("user_id", "book_id"),)


class BookNode(Base):
    __tablename__ = "book_nodes"
    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True)
    node_type: Mapped[str] = mapped_column(String(32))  # chapter/lesson/section/title/subsection/leaf
    title: Mapped[str] = mapped_column(String(256))
    code: Mapped[str] = mapped_column(String(64), default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class TestSet(Base):
    __tablename__ = "test_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    test_type: Mapped[str] = mapped_column(String(32), default="normal")
    node_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    stable_key: Mapped[str] = mapped_column(String(96), unique=True)
    test_set_id: Mapped[int] = mapped_column(ForeignKey("test_sets.id"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer)
    difficulty_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..3
    answer_type: Mapped[str] = mapped_column(String(16), default="multi_choice")
    answer_key: Mapped[str] = mapped_column(String(8), default="1")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class QuestionTopicMap(Base):
    __tablename__ = "question_topic_map"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("book_nodes.id"), index=True)
    __table_args__ = (UniqueConstraint("question_id", "node_id"),)


class NodeParityState(Base):
    __tablename__ = "node_parity_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    node_id: Mapped[int] = mapped_column(ForeignKey("book_nodes.id"))
    last_parity: Mapped[str] = mapped_column(String(8))  # odd/even
    last_used_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    __table_args__ = (UniqueConstraint("user_id", "node_id"),)


# ------------------------------- Test ---------------------------------------

class TestSession(Base):
    __tablename__ = "test_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    session_type: Mapped[str] = mapped_column(String(16), default="normal")  # normal/review/imported
    timed: Mapped[bool] = mapped_column(Boolean, default=False)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parity: Mapped[str] = mapped_column(String(8), default="any")
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress/completed
    # ---- V2 delta ----
    is_imported: Mapped[bool] = mapped_column(Boolean, default=False)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_time_adjust_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    session_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    review_queue_snapshot: Mapped[list] = mapped_column(JSON, default=list)


class TestSessionQuestion(Base):
    __tablename__ = "test_session_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    display_order: Mapped[int] = mapped_column(Integer)


class QuestionAttempt(Base):
    """append-only — هرگز overwrite نمی‌شود."""
    __tablename__ = "question_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    answer: Mapped[str | None] = mapped_column(String(16), nullable=True)
    result: Mapped[str] = mapped_column(String(16))  # correct/wrong/unanswered
    answered_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    response_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (Index("ix_attempts_session_question", "session_id", "question_id"),)


# ------------------------------- Planning -----------------------------------

class WeeklyGoal(Base):
    __tablename__ = "weekly_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    week_start: Mapped[dt.date] = mapped_column(Date, index=True)
    week_end: Mapped[dt.date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class WeeklyGoalItem(Base):
    __tablename__ = "weekly_goal_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("weekly_goals.id"), index=True)
    goal_type: Mapped[str] = mapped_column(String(16))  # count | topic
    target_value: Mapped[int] = mapped_column(Integer)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True)
    node_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(24), default="test")  # test/study/review
    title: Mapped[str] = mapped_column(String(256))
    source_type: Mapped[str] = mapped_column(String(24), default="manual")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_at: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="planned")  # planned/in_progress/completed/cancelled
    recommendation_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc)
    # جزئیات تست
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True)
    node_id: Mapped[int | None] = mapped_column(ForeignKey("book_nodes.id"), nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=20)
    parity: Mapped[str | None] = mapped_column(String(8), nullable=True)
    timed: Mapped[bool] = mapped_column(Boolean, default=False)
    # ---- V2.1: task_planning_metadata ----
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual/planner/imported/recurring
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    planner_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(16), default="user")
    updated_by: Mapped[str] = mapped_column(String(16), default="user")


class DailyTaskPlacement(Base):
    __tablename__ = "daily_task_placements"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


# ------------------------------- Academic -----------------------------------

class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    schedule_type: Mapped[str] = mapped_column(String(24), default="external_class")  # school/external_class
    title: Mapped[str] = mapped_column(String(128))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)  # شنبه=0 ... جمعه=6
    start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    recurring: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(32), default="user")  # default_seed_v2 | user
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)


class SchoolDayOverride(Base):
    __tablename__ = "school_day_overrides"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    is_school_day: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)


# ------------------------------- Review -------------------------------------

class ReviewQueueItem(Base):
    __tablename__ = "review_queue"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(16), default="question")
    entity_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    reason: Mapped[str] = mapped_column(String(64), default="wrong")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_for: Mapped[dt.date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/resolved
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    last_result: Mapped[str | None] = mapped_column(String(16), nullable=True)


# ------------------------------- Rewards ------------------------------------

class RewardEvent(Base):
    __tablename__ = "reward_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    points: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(256), default="")
    related_entity_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)


class Badge(Base):
    __tablename__ = "badges"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(256))
    condition_type: Mapped[str] = mapped_column(String(32))
    condition_value: Mapped[int] = mapped_column(Integer)


class UserBadge(Base):
    __tablename__ = "user_badges"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    badge_id: Mapped[int] = mapped_column(ForeignKey("badges.id"))
    earned_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    __table_args__ = (UniqueConstraint("user_id", "badge_id"),)


class WakeUpEvent(Base):
    """V2: ثبت بیدار شدن — یک‌بار در روز."""
    __tablename__ = "wake_up_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("user_id", "date"),)


# ------------------------------- V2.1: Behavioral ---------------------------

class UserProfile(Base):
    """مدل کاربر: شخصیت + ترجیحات + confidence."""
    __tablename__ = "user_profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    personality_json: Mapped[dict] = mapped_column(JSON, default=dict)
    preferences_json: Mapped[dict] = mapped_column(JSON, default=dict)
    behavior_json: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc)


class BehaviorEvent(Base):
    """حافظه رفتاری — append-only و قابل بازمحاسبه featureها."""
    __tablename__ = "behavior_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    event_time: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    event_date: Mapped[dt.date] = mapped_column(Date, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(16), default="system")  # system/self_report


class UserStateSnapshot(Base):
    """وضعیت لحظه‌ای — جدا از شخصیت."""
    __tablename__ = "user_state_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    captured_date: Mapped[dt.date] = mapped_column(Date, index=True)
    energy: Mapped[float] = mapped_column(Float, default=0.5)
    focus: Mapped[float] = mapped_column(Float, default=0.5)
    motivation: Mapped[float] = mapped_column(Float, default=0.5)
    stress: Mapped[float] = mapped_column(Float, default=0.5)
    fatigue: Mapped[float] = mapped_column(Float, default=0.5)
    readiness: Mapped[float] = mapped_column(Float, default=0.5)
    confidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(16), default="self_report")


class PlanningInterview(Base):
    """مصاحبه برنامه‌ریزی ابتدای هفته — V2.1."""
    __tablename__ = "planning_interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    week_start: Mapped[dt.date] = mapped_column(Date, index=True)
    answers_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress/completed
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    model_version: Mapped[str] = mapped_column(String(16), default="2.1")


class OnboardingAnswer(Base):
    """پاسخ‌های پرسشنامه تطبیقی — self-report (جدا از رفتار مشاهده‌شده)."""
    __tablename__ = "onboarding_answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question_key: Mapped[str] = mapped_column(String(64))
    answer_key: Mapped[str] = mapped_column(String(8))
    answered_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc)
    __table_args__ = (UniqueConstraint("user_id", "question_key"),)


class CapacityEstimate(Base):
    """ظرفیت تخمینی — خروجی حلقه تطبیق (Plan→Act→Observe→Evaluate→Update)."""
    __tablename__ = "capacity_estimates"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[str] = mapped_column(String(16))  # school_day | free_day
    tasks_per_day: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.2)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc)
    __table_args__ = (UniqueConstraint("user_id", "scope"),)


class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scope_type: Mapped[str] = mapped_column(String(16))  # total/book/node
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_date: Mapped[dt.date] = mapped_column(Date, index=True)
    attempted: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    wrong: Mapped[int] = mapped_column(Integer, default=0)
    unanswered: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    coverage: Mapped[float] = mapped_column(Float, default=0.0)
