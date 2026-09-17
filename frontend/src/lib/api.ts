/** Thin API client. The UI never computes domain values on its own: every
 *  number, label and Persian date string comes from the backend services. */

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  details: unknown;
  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const error = body?.error;
    throw new ApiError(error?.message || "خطا در ارتباط با سرور", res.status, error?.details);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  // multipart upload: let the browser set the boundary, never force JSON
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form, headers: {} }),
};

// ---------------------------------------------------------------------------
// Shared response shapes (only the parts the UI reads)
// ---------------------------------------------------------------------------

export type BookStats = {
  topic_count?: number;
  question_count?: number;
  questions_with_answer_key?: number;
  questions_missing_answer_key?: number;
  taught_topics?: number;
};

export type Book = {
  id: number;
  stable_key?: string;
  title: string;
  subject?: string;
  publisher?: string;
  grade?: string;
  topic_count?: number;
  active?: boolean;
  hierarchy_note?: string;
  stats?: BookStats;
};

export type TopicNode = {
  id: number;
  title: string;
  node_type: string;
  depth: number;
  is_leaf: boolean;
  taught_state: "checked" | "unchecked" | "indeterminate";
  taught: boolean;
  direct_question_count?: number;
  total_questions?: number;
  metadata?: Record<string, unknown>;
  children: TopicNode[];
};

export type TreeResponse = {
  book: Book;
  topics: TopicNode[];
  stats: Record<string, number>;
};

export type Suggestion = {
  topic_id: number;
  topic_title: string;
  book_id?: number;
  score: number;
  confidence: number;
  taught?: boolean;
  suggested_intervention?: string;
  suggested_intervention_label?: string;
  short_reason?: string;
  exam_days?: number | null;
  why?: Explain;
};

export type Explain = {
  what: string;
  why: string;
  evidence?: Record<string, unknown>;
  what_can_i_change?: string[];
  confidence?: number;
  model_version?: string;
};

export type Dashboard = {
  today?: { date: string; date_long: string; weekday: string; is_school_day: boolean };
  what_matters_now?: { priorities: any[]; review?: { open?: number; due_today?: number; critical?: number } };
  what_next?: { tasks?: any[]; over_capacity?: boolean; capacity?: any };
  next_action?: Record<string, unknown> | null;
  why?: { suggestions: Suggestion[]; quiet: Suggestion[] };
  time?: {
    theoretical_minutes_today?: number | null;
    realistic_minutes_today?: number | null;
    planned_minutes_today?: number;
    explanation?: string;
    week?: Record<string, unknown>;
  };
  exams?: { upcoming?: unknown[] };
  goals?: unknown[];
  learning?: Record<string, unknown>;
  habits?: Record<string, unknown>;
  midweek?: Record<string, unknown> | null;
  checkin?: Record<string, unknown> | null;
  empty_state?: unknown;
};

export type TestQuestion = {
  question_id: number;
  sequence_no: number;
  difficulty_level?: number | null;
  has_answer_key?: boolean;
  topic_id?: number;
  topic_title?: string;
};

export type TestSession = {
  id: number;
  status: string;
  session_type?: string;
  questions: TestQuestion[];
  planned_duration_label?: string | null;
  planned_date_label?: string;
  states_summary?: Record<string, number>;
};

export type TaskRow = {
  id: number;
  title: string;
  task_type: string;
  intervention_type?: string | null;
  status: string;
  planned_date: string;
  planned_date_long?: string;
  planned_minutes?: number | null;
  duration_low?: number | null;
  duration_high?: number | null;
  duration_label?: string | null;
  parity?: string | null;
  sequence_from?: number | null;
  sequence_to?: number | null;
  manual_override?: boolean;
  override_reason?: string | null;
  priority_score?: number | null;
  topic_id?: number | null;
  topic_title?: string | null;
  source?: string;
  created_by?: string;
  evidence?: Record<string, unknown>;
};

export type PlanExplanation = {
  summary?: string;
  capacity_note?: string;
  exams?: { title: string; date: string; days_remaining?: number }[];
  goals?: { title: string }[];
  review_open?: number;
  overload?: { has_overload: boolean; days: { date: string; excess: number; suggestion: string }[] };
  what_can_i_change?: string[];
  no_magic?: string;
};

export type PlanningSession = {
  id: number;
  status: string;
  week_label?: string;
  interview?: Record<string, any>;
  explanation?: PlanExplanation;
  plan?: { days?: { date: string; date_label?: string; tasks: TaskRow[]; planned_minutes?: number }[] };
  overload?: PlanExplanation["overload"];
  suggestion_count?: number;
  question_count?: number;
  answered_count?: number;
};
