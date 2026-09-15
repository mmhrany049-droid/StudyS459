/** Test Engine types — mirrors backend schemas/tests.py. */

export type Parity = "odd" | "even" | "any";
export type SessionStatus = "in_progress" | "pending_correction" | "completed";

export interface SessionCreate {
  node_id: number;
  count: number;
  sequence_from?: number | null;
  sequence_to?: number | null;
  parity: Parity;
  timed: boolean;
  time_limit_seconds?: number | null;
  task_id?: number | null;
}

export interface TopicRef {
  node_id: number;
  title: string;
}

export interface SessionQuestion {
  question_id: number;
  display_order: number;
  sequence_no: number;
  test_set_id: number;
  test_set_title: string;
  difficulty: string | null;
  topics: TopicRef[];
  answer: string | null;
  result: string | null;
  response_time_seconds: number | null;
  has_answer_key: boolean;
}

export interface TopicBreakdown {
  node_id: number;
  title: string;
  total: number;
  correct: number;
  wrong: number;
  unanswered: number;
  pending: number;
}

export interface DifficultyBreakdown {
  difficulty: string | null;
  total: number;
  correct: number;
  wrong: number;
  unanswered: number;
  pending: number;
}

export interface SessionResult {
  status: SessionStatus;
  total: number;
  correct: number;
  wrong: number;
  unanswered: number;
  pending: number;
  accuracy: number | null;
  duration_seconds: number | null;
  average_response_time_seconds: number | null;
  topic_breakdown: TopicBreakdown[];
  difficulty_breakdown: DifficultyBreakdown[];
  parity: Parity;
  sequence_from: number | null;
  sequence_to: number | null;
  timed: boolean;
  time_limit_seconds: number | null;
  started_at: string;
  ended_at: string | null;
  points_earned?: number | null;
}

export interface TestSession {
  id: number;
  user_id: number;
  task_id: number | null;
  timed: boolean;
  time_limit_seconds: number | null;
  sequence_from: number | null;
  sequence_to: number | null;
  parity: Parity;
  status: SessionStatus;
  started_at: string;
  ended_at: string | null;
  remaining_seconds: number | null;
  expired: boolean;
}

export interface SessionView {
  session: TestSession;
  questions: SessionQuestion[];
  result: SessionResult | null;
}

export interface ParityState {
  node_id: number;
  last_parity: Parity | null;
  last_used_at: string | null;
  suggested_parity: Parity | null;
}

export interface AnswerSubmit {
  question_id: number;
  answer: string | null;
  response_time_seconds?: number | null;
  client_attempt_id: string;
}

export interface RecordedAttempt {
  question_id: number;
  attempt_id: number;
  duplicate: boolean;
}

export interface CorrectionOut {
  session_id: number;
  status: SessionStatus;
  pending_remaining: number;
}

export interface InsufficientDetails {
  requested: number;
  available: number;
  available_odd: number;
  available_even: number;
  node_id: number;
  sequence_from: number | null;
  sequence_to: number | null;
  parity: Parity;
}
