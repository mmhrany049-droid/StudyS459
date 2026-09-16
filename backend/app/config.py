"""
ثابت‌های مرکزی سیستم (منبع حقیقت: 14_NUMERIC_ALGORITHMS_REFERENCE.md)
هیچ عددی در کد hard-code نشود؛ همه از اینجا خوانده شوند.
"""
from pathlib import Path

APP_NAME = "SS459 — سیستم مدیریت و تحلیل مطالعه"
APP_VERSION = "2.2.0"
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = DATA_DIR / "storage"
DB_PATH = DATA_DIR / "ss459.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"
TIMEZONE = "Asia/Tehran"

# ---------------- Reward (V2) ----------------
WAKE_UP_DEADLINE_HOUR = 7
WAKE_UP_DEADLINE_MINUTE = 0
WAKE_UP_EARLY_HOUR = 6
WAKE_UP_EARLY_MINUTE = 45
WAKE_UP_LATE_LIMIT_HOUR = 7
WAKE_UP_LATE_LIMIT_MINUTE = 15
POINTS_WAKE_UP = 15
POINTS_WAKE_UP_EARLY_BONUS = 5
POINTS_COMPLETE_DAILY_TESTS = 40
POINTS_COMPLETE_TASK = 8
POINTS_CORRECT_ANSWER = 2
POINTS_SUCCESSFUL_REVIEW = 3
POINTS_DAILY_GOAL = 20
POINTS_WEEKLY_GOAL = 70
POINTS_STREAK_DAY = 10

# ---------------- Review (V2) ----------------
REVIEW_MAX_QUESTIONS_PER_SESSION = 25
REVIEW_MIN_CLUSTER_SIZE = 8
REVIEW_CRITICAL_WRONG_COUNT = 2
REVIEW_CRITICAL_MAX_DAYS = 2
REVIEW_NORMAL_MAX_DAYS = 3

# ---------------- Planning weights (sum = 100) ----------------
WEIGHT_TOPIC_GOAL = 35
WEIGHT_REVIEW_CRITICAL = 25
WEIGHT_CLASS_ALIGNMENT = 15
WEIGHT_PARITY_OPPOSITE = 10
WEIGHT_DEADLINE = 10
WEIGHT_COUNT_GOAL = 5
CLASS_DAY_BONUS = 15

# ---------------- Capacity ----------------
DEFAULT_SLEEP_HOUR = 23
DEFAULT_SLEEP_MINUTE = 30
DEFAULT_PERSONAL_TIME_MINUTES = 45
DEFAULT_SCHOOL_END_HOUR = 13
DEFAULT_SCHOOL_END_MINUTE = 30
NO_SCHOOL_CAPACITY_MULTIPLIER = 1.35
NO_SCHOOL_MIN_CAPACITY_MINUTES = 180

# ---------------- Weekly ----------------
MIDWEEK_CHECK_DAY_INDEX = 4          # شنبه=0 ... چهارشنبه=4
MIDWEEK_PROGRESS_THRESHOLD = 0.50
CATCHUP_GOAL_WEIGHT_MULTIPLIER = 1.5
DEFAULT_FIRST_PARITY = "odd"

# ---------------- Habit (V2) ----------------
HABIT_LEARNING_DAYS = 30
STUDY_BLOCK_MIN_MINUTES = 60
STUDY_BLOCK_MAX_MINUTES = 120

# ---------------- V2.2 ----------------
EXAM_IMAGE_MAX_BYTES = 5 * 1024 * 1024        # S12 — هر عکس تا ۵MB
EXAM_PDF_MAX_BYTES = 15 * 1024 * 1024         # S12 — PDF تا ۱۵MB
READINESS_LOW_COVERAGE_THRESHOLD = 0.30       # S6 — Coverage < ۳۰٪
READINESS_COUNTDOWN_DAYS = 14                 # S6 — حالت «۱۴ روز مانده»
READINESS_DEADLINE_BOOST_DAYS = 7
AUTOSAVE_EVERY_N_ANSWERS = 10                 # S2
TAUGHT_RECENT_DAYS = 2                        # S5 / post-teach 48h
TAUGHT_LOW_COVERAGE_THRESHOLD = 0.30
SUGGESTION_DEFAULT_LIMIT = 30

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_PDF_EXT = {".pdf"}
EXAM_FILE_KINDS = ("exam_paper", "answer_key_sheet")
QUESTION_TAGS = ("مفهومی", "محاسباتی", "حفظی", "ترکیبی")   # S7
