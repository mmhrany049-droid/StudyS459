"""Domain vocabulary - enums and constants shared by engines and API layer.

The names mirror the V3 master specification one-to-one so that a reader can
map code back to the document.
"""

from __future__ import annotations

from enum import Enum


class NodeType(str, Enum):
    """Topic hierarchy: Subject > Book > Chapter > Lesson > Section > Subsection/Fine topic."""

    BOOK = "book"
    CHAPTER = "chapter"
    LESSON = "lesson"
    SECTION = "section"
    SUBSECTION = "subsection"
    TOPIC = "topic"


NODE_TYPE_LABELS_FA = {
    NodeType.BOOK: "کتاب",
    NodeType.CHAPTER: "فصل",
    NodeType.LESSON: "درس",
    NodeType.SECTION: "بخش",
    NodeType.SUBSECTION: "زیربخش",
    NodeType.TOPIC: "مبحث",
}

NODE_TYPE_ORDER = [
    NodeType.CHAPTER,
    NodeType.LESSON,
    NodeType.SECTION,
    NodeType.SUBSECTION,
    NodeType.TOPIC,
]


class AnswerState(str, Enum):
    """The three mandatory and distinct response states (V3 non-negotiable rule)."""

    ANSWERED = "ANSWERED"
    UNANSWERED = "UNANSWERED"        # user really left it blank
    NOT_ENTERED = "NOT_ENTERED"      # historical response not entered yet


class AttemptResultValue(str, Enum):
    CORRECT = "CORRECT"
    WRONG = "WRONG"
    UNANSWERED = "UNANSWERED"
    NOT_EVALUABLE = "NOT_EVALUABLE"  # no answer key yet -> pending correction
    NOT_ENTERED = "NOT_ENTERED"      # the row was never recorded: not "unanswered"


class SessionType(str, Enum):
    PRACTICE = "practice"
    REVIEW = "review"
    TIMED_QUIZ = "timed_quiz"
    DIAGNOSTIC = "diagnostic"
    MOCK = "mock"
    IMPORTED = "imported"
    CHECKUP = "checkup"              # coverage-range session (V3.1 doc 03)
    COMPREHENSIVE = "comprehensive"  # multi-chapter closure session


SESSION_TYPE_LABELS_FA = {
    SessionType.PRACTICE.value: "تمرین",
    SessionType.REVIEW.value: "مرور",
    SessionType.TIMED_QUIZ.value: "آزمون زمان‌دار",
    SessionType.DIAGNOSTIC.value: "تشخیصی",
    SessionType.MOCK.value: "آزمون آزمایشی",
    SessionType.IMPORTED.value: "ورود گذشته",
    SessionType.CHECKUP.value: "چکاپ",
    SessionType.COMPREHENSIVE.value: "جامع",
}


class SessionStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PENDING_CORRECTION = "pending_correction"
    ABANDONED = "abandoned"


class InterventionType(str, Enum):
    """Choose WHY/WHAT before choosing questions (V3)."""

    READ_LESSON = "READ_LESSON"
    REVIEW = "REVIEW"
    ACTIVE_RECALL = "ACTIVE_RECALL"
    EASY_PRACTICE = "EASY_PRACTICE"
    MEDIUM_PRACTICE = "MEDIUM_PRACTICE"
    DIFFICULT_PRACTICE = "DIFFICULT_PRACTICE"
    MIXED_PRACTICE = "MIXED_PRACTICE"
    TIMED_QUIZ = "TIMED_QUIZ"
    DIAGNOSTIC = "DIAGNOSTIC"
    MOCK_EXAM = "MOCK_EXAM"
    PREREQUISITE_REVIEW = "PREREQUISITE_REVIEW"
    ERROR_REVIEW = "ERROR_REVIEW"


INTERVENTION_LABELS_FA = {
    InterventionType.READ_LESSON: "خواندن درس‌نامه",
    InterventionType.REVIEW: "مرور",
    InterventionType.ACTIVE_RECALL: "یادآوری فعال",
    InterventionType.EASY_PRACTICE: "تمرین آسان",
    InterventionType.MEDIUM_PRACTICE: "تمرین متوسط",
    InterventionType.DIFFICULT_PRACTICE: "تمرین دشوار",
    InterventionType.MIXED_PRACTICE: "تمرین ترکیبی",
    InterventionType.TIMED_QUIZ: "آزمون زمان‌دار",
    InterventionType.DIAGNOSTIC: "تشخیصی",
    InterventionType.MOCK_EXAM: "آزمون آزمایشی",
    InterventionType.PREREQUISITE_REVIEW: "مرور پیش‌نیاز",
    InterventionType.ERROR_REVIEW: "بازبینی خطاها",
}


class TaskType(str, Enum):
    TEST_SESSION = "test_session"
    REVIEW_SESSION = "review_session"
    READ_LESSON = "read_lesson"
    ERROR_REVIEW = "error_review"
    ACTIVE_RECALL = "active_recall"
    GOAL_TASK = "goal_task"
    EXAM_PREP = "exam_prep"
    MOCK_RETAKE = "mock_retake"
    OTHER = "other"


TASK_TYPE_LABELS_FA = {
    TaskType.TEST_SESSION: "جلسه تست",
    TaskType.REVIEW_SESSION: "جلسه مرور",
    TaskType.READ_LESSON: "مطالعه درس",
    TaskType.ERROR_REVIEW: "بازبینی خطا",
    TaskType.ACTIVE_RECALL: "یادآوری فعال",
    TaskType.GOAL_TASK: "کار هدف",
    TaskType.EXAM_PREP: "آماده‌سازی امتحان",
    TaskType.MOCK_RETAKE: "تکرار آزمون آزمایشی",
    TaskType.OTHER: "سایر",
}


class TaskStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    DEFERRED = "deferred"
    MISSED = "missed"
    CANCELLED = "cancelled"


class TaskSource(str, Enum):
    PLANNER = "planner"
    MANUAL = "manual"
    IMPORTED = "imported"
    RECURRING = "recurring"


class ActivityCategory(str, Enum):
    SPORT = "sport"
    GYM = "gym"
    WORK = "work"
    APPOINTMENT = "appointment"
    FAMILY = "family"
    SCHOOL = "school"
    COMMUTE = "commute"
    REST = "rest"
    TRAVEL = "travel"
    CLASS = "class"
    OTHER = "other"


ACTIVITY_LABELS_FA = {
    ActivityCategory.SPORT: "ورزش",
    ActivityCategory.GYM: "باشگاه",
    ActivityCategory.WORK: "کار",
    ActivityCategory.APPOINTMENT: "قرار/نوبت",
    ActivityCategory.FAMILY: "خانواده",
    ActivityCategory.SCHOOL: "مدرسه",
    ActivityCategory.COMMUTE: "مسیر رفت‌وآمد",
    ActivityCategory.REST: "استراحت",
    ActivityCategory.TRAVEL: "سفر",
    ActivityCategory.CLASS: "کلاس",
    ActivityCategory.OTHER: "سایر",
}


class SchedulingType(str, Enum):
    FIXED = "fixed"
    PREFERRED = "preferred"
    FLEXIBLE = "flexible"
    DEADLINE_ONLY = "deadline_only"


class ExamType(str, Enum):
    """V3.1 (doc 03): one unified exam model, five types.

    ``school`` and ``mock`` keep their V3 meaning so existing rows stay valid;
    ``personal``, ``checkup`` and ``comprehensive`` are additive.
    """

    PERSONAL = "personal"
    SCHOOL = "school"
    MOCK = "mock"
    CHECKUP = "checkup"
    COMPREHENSIVE = "comprehensive"


EXAM_TYPE_LABELS_FA = {
    ExamType.PERSONAL.value: "آزمون شخصی",
    ExamType.SCHOOL.value: "آزمون مدرسه",
    ExamType.MOCK.value: "آزمون آزمایشی",
    ExamType.CHECKUP.value: "چکاپ",
    ExamType.COMPREHENSIVE.value: "جامع",
}

EXAM_TYPE_HINTS_FA = {
    ExamType.PERSONAL.value: "خودت سؤال می‌گذاری و خودت تصحیح می‌کنی.",
    ExamType.SCHOOL.value: "آزمون رسمی مدرسه با تاریخ مشخص.",
    ExamType.MOCK.value: "آزمون آزمایشی؛ می‌تواند چند درس داشته باشد و برای نوبت بعد نگه داشته شود.",
    ExamType.CHECKUP.value: "پوشش چند مبحث پیوسته (از چکاپ قبلی تا این چکاپ)؛ آزمون یک مبحث تکی نیست.",
    ExamType.COMPREHENSIVE.value: "پوشش چند فصل/کتاب به‌عنوان جمع‌بندی.",
}


class ExamStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TopicMarkKind(str, Enum):
    PLANNED = "planned"
    ACTUAL = "actual"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    ACHIEVED = "achieved"
    MISSED = "missed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    MISSED = "missed"


class ReviewReason(str, Enum):
    WRONG = "wrong"
    UNANSWERED = "unanswered"
    CRITICAL = "critical"
    TAUGHT_NO_PRACTICE = "taught_no_practice"
    EXAM_FOCUS = "exam_focus"
    MOCK_FOCUS = "mock_focus"
    ERROR_REVIEW = "error_review"


class ReviewItemState(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DEFERRED = "deferred"


class RecommendationStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    INCREASED = "increased"
    DECREASED = "decreased"
    REJECTED = "rejected"
    CONVERTED = "converted_to_task"
    EXPIRED = "expired"


class PlanScope(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    EXAM = "exam"
    MOCK = "mock"
    TOPIC = "topic"


class PlanningStatus(str, Enum):
    INTERVIEW = "interview"
    PRIORITIES = "priorities"
    ADAPTIVE_QUESTIONS = "adaptive_questions"
    GENERATING = "generating"
    READY = "ready"
    FINALIZED = "finalized"
    DISCARDED = "discarded"


class CheckinPhase(str, Enum):
    START = "start"
    END = "end"


class SourceChannel(str, Enum):
    SYSTEM = "system"
    USER = "user"
    OBSERVED = "observed"
    SELF_REPORT = "self_report"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ErrorCategory(str, Enum):
    """Error taxonomy - inferred only when evidence supports it (V3)."""

    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"
    CALCULATION = "calculation"
    CARELESS = "careless"
    MISREAD = "misread"
    TIME_PRESSURE = "time_pressure"
    MEMORY = "memory"
    UNKNOWN = "unknown"
    GUESS = "guess"


ERROR_CATEGORY_LABELS_FA = {
    ErrorCategory.CONCEPTUAL: "مفهومی",
    ErrorCategory.PROCEDURAL: "رویهای",
    ErrorCategory.CALCULATION: "محاسباتی",
    ErrorCategory.CARELESS: "بی‌دقتی",
    ErrorCategory.MISREAD: "بدفهمی صورت سؤال",
    ErrorCategory.TIME_PRESSURE: "کمبود زمان",
    ErrorCategory.MEMORY: "حافظه/یادآوری",
    ErrorCategory.UNKNOWN: "نامشخص",
    ErrorCategory.GUESS: "حدس",
}


class RecalcScope(str, Enum):
    QUESTION = "question"
    TOPIC = "topic"
    BOOK = "book"
    USER = "user"
    ANSWER_KEY = "answer_key"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
