export type Book = {
  id: number;
  title: string;
  publisher: string;
  subject: string;
  subject_id: number;
  color: string;
  active: boolean;
  has_difficulty_levels: boolean;
  chapters: number;
  total_questions: number;
  coverage: number;
  accuracy: number;
};

export type NodeStats = {
  total: number;
  with_answer_key: number;
  attempted: number;
  coverage: number;
  accuracy: number;
  open_review: number;
};

export type TreeNode = {
  id: number;
  title: string;
  node_type: string;
  order_index: number;
  has_test_set: boolean;
  test_set_id: number | null;
  stats?: NodeStats;
  children: TreeNode[];
};

export type BankQuestion = {
  id: number;
  sequence_no: number;
  answer_key: number | null;
  difficulty_level: number | null;
  question_tag: string | null;
  archived: boolean;
  attempt_count: number;
  last_result: string | null;
  wrong_count: number;
  unanswered_count: number;
};

export type BankData = {
  node_id: number;
  node_title: string;
  test_set_id: number | null;
  summary: {
    total: number;
    with_answer_key: number;
    missing_answer_key: number;
    attempted: number;
    coverage: number;
    accuracy: number;
    open_review: number;
  };
  questions: BankQuestion[];
};

export type SheetGroup = {
  test_set_id: number;
  node_id: number;
  title: string;
  short_title: string;
  questions: { id: number; sequence_no: number; answer_key: number | null; attempt_count: number }[];
};

export type AnswerSheet = {
  book: { id: number; title: string; publisher: string };
  total_questions: number;
  groups: SheetGroup[];
};

export type Task = {
  id: number;
  title: string;
  task_type: string;
  subject: string | null;
  subject_color: string;
  book_id: number | null;
  node_id: number | null;
  node_title: string | null;
  source_type: string;
  priority: number;
  quantity: number;
  estimated_minutes: number;
  parity: string;
  planned_date: string;
  planned_date_jalali: string;
  planned_time: string | null;
  due_at: string | null;
  due_at_jalali: string | null;
  status: string;
  recommendation_reason: string;
  manual_override: boolean;
};

export type DayInfo = {
  date: string;
  jalali: string;
  jalali_long: string;
  weekday: string;
  weekday_index: number;
};

export type Capacity = DayInfo & {
  is_school_day: boolean;
  overridden: boolean;
  capacity_minutes: number;
  planned_minutes: number;
  remaining_minutes: number;
  over_capacity: boolean;
  suggested_blocks: number;
  classes: { id: number; title: string; subject_id: number | null; start_time: string | null; end_time: string | null }[];
};

export type Dashboard = {
  user: { display_name: string; grade: string; track: string; season_mode: string };
  today: DayInfo;
  week: { start: string; end: string; label: string };
  tasks: { total: number; done: number; pending: number };
  attempts: { today: number; week: number; total: number };
  quality: { correct: number; wrong: number; unanswered: number; accuracy: number };
  review: { open: number; due: number };
  rewards: {
    coins: number;
    today_points: number;
    week_points: number;
    current_streak: number;
    longest_streak: number;
    wake_up_today: boolean;
    wake_up_time: string | null;
    badges: { title: string; earned_at: string }[];
  };
  capacity: Capacity;
  state: { energy: number; focus: number; motivation: number; stress: number; fatigue: number; readiness: number; source: string; confidence: number; evidence_count: number };
  habit: { active_days: number; threshold: number; learning_phase: boolean; avg_tasks_school_day: number; avg_tasks_free_day: number; avg_session_minutes: number | null };
  habit_advice: string | null;
  taught_counts: Record<string, number>;
  taught_warnings: string[];
  exam_coverage_card: { items: { id: number; title: string; days_left: number; exam_date_jalali: string; avg_coverage: number; low_coverage_topics: number; topic_count: number }[] };
  upcoming_reminders: UpcomingExam[];
};

export type TaughtItem = {
  id: number;
  node_id: number;
  title: string;
  full_title: string;
  book_title: string;
  subject: string;
  taught_at: string;
  taught_at_jalali: string;
  days_since: number;
  fresh: boolean;
  source_type: string;
  notes: string;
  has_bank: boolean;
  total_questions: number;
  coverage: number;
  accuracy: number;
  open_review: number;
  untouched: number;
  status: string;
  status_label: string;
};

export type TaughtInsights = {
  items: TaughtItem[];
  warnings: string[];
  suggestions: { node_id: number; title: string; reason: string; suggested_count: number; priority: number }[];
  counts: Record<string, number>;
};

export type ExamListItem = {
  id: number;
  title: string;
  exam_kind: string;
  exam_type: string;
  provider: string;
  subject: string | null;
  exam_date: string;
  exam_date_jalali: string;
  total_questions: number;
  file_count: number;
  attempt_count: number;
  best_percentage: number | null;
  last_percentage: number | null;
};

export type ExamAttempt = {
  id: number;
  label: string;
  attempted_at: string;
  attempted_at_jalali: string;
  duration_minutes: number;
  correct: number;
  wrong: number;
  unanswered: number;
  percentage: number;
  notes: string;
};

export type ExamDetail = {
  id: number;
  title: string;
  exam_kind: string;
  exam_type: string;
  provider: string;
  subject_id: number | null;
  exam_date: string;
  exam_date_jalali: string;
  total_questions: number;
  notes: string;
  answer_key: { sequence_no: number; answer_key: number }[];
  files: { id: number; file_type: string; file_kind: string; original_name: string; size_bytes: number; url: string }[];
  sections: { id: number; subject_id: number; subject: string; sequence_from: number; sequence_to: number; duration_minutes: number | null }[];
  topic_map: { sequence_no: number; node_id: number; node_title: string }[];
  attempts: ExamAttempt[];
  progress: { points: { label: string; date_jalali: string; percentage: number; duration_minutes: number }[]; delta_percentage: number | null; delta_minutes: number | null };
  breakdown: {
    attempt_label?: string;
    per_subject: { subject_id: number; subject: string; range: number[]; correct: number; wrong: number; unanswered: number; percentage: number; duration_minutes: number | null }[];
    per_topic: { node_id: number; title: string; correct: number; wrong: number; unanswered: number; percentage: number }[];
  };
};

export type UpcomingExam = {
  id: number;
  title: string;
  exam_date: string;
  exam_date_jalali: string;
  days_left: number;
  countdown_mode: boolean;
  reminder: boolean;
  topic_count: number;
  notes: string;
};

export type ReadinessPlan = {
  upcoming_exam: { id: number; title: string; exam_date: string; exam_date_jalali: string; days_left: number };
  countdown_mode: boolean;
  topics_total: number;
  topics_low_coverage: number;
  low_coverage_ratio: number;
  total_suggested_tests: number;
  week_capacity_tests: number;
  capacity_warning: string | null;
  missing_bank: string[];
  today_capacity: Capacity;
  suggestions: {
    node_id: number;
    title: string;
    short_title: string;
    book_id: number;
    coverage: number;
    accuracy: number;
    open_review: number;
    unseen: number;
    suggested_count: number;
    parity: string;
    priority: number;
    reason: string;
  }[];
};

export type SessionData = {
  id: number;
  kind: string;
  timed: boolean;
  time_limit_seconds: number | null;
  parity: string;
  range: (number | null)[];
  status: string;
  node_title: string;
  questions: { question_id: number; sequence_no: number; difficulty_level: number | null; node_title: string }[];
};

export type SessionResult = {
  session_id: number;
  kind: string;
  total: number;
  correct: number;
  wrong: number;
  unanswered: number;
  accuracy: number;
  parity: string;
  range: (number | null)[];
  duration_minutes: number | null;
  points_awarded: number;
  items: { question_id: number; sequence_no: number | null; answer: number | null; result: string; answer_key: number | null }[];
};

export type Candidate = {
  node_id: number;
  book_id: number;
  book_title: string;
  subject_id: number;
  subject: string;
  title: string;
  full_title: string;
  score: number;
  parity: string;
  suggested_count: number;
  coverage: number;
  accuracy: number;
  untouched: number;
  open_review: number;
  reasons: string[];
};

export type ProgressData = {
  books: {
    book_id: number;
    title: string;
    subject: string;
    color: string;
    chapters: { node_id: number; title: string; total: number; attempted: number; coverage: number; accuracy: number; correct: number; wrong: number; unanswered: number; open_review: number }[];
    total: number;
    attempted: number;
    coverage: number;
    correct: number;
    wrong: number;
    unanswered: number;
    accuracy: number;
  }[];
  trend: { date_jalali: string; weekday: string; attempts: number }[];
  behavior: { task_completion_rate: number; skip_rate: number; average_session_minutes: number; manual_override_count: number; evidence_count: number; confidence: number };
};

export type ReviewQueueData = {
  total: number;
  items: {
    id: number;
    question_id: number;
    sequence_no: number | null;
    node_title: string;
    reason: string;
    wrong_count: number;
    unanswered_count: number;
    critical: boolean;
    scheduled_for_jalali: string;
    due: boolean;
  }[];
};

export type ScheduleItem = {
  id: number;
  title: string;
  subject_id: number | null;
  subject: string | null;
  day_of_week: number | null;
  day_name: string | null;
  start_time: string | null;
  end_time: string | null;
  source: string;
};

export type WeekView = {
  week_start: string;
  week_end: string;
  days: (DayInfo & { capacity: Capacity; tasks: Task[] })[];
};
