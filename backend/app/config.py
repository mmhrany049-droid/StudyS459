"""SS459 — پیکربندی مرکزی.

تمام اعداد و وزن‌های قطعی از مستندات (به‌ویژه 14_NUMERIC_ALGORITHMS_REFERENCE و
اسناد V2/V2.1) برداشته شده‌اند. هیچ عددی در جای دیگری hard-code نشود.
"""

# ----------------------------- Reward / Coins -----------------------------
WAKE_UP_DEADLINE_HOUR = 7
WAKE_UP_DEADLINE_MINUTE = 0
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

# ----------------------------- Review ------------------------------------
REVIEW_MAX_QUESTIONS_PER_SESSION = 25
REVIEW_MIN_CLUSTER_SIZE = 8
REVIEW_CRITICAL_WRONG_COUNT = 2
REVIEW_CRITICAL_MAX_DAYS = 2
REVIEW_NORMAL_MAX_DAYS = 3

# ----------------------- Planning weights (sum = 100) --------------------
WEIGHT_TOPIC_GOAL = 35
WEIGHT_REVIEW_CRITICAL = 25
WEIGHT_CLASS_ALIGNMENT = 15
WEIGHT_PARITY_OPPOSITE = 10
WEIGHT_DEADLINE = 10
WEIGHT_COUNT_GOAL = 5
CLASS_DAY_BONUS = 15

# ----------------------------- Capacity ----------------------------------
DEFAULT_SLEEP_HOUR = 23
DEFAULT_SLEEP_MINUTE = 30
DEFAULT_PERSONAL_TIME_MINUTES = 45
DEFAULT_SCHOOL_END_HOUR = 13
DEFAULT_SCHOOL_END_MINUTE = 30
NO_SCHOOL_CAPACITY_MULTIPLIER = 1.35
NO_SCHOOL_MIN_CAPACITY_MINUTES = 180

# ----------------------------- Weekly ------------------------------------
# هفته شنبه‌محور: شنبه=0 ... چهارشنبه=4، پنج‌شنبه=5، جمعه=6
MIDWEEK_CHECK_DAY = 4  # چهارشنبه
MIDWEEK_PROGRESS_THRESHOLD = 0.50
CATCHUP_GOAL_WEIGHT_MULTIPLIER = 1.5

# ----------------------------- Test engine -------------------------------
DEFAULT_FIRST_PARITY = "odd"
# کاهش تدریجی time limit در Timed
TIME_ADJUST_MIN_ATTEMPTS = 20
TIME_ADJUST_MIN_ACCURACY = 0.75
TIME_ADJUST_FACTOR = 0.8
TIME_ADJUST_MIN_SECONDS = 60

# ----------------------------- Habits / V2.1 ------------------------------
HABIT_LEARNING_DAYS = 30
SESSION_BLOCK_MIN_MINUTES = 60
SESSION_BLOCK_MAX_MINUTES = 120
# ظرفیت تخمینی روز پیش‌فرض (تعداد کار) قبل از داده کافی
DEFAULT_DAILY_TASK_CAPACITY = 3
# تغییر تدریجی ظرفیت در حلقه تطبیق (حداکثر ±۱۰٪ در هر به‌روزرسانی)
CAPACITY_ADJUST_STEP = 0.10
CAPACITY_MIN_TASKS = 1
CAPACITY_MAX_TASKS = 12

# --------------------- Personality / Confidence (V2.1) --------------------
# هر پاسخ منفرد ویژگی را قطعی نمی‌کند: حرکت جزئی ارزش + افزایش پله‌ای confidence
PERSONALITY_VALUE_STEP = 0.35      # نرخ حرکت به سمت شاهد پاسخ
PERSONALITY_CONFIDENCE_STEP = 0.08
PERSONALITY_CONFIDENCE_MAX = 0.95
PERSONALITY_CONFIDENCE_MIN_EVIDENCE = 1
# ۳ مشاهده نباید مثل ۳۰ مشاهده اعتبار داشته باشد
EVIDENCE_CONFIDENCE_SATURATION = 30

# ----------------------------- General ------------------------------------
TIMEZONE = "Asia/Tehran"
WEEK_START_DAY = 5  # شنبه = Saturday (weekday() در پایتون: دوشنبه=0 ... یکشنبه=6)
AUTHORIZATION_CODE = 459
DB_PATH = "data/study.db"
