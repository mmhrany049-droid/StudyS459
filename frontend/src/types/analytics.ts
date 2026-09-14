/** Analytics types — mirrors backend schemas/analytics.py. */

export interface BookProgress {
  book_id: number;
  title: string;
  active: boolean;
  volume: number;
  correct: number;
  wrong: number;
  unanswered: number;
  pending: number;
  accuracy: number | null;
  coverage: number | null;
  last_activity: string | null;
}

export interface Overview {
  user_id: number;
  sessions_total: number;
  sessions_completed: number;
  volume: number;
  correct: number;
  wrong: number;
  unanswered: number;
  pending: number;
  accuracy: number | null;
  coverage: number | null;
  books: BookProgress[];
}

export interface TopicRow {
  node_id: number;
  book_id: number;
  parent_id: number | null;
  node_type: string;
  title: string;
  code: string;
  depth: number;
  path: string;
  is_leaf: boolean;
  total: number;
  attempted: number;
  volume: number;
  correct: number;
  wrong: number;
  unanswered: number;
  pending: number;
  coverage: number | null;
  accuracy: number | null;
  last_activity: string | null;
  last_parity: string | null;
}

export interface QuestionAttempt {
  session_id: number;
  answer: string | null;
  result: string | null;
  answered_at: string;
  response_time_seconds: number | null;
}

export interface QuestionHistory {
  question_id: number;
  book_id: number;
  test_set_id: number;
  test_set_title: string;
  sequence_no: number;
  difficulty: string | null;
  has_answer_key: boolean;
  topics: Array<{ node_id: number; title: string }>;
  sessions_count: number;
  attempt_count: number;
  correct: number;
  wrong: number;
  unanswered: number;
  pending: number;
  last_answer: string | null;
  last_result: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  attempts: QuestionAttempt[];
}

export interface TrendPoint {
  period_start: string;
  sessions: number;
  volume: number;
  correct: number;
  wrong: number;
  unanswered: number;
  accuracy: number | null;
}

export interface Weakness {
  node_id: number;
  book_id: number;
  title: string;
  path: string;
  node_type: string;
  is_leaf: boolean;
  volume: number;
  correct: number;
  wrong: number;
  unanswered: number;
  error_rate: number | null;
  last_activity: string | null;
  last_parity: string | null;
  score: number;
}
