"""SQLAlchemy models for StudyS459 V3.

Design rules enforced by the schema (from the V3 master specification):

* raw observations are append oriented and never overwritten;
* derived tables are rebuildable and always carry a ``model_version``;
* question definition, answer key and response sheet are three separate things;
* ``ANSWERED`` / ``UNANSWERED`` / ``NOT_ENTERED`` are three separate states;
* taught state is its own entity and never implies mastery;
* activities (time constraints) are never study tasks;
* user decisions (manual overrides, recommendation feedback) are stored as data.
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from .base import Base, SafeJSON


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)


# ===========================================================================
# Identity / configuration
# ===========================================================================

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    grade = Column(String(32), default="یازدهم")
    track = Column(String(32), default="ریاضی-تجربی")
    timezone = Column(String(64), default="Asia/Tehran")
    total_coins = Column(Integer, default=0)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    season_mode = Column(String(16), default="school_term")
    quiet_mode = Column(Boolean, default=True)
    auto_time_adjust = Column(Boolean, default=True)
    onboarding_completed = Column(Boolean, default=False)

    profile = relationship("UserProfile", back_populates="user", uselist=False)


class UserProfile(Base, TimestampMixin):
    """Personality / preferences. Every dimension carries value+confidence+evidence."""

    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # {"discipline": {"value": 0.5, "confidence": 0.4, "evidence_count": 6, "last_updated": iso}}
    personality = Column(SafeJSON, default=dict)
    # self reported vs observed kept apart (V2.1 golden rule)
    self_reported = Column(SafeJSON, default=dict)
    preferences = Column(SafeJSON, default=dict)
    model_version = Column(String(32), default="v3.0.0")
    version = Column(Integer, default=1)

    user = relationship("User", back_populates="profile")


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True)
    model_name = Column(String(64), nullable=False)
    version = Column(String(32), nullable=False)
    params = Column(SafeJSON, default=dict)
    notes = Column(Text)
    active = Column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("model_name", "version", name="uq_model_version"),)


# ===========================================================================
# Curriculum: subjects / books / topics / dependencies
# ===========================================================================

class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    slug = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    grade = Column(String(32))
    track = Column(String(32))
    color = Column(String(16), default="#4f46e5")
    order_index = Column(Integer, default=0)


class Book(Base, TimestampMixin):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    stable_key = Column(String(64), unique=True, nullable=False)
    title = Column(String(160), nullable=False)
    publisher = Column(String(120))
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    grade = Column(String(32))
    track = Column(String(32))
    edition = Column(String(32))
    config_version = Column(String(16), default="v3")
    notes = Column(Text)
    active = Column(Boolean, default=True)
    hierarchy_note = Column(Text)

    subject = relationship("Subject")
    topics = relationship("Topic", back_populates="book", cascade="all, delete-orphan")


class UserBookActivation(Base, TimestampMixin):
    __tablename__ = "user_book_activations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    active = Column(Boolean, default=True)
    activated_at = Column(DateTime, default=_now)

    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book"),)


class Topic(Base, TimestampMixin):
    """A node of the curriculum tree: book > chapter > lesson > section > subsection > topic."""

    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("topics.id"))
    node_type = Column(String(24), nullable=False, default="topic")
    title = Column(String(255), nullable=False)
    code = Column(String(32))
    order_index = Column(Integer, default=0)
    depth = Column(Integer, default=0)
    path = Column(String(512), default="")  # materialized path of ids: /1/12/34/
    is_leaf = Column(Boolean, default=True)
    # difficulty bands / level metadata (e.g. حسابان level 1..3 test sets)
    metadata_json = Column(SafeJSON, default=dict)

    book = relationship("Book", back_populates="topics")
    children = relationship("Topic", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_topics_book_parent", "book_id", "parent_id"),
        Index("ix_topics_path", "path"),
    )


class TopicDependency(Base, TimestampMixin):
    """Topic A is a prerequisite of topic B. Cycles are rejected in the service layer."""

    __tablename__ = "topic_dependencies"

    id = Column(Integer, primary_key=True)
    prerequisite_topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    dependent_topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    strength = Column(Float, default=0.5)
    source = Column(String(24), default="user")  # user | curriculum | inferred
    note = Column(Text)

    __table_args__ = (
        UniqueConstraint("prerequisite_topic_id", "dependent_topic_id", name="uq_dependency"),
    )


# ===========================================================================
# Questions / answer keys / test sets
# ===========================================================================

class TestSet(Base, TimestampMixin):
    __tablename__ = "test_sets"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"))
    title = Column(String(160), nullable=False)
    test_type = Column(String(24), default="normal")  # normal | review | mock | level
    difficulty_level = Column(Integer)  # 1..3 for حسابان levels
    metadata_json = Column(SafeJSON, default=dict)


class Question(Base, TimestampMixin):
    """Question *definition* only. Answer key and responses live elsewhere."""

    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    test_set_id = Column(Integer, ForeignKey("test_sets.id"))
    primary_topic_id = Column(Integer, ForeignKey("topics.id"))
    stable_key = Column(String(96), nullable=False)
    sequence_no = Column(Integer, nullable=False)
    difficulty_level = Column(Integer)
    answer_type = Column(String(24), default="four_choice")
    current_answer_key = Column(String(8))  # denormalised cache of latest AnswerKeyVersion
    current_answer_key_version = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    disabled_reason = Column(String(160))
    metadata_json = Column(SafeJSON, default=dict)
    source = Column(String(24), default="manual")  # manual | import | seed

    __table_args__ = (
        UniqueConstraint("book_id", "stable_key", name="uq_question_stable_key"),
        UniqueConstraint("test_set_id", "sequence_no", name="uq_question_sequence"),
        Index("ix_questions_topic", "primary_topic_id"),
    )


class QuestionTopic(Base, TimestampMixin):
    """Multi-topic mapping: primary / related / prerequisite / solution-used."""

    __tablename__ = "question_topics"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    relation = Column(String(24), default="primary")  # primary|related|prerequisite|solution
    weight = Column(Float, default=1.0)
    source = Column(String(24), default="manual")
    corrected_from = Column(Integer)  # previous topic id, mapping is correctable

    __table_args__ = (UniqueConstraint("question_id", "topic_id", "relation", name="uq_question_topic"),)


class AnswerKeyVersion(Base, TimestampMixin):
    """Answer key is versioned: corrections keep the audit history."""

    __tablename__ = "answer_key_versions"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    version_no = Column(Integer, nullable=False)
    answer_key = Column(String(8), nullable=False)  # "1".."4" (four-choice) or free text code
    reason = Column(String(160))
    changed_by = Column(String(24), default="user")
    superseded_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("question_id", "version_no", name="uq_answer_key_version"),)


# ===========================================================================
# Test sessions / response sheets / attempts
# ===========================================================================

class TestSession(Base, TimestampMixin):
    __tablename__ = "test_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_type = Column(String(24), default="practice")
    book_id = Column(Integer, ForeignKey("books.id"))
    topic_id = Column(Integer, ForeignKey("topics.id"))
    task_id = Column(Integer, ForeignKey("study_tasks.id"))
    exam_id = Column(Integer, ForeignKey("exams.id"))
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"))
    intervention_type = Column(String(32))

    timed = Column(Boolean, default=False)
    time_limit_seconds = Column(Integer)
    auto_time_adjusted = Column(Boolean, default=False)

    # V3.1: a checkup/comprehensive session covers a *range* of topics, not one topic
    coverage_id = Column(Integer, ForeignKey("checkup_coverages.id"))
    coverage_topic_ids = Column(SafeJSON, default=list)

    sequence_from = Column(Integer)
    sequence_to = Column(Integer)
    parity = Column(String(8), default="any")  # odd | even | any
    planned_question_count = Column(Integer)
    planned_duration_low = Column(Integer)
    planned_duration_high = Column(Integer)

    planned_date = Column(Date)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    actual_duration_minutes = Column(Float)
    status = Column(String(24), default="planned")
    is_imported = Column(Boolean, default=False)
    import_key = Column(String(96))  # idempotency for past imports
    source = Column(String(24), default="manual")
    notes = Column(Text)
    model_version = Column(String(32), default="v3.0.0")

    __table_args__ = (Index("ix_sessions_user_date", "user_id", "planned_date"),)


class SessionQuestion(Base, TimestampMixin):
    __tablename__ = "session_questions"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("test_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    display_order = Column(Integer, default=0)
    selection_reason = Column(String(160))

    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_session_question"),)


class ResponseSheet(Base, TimestampMixin):
    """The user's answers for one concrete sitting. Never redefines the question."""

    __tablename__ = "response_sheets"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("test_sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(16), default="open")  # open | finalized
    finalized_at = Column(DateTime)
    entry_mode = Column(String(16), default="live")  # live | historical_import


class ResponseEntry(Base, TimestampMixin):
    __tablename__ = "response_entries"

    id = Column(Integer, primary_key=True)
    response_sheet_id = Column(Integer, ForeignKey("response_sheets.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    state = Column(String(16), nullable=False, default="NOT_ENTERED")
    selected_choice = Column(String(8))
    response_time_seconds = Column(Integer)
    entered_at = Column(DateTime)
    entry_source = Column(String(16), default="live")
    note = Column(Text)

    __table_args__ = (UniqueConstraint("response_sheet_id", "question_id", name="uq_response_entry"),)


class AttemptResult(Base, TimestampMixin):
    """Comparison of a response entry with the answer key version that applied."""

    __tablename__ = "attempt_results"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("test_sessions.id"))
    response_entry_id = Column(Integer, ForeignKey("response_entries.id"))
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"))
    answer_key_version_id = Column(Integer, ForeignKey("answer_key_versions.id"))
    answer_key_value = Column(String(8))
    selected_choice = Column(String(8))
    state = Column(String(16), nullable=False)
    result = Column(String(16), nullable=False)
    difficulty_level = Column(Integer)
    duration_seconds = Column(Integer)
    attempted_on = Column(Date)
    evaluated_at = Column(DateTime, default=_now)
    is_current = Column(Boolean, default=True)
    superseded_by_id = Column(Integer, ForeignKey("attempt_results.id"))
    error_category = Column(String(24))
    error_category_confidence = Column(Float)
    source = Column(String(24), default="live")  # live | historical_import
    model_version = Column(String(32), default="v3.0.0")

    __table_args__ = (
        UniqueConstraint("response_entry_id", "is_current", name="uq_attempt_current_entry"),
        Index("ix_attempt_user_topic", "user_id", "topic_id"),
    )


# ===========================================================================
# Academic calendar: classes, activities, taught topics
# ===========================================================================

class ClassSchedule(Base, TimestampMixin):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    title = Column(String(160), nullable=False)
    kind = Column(String(24), default="external_class")  # school | external_class
    day_of_week = Column(Integer)  # 0 = شنبه .. 6 = جمعه (None until user fills it)
    start_time = Column(Time)
    end_time = Column(Time)
    recurring = Column(Boolean, default=True)
    source = Column(String(32), default="manual")  # manual | default_seed_v2
    active = Column(Boolean, default=True)
    notes = Column(Text)


class SchoolDayOverride(Base, TimestampMixin):
    __tablename__ = "school_day_overrides"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    is_school_day = Column(Boolean, nullable=False)
    reason = Column(String(160))
    capacity_multiplier = Column(Float)

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_school_override"),)


class ClassSession(Base, TimestampMixin):
    __tablename__ = "class_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"))
    date = Column(Date, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    attended = Column(Boolean, default=True)
    topics_taught_text = Column(Text)
    notes = Column(Text)


class TaughtTopic(Base, TimestampMixin):
    """Taught = exposed/covered. It never means learned or mastered."""

    __tablename__ = "taught_topics"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    taught = Column(Boolean, default=True)
    taught_at = Column(DateTime)
    source = Column(String(24), default="manual")  # manual | cascade | class_session | seed
    class_id = Column(Integer, ForeignKey("classes.id"))
    confidence = Column(Float, default=1.0)
    note = Column(Text)

    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_taught_topic"),)


class Activity(Base, TimestampMixin):
    """Occupies time and availability. Never a failed study task."""

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(160), nullable=False)
    category = Column(String(24), default="other")
    scheduling_type = Column(String(16), default="fixed")  # fixed|preferred|flexible|deadline_only
    date = Column(Date)  # one-off date
    day_of_week = Column(Integer)  # recurring weekday (0=شنبه)
    start_time = Column(Time)
    end_time = Column(Time)
    duration_minutes = Column(Integer)
    recurring = Column(Boolean, default=False)
    is_exceptional = Column(Boolean, default=False)
    note = Column(Text)
    active = Column(Boolean, default=True)


# ===========================================================================
# Planning: tasks, executions, capacity, planning sessions
# ===========================================================================

class StudyTask(Base, TimestampMixin):
    __tablename__ = "study_tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    task_type = Column(String(24), default="other")
    intervention_type = Column(String(32))
    book_id = Column(Integer, ForeignKey("books.id"))
    topic_id = Column(Integer, ForeignKey("topics.id"))
    goal_id = Column(Integer, ForeignKey("goals.id"))
    milestone_id = Column(Integer, ForeignKey("goal_milestones.id"))
    objective_id = Column(Integer, ForeignKey("goal_objectives.id"))
    exam_id = Column(Integer, ForeignKey("exams.id"))
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"))
    parent_task_id = Column(Integer, ForeignKey("study_tasks.id"))

    planned_date = Column(Date)
    planned_start_time = Column(Time)
    planned_question_count = Column(Integer)
    planned_minutes = Column(Integer)
    duration_low = Column(Integer)
    duration_high = Column(Integer)
    duration_confidence = Column(Float)
    parity = Column(String(8))
    sequence_from = Column(Integer)
    sequence_to = Column(Integer)

    status = Column(String(16), default="planned")
    source = Column(String(16), default="planner")
    manual_override = Column(Boolean, default=False)
    override_reason = Column(Text)
    priority_score = Column(Float)
    display_order = Column(Integer, default=0)
    planner_version = Column(String(32), default="v3.0.0")
    evidence = Column(SafeJSON, default=dict)
    created_by = Column(String(16), default="planner")
    updated_by = Column(String(16), default="planner")
    completed_at = Column(DateTime)
    cancelled_reason = Column(String(120))
    deferred_from_date = Column(Date)

    __table_args__ = (
        Index("ix_tasks_user_date_status", "user_id", "planned_date", "status"),
    )


class TaskExecution(Base, TimestampMixin):
    __tablename__ = "task_executions"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("study_tasks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    actual_minutes = Column(Integer)
    outcome = Column(String(16), default="completed")
    blocker = Column(String(160))
    perceived_difficulty = Column(Integer)
    state_snapshot = Column(SafeJSON, default=dict)
    note = Column(Text)


class CapacitySnapshot(Base, TimestampMixin):
    __tablename__ = "capacity_snapshots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    theoretical_minutes = Column(Integer)
    realistic_minutes = Column(Integer)
    planned_minutes = Column(Integer)
    completed_minutes = Column(Integer)
    planned_task_count = Column(Integer)
    completed_task_count = Column(Integer)
    confidence = Column(Float, default=0.3)
    factors = Column(SafeJSON, default=dict)
    evidence = Column(SafeJSON, default=dict)
    source = Column(String(24), default="estimate")
    model_version = Column(String(32), default="v3.0.0")

    __table_args__ = (UniqueConstraint("user_id", "date", "source", name="uq_capacity_day"),)


class PlanningSession(Base, TimestampMixin):
    __tablename__ = "planning_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    status = Column(String(24), default="interview")
    seed = Column(Integer, default=0)
    capacity_snapshot_id = Column(Integer, ForeignKey("capacity_snapshots.id"))
    interview = Column(SafeJSON, default=dict)          # weekly interview answers (user decisions)
    priority_suggestions = Column(SafeJSON, default=dict)  # what the user accepted/adjusted
    plan = Column(SafeJSON, default=dict)               # final edited plan (user owned)
    auto_plan = Column(SafeJSON, default=dict)          # untouched planner output
    explanation = Column(SafeJSON, default=dict)
    animation_stages = Column(SafeJSON, default=dict)
    overload = Column(SafeJSON, default=dict)
    confidence = Column(Float)
    planner_version = Column(String(32), default="v3.0.0")
    finalized_at = Column(DateTime)
    rebuilt_from_id = Column(Integer, ForeignKey("planning_sessions.id"))


class PlanningQuestion(Base, TimestampMixin):
    __tablename__ = "planning_questions"

    id = Column(Integer, primary_key=True)
    planning_session_id = Column(Integer, ForeignKey("planning_sessions.id"), nullable=False)
    code = Column(String(48), nullable=False)
    text = Column(Text, nullable=False)
    kind = Column(String(16), default="single_choice")
    options = Column(SafeJSON, default=list)
    because = Column(Text)               # "why we ask" -> explainability
    information_value = Column(Float)    # uncertainty * impact
    order_index = Column(Integer, default=0)
    uncertainty_key = Column(String(48))


class PlanningAnswer(Base, TimestampMixin):
    __tablename__ = "planning_answers"

    id = Column(Integer, primary_key=True)
    planning_question_id = Column(Integer, ForeignKey("planning_questions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    answer = Column(SafeJSON, default=dict)
    skipped = Column(Boolean, default=False)
    answered_at = Column(DateTime, default=_now)


class WeeklyGoal(Base, TimestampMixin):
    __tablename__ = "weekly_goals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    active = Column(Boolean, default=True)
    note = Column(Text)

    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_weekly_goal"),)


class WeeklyGoalItem(Base, TimestampMixin):
    __tablename__ = "weekly_goal_items"

    id = Column(Integer, primary_key=True)
    weekly_goal_id = Column(Integer, ForeignKey("weekly_goals.id"), nullable=False)
    goal_type = Column(String(32), default="question_count")  # question_count|topic|accuracy
    target_value = Column(Float)
    achieved_value = Column(Float, default=0)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    book_id = Column(Integer, ForeignKey("books.id"))
    topic_id = Column(Integer, ForeignKey("topics.id"))
    label = Column(String(160))


# ===========================================================================
# Exams (school + mock) and goals
# ===========================================================================

class Exam(Base, TimestampMixin):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    exam_type = Column(String(16), default="school")  # personal|school|mock|checkup|comprehensive
    title = Column(String(200), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"))  # null for multi-subject mock
    # V3.1: a mock/comprehensive exam can span several subjects; `subject_id` stays
    # as the primary (backward compatible) subject.
    subjects = Column(SafeJSON, default=list)      # [subject_id, ...]
    source = Column(String(120))                    # «مدرسه»، «کانون»، «خودم»
    question_count = Column(Integer)                # V3.1 name for the planned count
    answer_key = Column(SafeJSON, default=dict)     # {sequence: 1..4}
    answer_key_source = Column(String(24))          # manual | imported | scanned
    coverage_range = Column(SafeJSON, default=dict)  # checkup: {included_topics, from, to}
    provider = Column(String(120))
    exam_date = Column(Date, nullable=False)
    start_time = Column(Time)
    status = Column(String(16), default="planned")
    total_questions = Column(Integer)
    planned_question_count = Column(Integer)
    actual_question_count = Column(Integer)
    planned_duration_minutes = Column(Integer)
    actual_duration_minutes = Column(Integer)
    score = Column(Float)
    max_score = Column(Float)
    percentage = Column(Float)
    correct_count = Column(Integer)
    wrong_count = Column(Integer)
    unanswered_count = Column(Integer)
    keep_for_retake = Column(Boolean, default=False)
    use_for_future_prep = Column(Boolean, default=True)
    retake_of_id = Column(Integer, ForeignKey("exams.id"))
    attempt_no = Column(Integer, default=1)
    files = Column(SafeJSON, default=list)          # uploaded PDF/photo metadata
    planned_topics_only = Column(Boolean, default=True)
    notes = Column(Text)
    model_version = Column(String(32), default="v3.0.0")


class ExamTopic(Base, TimestampMixin):
    __tablename__ = "exam_topics"

    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    mark_kind = Column(String(8), default="planned")  # planned | actual (kept separate!)
    checked = Column(Boolean, default=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    question_from = Column(Integer)
    question_to = Column(Integer)
    planned_question_count = Column(Integer)
    note = Column(Text)

    __table_args__ = (UniqueConstraint("exam_id", "topic_id", "mark_kind", name="uq_exam_topic_mark"),)


class ExamAttempt(Base, TimestampMixin):
    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    attempt_no = Column(Integer, default=1)
    date = Column(Date)
    duration_minutes = Column(Integer)
    per_subject = Column(SafeJSON, default=dict)  # per-subject duration / counts
    answers = Column(SafeJSON, default=dict)      # sequence -> choice/null(unanswered)/absent(not entered)
    score = Column(Float)
    percentage = Column(Float)
    correct_count = Column(Integer)
    wrong_count = Column(Integer)
    unanswered_count = Column(Integer)
    question_count = Column(Integer)
    # per-subject / per-part result summary + the follow-up the attempt produced
    summary = Column(SafeJSON, default=dict)
    note = Column(Text)


class QuestionEffect(Base, TimestampMixin):
    """Derived effect of a purposeful answer (V3.1 doc 07).

    The raw answer stays in ``DailyCheckin``/``WeeklyReflection``; this table keeps
    only the *bounded* change that was applied to a derived value, so raw data and
    derived data never mix (V3 hard rule).
    """

    __tablename__ = "question_effects"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # points at daily_checkins.id or weekly_reflections.id depending on the channel
    checkin_id = Column(Integer)
    channel = Column(String(24), nullable=False)          # day_start | day_end | weekly | onboarding
    question_code = Column(String(48), nullable=False)
    applied_to = Column(String(64), nullable=False)       # capacity.today | priority.weight.*@weekly | ordering.today
    day = Column(Date, nullable=False)                    # the day the effect applies to
    delta_pct = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    evidence_count = Column(Integer, default=0)
    note = Column(Text)
    model_version = Column(String(32))

    __table_args__ = (
        UniqueConstraint("user_id", "channel", "question_code", "day", name="uq_question_effect"),
    )


class CalendarOccasion(Base, TimestampMixin):
    """A student-defined calendar entry (V3.1 doc 05 — «حداقل ساختار داده»).

    Only fixed solar holidays ship as data; lunar occasions move every year, so the
    student adds theirs here instead of the app guessing.
    """

    __tablename__ = "calendar_occasions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    occurs_on = Column(Date, nullable=False)
    jalali_year = Column(Integer, nullable=False)
    title = Column(String(160), nullable=False)
    kind = Column(String(24), default="personal")  # personal | religious | school | holiday
    is_holiday = Column(Boolean, default=False)
    note = Column(Text)

    __table_args__ = (Index("ix_calendar_occasion_user_year", "user_id", "jalali_year"),)


class CheckupCoverage(Base, TimestampMixin):
    """V3.1 doc 03: a checkup is a *coverage range*, never a single topic.

    Seeded from the chemistry table of contents («• آزمون چکاپ اول …») and used by
    the testing engine to build a session over ``included_topic_ids`` — the segment
    from the previous checkup up to this one.
    """

    __tablename__ = "checkup_coverages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    chapter_topic_id = Column(Integer, ForeignKey("topics.id"))
    chapter_title = Column(String(200))
    kind = Column(String(16), default="checkup")          # checkup | comprehensive
    label = Column(String(160), nullable=False)
    order_index = Column(Integer, default=0)
    scope = Column(String(16), default="segment")         # segment | chapter
    covered_from = Column(String(200))
    covered_to = Column(String(200))
    included_topic_ids = Column(SafeJSON, default=list)
    included_topic_titles = Column(SafeJSON, default=list)
    previous_checkup_id = Column(Integer, ForeignKey("checkup_coverages.id"))
    source_file = Column(String(200))
    exam_id = Column(Integer, ForeignKey("exams.id"))

    # «آزمون چکاپ اول» repeats in every chapter, so identity is the file order
    __table_args__ = (UniqueConstraint("book_id", "order_index", name="uq_checkup_book_order"),)


class Goal(Base, TimestampMixin):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    goal_type = Column(String(24), default="three_month")
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    book_id = Column(Integer, ForeignKey("books.id"))
    topic_id = Column(Integer, ForeignKey("topics.id"))
    # multi-book / multi-topic scope (V3 doc 06): a goal is not always one node
    scope = Column(SafeJSON, default=dict)
    status = Column(String(16), default="active")
    start_date = Column(Date)
    target_date = Column(Date)  # ~3 months later by default
    baseline = Column(SafeJSON, default=dict)
    target = Column(SafeJSON, default=dict)
    progress = Column(SafeJSON, default=dict)
    confidence = Column(Float)
    notes = Column(Text)
    model_version = Column(String(32), default="v3.0.0")


class GoalMilestone(Base, TimestampMixin):
    __tablename__ = "goal_milestones"

    id = Column(Integer, primary_key=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("goal_milestones.id"))
    level = Column(String(8), default="month")  # month | week | day
    title = Column(String(200), nullable=False)
    target_date = Column(Date)
    metrics = Column(SafeJSON, default=dict)
    progress = Column(SafeJSON, default=dict)
    status = Column(String(16), default="pending")
    adapted_from = Column(SafeJSON, default=dict)  # deviation driven adaptation history


class GoalObjective(Base, TimestampMixin):
    __tablename__ = "goal_objectives"

    id = Column(Integer, primary_key=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    milestone_id = Column(Integer, ForeignKey("goal_milestones.id"))
    topic_id = Column(Integer, ForeignKey("topics.id"))
    title = Column(String(200), nullable=False)
    metric = Column(String(24), default="coverage")  # coverage|accuracy|question_count|readiness
    target_value = Column(Float)
    current_value = Column(Float)
    unit = Column(String(16))
    status = Column(String(16), default="pending")


# ===========================================================================
# Learning intelligence (derived, rebuildable, versioned)
# ===========================================================================

class LearningState(Base, TimestampMixin):
    __tablename__ = "learning_states"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    accuracy = Column(Float)
    coverage = Column(Float)
    attempts = Column(Integer, default=0)
    answered = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    wrong = Column(Integer, default=0)
    unanswered = Column(Integer, default=0)
    not_entered = Column(Integer, default=0)
    retention_estimate = Column(Float)
    retention_confidence = Column(Float)
    confidence = Column(Float)
    recency_days = Column(Float)
    difficulty_adjusted = Column(Float)
    repeated_error_signal = Column(Float)
    time_performance = Column(Float)
    exam_readiness = Column(Float)
    prerequisite_health = Column(Float)
    uncertainty = Column(Float)
    evidence = Column(SafeJSON, default=dict)
    computed_at = Column(DateTime, default=_now)
    model_version = Column(String(32), default="v3.0.0")

    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", "model_version", name="uq_learning_state"),
        Index("ix_learning_state_user", "user_id"),
    )


class CoverageMetric(Base, TimestampMixin):
    __tablename__ = "coverage_metrics"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scope_type = Column(String(16), default="topic")  # topic|book|subject
    scope_id = Column(Integer, nullable=False)
    target_question_count = Column(Integer, default=0)
    attempted_question_count = Column(Integer, default=0)
    coverage = Column(Float)
    computed_at = Column(DateTime, default=_now)
    model_version = Column(String(32), default="v3.0.0")

    __table_args__ = (UniqueConstraint("user_id", "scope_type", "scope_id", name="uq_coverage_scope"),)


class AccuracyMetric(Base, TimestampMixin):
    __tablename__ = "accuracy_metrics"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scope_type = Column(String(16), default="topic")
    scope_id = Column(Integer, nullable=False)
    answered = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    wrong = Column(Integer, default=0)
    unanswered = Column(Integer, default=0)
    accuracy = Column(Float)
    unanswered_rate = Column(Float)
    computed_at = Column(DateTime, default=_now)
    model_version = Column(String(32), default="v3.0.0")

    __table_args__ = (UniqueConstraint("user_id", "scope_type", "scope_id", name="uq_accuracy_scope"),)


class RetentionState(Base, TimestampMixin):
    __tablename__ = "retention_states"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    retention_estimate = Column(Float)
    stability_days = Column(Float)
    last_reviewed_at = Column(DateTime)
    last_review_result = Column(String(16))
    next_review_at = Column(DateTime)
    review_count = Column(Integer, default=0)
    lapses = Column(Integer, default=0)
    confidence = Column(Float)
    evidence_count = Column(Integer, default=0)
    model_version = Column(String(32), default="v3.0.0")

    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_retention_topic"),)


class ConfidenceState(Base, TimestampMixin):
    """value + confidence + evidence_count for every important prediction."""

    __tablename__ = "confidence_states"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scope_type = Column(String(24), nullable=False)  # topic|subject|user|goal|exam|capacity|duration
    scope_id = Column(Integer)
    metric = Column(String(48), nullable=False)
    value = Column(Float)
    confidence = Column(Float)
    evidence_count = Column(Integer, default=0)
    evidence = Column(SafeJSON, default=dict)
    model_version = Column(String(32), default="v3.0.0")

    __table_args__ = (UniqueConstraint("user_id", "scope_type", "scope_id", "metric", name="uq_confidence_metric"),)


class ReviewItem(Base, TimestampMixin):
    __tablename__ = "review_items"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"))
    topic_id = Column(Integer, ForeignKey("topics.id"))
    reason = Column(String(24), default="wrong")
    priority = Column(String(16), default="normal")  # critical|high|normal|low
    wrong_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    state = Column(String(16), default="open")
    scheduled_for = Column(Date)
    source_session_id = Column(Integer, ForeignKey("test_sessions.id"))
    last_attempt_id = Column(Integer, ForeignKey("attempt_results.id"))
    resolved_at = Column(DateTime)
    evidence = Column(SafeJSON, default=dict)

    __table_args__ = (UniqueConstraint("user_id", "question_id", "state", name="uq_review_item"),)


# ===========================================================================
# Decisions: recommendations / priorities
# ===========================================================================

class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scope = Column(String(16), default="weekly")  # daily|weekly|exam|mock|topic
    intervention_type = Column(String(32))
    book_id = Column(Integer, ForeignKey("books.id"))
    topic_id = Column(Integer, ForeignKey("topics.id"))
    exam_id = Column(Integer, ForeignKey("exams.id"))
    goal_id = Column(Integer, ForeignKey("goals.id"))
    title = Column(String(220))
    human_reason = Column(Text)
    question_count = Column(Integer)
    duration_low = Column(Integer)
    duration_high = Column(Integer)
    priority_score = Column(Float)
    confidence = Column(Float)
    status = Column(String(24), default="proposed")
    recommended_for = Column(Date)
    expires_at = Column(Date)
    feedback = Column(SafeJSON, default=dict)
    explanation = Column(SafeJSON, default=dict)
    model_version = Column(String(32), default="v3.0.0")
    quiet = Column(Boolean, default=True)


class RecommendationReason(Base, TimestampMixin):
    __tablename__ = "recommendation_reasons"

    id = Column(Integer, primary_key=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    code = Column(String(48), nullable=False)
    weight = Column(Float)
    human_text = Column(Text)
    evidence = Column(SafeJSON, default=dict)


class PrioritySnapshot(Base, TimestampMixin):
    __tablename__ = "priority_snapshots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    horizon = Column(String(16), default="week")
    computed_for = Column(Date)
    score = Column(Float)
    components = Column(SafeJSON, default=dict)
    confidence = Column(Float)
    model_version = Column(String(32), default="v3.0.0")
    rank = Column(Integer)

    __table_args__ = (UniqueConstraint("user_id", "topic_id", "horizon", "computed_for", name="uq_priority_snapshot"),)


# ===========================================================================
# Time estimation
# ===========================================================================

class DurationPrediction(Base, TimestampMixin):
    __tablename__ = "duration_predictions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scope_type = Column(String(24), default="task")  # task|session|topic
    scope_id = Column(Integer)
    task_type = Column(String(24))
    question_count = Column(Integer)
    low_minutes = Column(Integer)
    high_minutes = Column(Integer)
    point_minutes = Column(Integer)
    confidence = Column(Float)
    evidence_count = Column(Integer, default=0)
    method = Column(String(32))  # personal_model|topic_model|type_model|first_month_fallback
    based_on = Column(SafeJSON, default=dict)
    model_version = Column(String(32), default="v3.0.0")


class DurationObservation(Base, TimestampMixin):
    __tablename__ = "duration_observations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("study_tasks.id"))
    session_id = Column(Integer, ForeignKey("test_sessions.id"))
    task_type = Column(String(24))
    topic_id = Column(Integer, ForeignKey("topics.id"))
    book_id = Column(Integer, ForeignKey("books.id"))
    question_count = Column(Integer)
    difficulty = Column(Integer)
    actual_minutes = Column(Integer, nullable=False)
    predicted_low = Column(Integer)
    predicted_high = Column(Integer)
    within_range = Column(Boolean)
    time_of_day = Column(String(16))  # morning|afternoon|evening|night
    state = Column(SafeJSON, default=dict)
    source = Column(String(16), default="user")  # user | system
    recorded_at = Column(DateTime, default=_now)


# ===========================================================================
# Behaviour, state, patterns, experiments
# ===========================================================================

class BehaviorObservation(Base, TimestampMixin):
    __tablename__ = "behavior_observations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(48), nullable=False)
    observed_at = Column(DateTime, default=_now)
    day = Column(Date)
    source = Column(String(16), default="observed")  # observed | self_report | user
    payload = Column(SafeJSON, default=dict)
    task_id = Column(Integer, ForeignKey("study_tasks.id"))
    session_id = Column(Integer, ForeignKey("test_sessions.id"))


class UserState(Base, TimestampMixin):
    __tablename__ = "user_states"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    captured_at = Column(DateTime, default=_now)
    day = Column(Date)
    energy = Column(Float)
    focus = Column(Float)
    motivation = Column(Float)
    stress = Column(Float)
    fatigue = Column(Float)
    readiness = Column(Float)
    confidence = Column(SafeJSON, default=dict)
    source = Column(String(16), default="checkin")  # checkin | inferred
    evidence = Column(SafeJSON, default=dict)


class BehaviorPattern(Base, TimestampMixin):
    __tablename__ = "behavior_patterns"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pattern_code = Column(String(48), nullable=False)
    description = Column(Text)
    strength = Column(Float)
    confidence = Column(Float)
    evidence_count = Column(Integer, default=0)
    first_seen = Column(Date)
    last_seen = Column(Date)
    evidence = Column(SafeJSON, default=dict)
    dismissed_until = Column(DateTime)
    suggestion = Column(Text)

    __table_args__ = (UniqueConstraint("user_id", "pattern_code", name="uq_pattern_code"),)


class Experiment(Base, TimestampMixin):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    hypothesis = Column(Text, nullable=False)
    intervention = Column(SafeJSON, default=dict)
    control = Column(SafeJSON, default=dict)
    metric = Column(String(48), nullable=False)
    metric_direction = Column(String(8), default="higher")
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String(16), default="planned")  # planned|running|completed|abandoned
    result = Column(SafeJSON, default=dict)
    confidence = Column(Float)
    notes = Column(Text)


class ExperimentObservation(Base, TimestampMixin):
    __tablename__ = "experiment_observations"

    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    phase = Column(String(16), nullable=False)  # intervention | control
    observed_at = Column(DateTime, default=_now)
    day = Column(Date)
    metrics = Column(SafeJSON, default=dict)
    note = Column(Text)


class ExperimentResult(Base, TimestampMixin):
    __tablename__ = "experiment_results"

    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    computed_at = Column(DateTime, default=_now)
    metric = Column(String(48))
    intervention_value = Column(Float)
    control_value = Column(Float)
    n_intervention = Column(Integer)
    n_control = Column(Integer)
    effect_size = Column(Float)
    conclusion = Column(String(32))  # supports|contradicts|inconclusive
    confidence = Column(Float)
    interpretation = Column(Text)
    model_version = Column(String(32), default="v3.0.0")


class ResearchEntry(Base, TimestampMixin):
    __tablename__ = "research_registry"

    id = Column(Integer, primary_key=True)
    source = Column(String(64))
    title = Column(String(300), nullable=False)
    authors = Column(String(300))
    year = Column(Integer)
    doi_url = Column(String(300))
    finding = Column(Text)
    limitations = Column(Text)
    product_implication = Column(Text)
    evidence_level = Column(String(24), default="HEURISTIC")
    review_date = Column(Date)
    linked_params = Column(SafeJSON, default=list)


# ===========================================================================
# Questionnaires / check-ins / rewards / habits
# ===========================================================================

class OnboardingQuestion(Base, TimestampMixin):
    __tablename__ = "onboarding_questions"

    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False)
    group = Column(String(48))
    text = Column(Text, nullable=False)
    kind = Column(String(16), default="single_choice")
    options = Column(SafeJSON, default=list)
    # multi-facet: each answer nudges 2..4 dimensions with small deltas
    effects = Column(SafeJSON, default=dict)
    order_index = Column(Integer, default=0)
    active = Column(Boolean, default=True)


class OnboardingAnswer(Base, TimestampMixin):
    __tablename__ = "onboarding_answers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_code = Column(String(64), nullable=False)
    answer = Column(SafeJSON, default=dict)
    dimension_deltas = Column(SafeJSON, default=dict)
    answered_at = Column(DateTime, default=_now)


class OnboardingState(Base, TimestampMixin):
    __tablename__ = "onboarding_state"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    asked_codes = Column(SafeJSON, default=list)
    skipped_codes = Column(SafeJSON, default=list)
    completed = Column(Boolean, default=False)
    uncertainty = Column(SafeJSON, default=dict)
    updated_round = Column(Integer, default=1)


class DailyCheckin(Base, TimestampMixin):
    __tablename__ = "daily_checkins"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    day = Column(Date, nullable=False)
    phase = Column(String(8), default="start")  # start | end
    answers = Column(SafeJSON, default=dict)
    skipped = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("user_id", "day", "phase", name="uq_checkin"),)


class WeeklyReflection(Base, TimestampMixin):
    __tablename__ = "weekly_reflections"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    answers = Column(SafeJSON, default=dict)
    skipped = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_reflection"),)


class RewardEvent(Base, TimestampMixin):
    __tablename__ = "reward_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(String(48), nullable=False)
    coins = Column(Integer, default=0)
    description = Column(String(200))
    related_entity_type = Column(String(32))
    related_entity_id = Column(Integer)
    dedupe_key = Column(String(96))
    day = Column(Date)
    created_at_local = Column(DateTime)

    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_reward_dedupe"),)


class Badge(Base, TimestampMixin):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True)
    code = Column(String(48), unique=True, nullable=False)
    title = Column(String(120), nullable=False)
    description = Column(Text)
    condition_type = Column(String(48))
    condition_value = Column(Float)
    icon = Column(String(16))


class UserBadge(Base, TimestampMixin):
    __tablename__ = "user_badges"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=False)
    earned_at = Column(DateTime, default=_now)

    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)


class Habit(Base, TimestampMixin):
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    code = Column(String(48), nullable=False)
    title = Column(String(160))
    target = Column(String(64))
    streak = Column(Integer, default=0)
    best_streak = Column(Integer, default=0)
    last_success_date = Column(Date)
    metadata_json = Column(SafeJSON, default=dict)

    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_habit"),)


class WakeUpEvent(Base, TimestampMixin):
    __tablename__ = "wake_up_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    day = Column(Date, nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    local_time = Column(String(8))
    coins_awarded = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_wakeup_day"),)


class NodeParityState(Base, TimestampMixin):
    __tablename__ = "node_parity_state"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    last_parity = Column(String(8))
    last_used_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_parity_state"),)


# ===========================================================================
# Integrity: audit, recalculation, notifications, integrations
# ===========================================================================

class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String(64), nullable=False)
    entity_type = Column(String(48))
    entity_id = Column(Integer)
    actor = Column(String(16), default="user")  # user | system
    reason = Column(Text)
    before = Column(SafeJSON, default=dict)
    after = Column(SafeJSON, default=dict)

    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)


class RecalculationJob(Base, TimestampMixin):
    __tablename__ = "recalculation_jobs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    scope = Column(String(24), nullable=False)
    scope_id = Column(Integer)
    trigger = Column(String(120))
    status = Column(String(16), default="queued")
    incremental = Column(Boolean, default=True)
    changes = Column(SafeJSON, default=dict)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    model_version = Column(String(32), default="v3.0.0")
    error = Column(Text)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(48))
    title = Column(String(200))
    body = Column(Text)
    quiet = Column(Boolean, default=True)
    source_type = Column(String(32))
    source_id = Column(Integer)
    read_at = Column(DateTime)
    dismissed_until = Column(DateTime)


class TelegramConnection(Base, TimestampMixin):
    """Optional, non critical add-on (V2.2). The app is complete without it."""

    __tablename__ = "telegram_connections"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    chat_id = Column(String(64))
    enabled = Column(Boolean, default=False)
    settings = Column(SafeJSON, default=dict)
    last_error = Column(Text)
