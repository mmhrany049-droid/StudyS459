/** Academic types — mirrors backend schemas/academic.py. */

export interface Schedule {
  id: number;
  schedule_type: "school" | "external";
  title: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  recurring: boolean;
  date: string | null;
  subject_id: number | null;
  node_id: number | null;
  source: string | null;
  duration_minutes: number;
}

export interface ClassSession {
  id: number;
  schedule_id: number | null;
  date: string;
  subject_id: number;
  subject_name: string;
  attended: boolean;
  notes: string | null;
}

export interface TaughtLesson {
  id: number;
  class_session_id: number | null;
  subject_id: number;
  subject_name: string;
  node_id: number | null;
  node_title: string | null;
  taught_at: string;
  duration_minutes: number;
  notes: string | null;
}

export interface Homework {
  id: number;
  source_type: string;
  title: string;
  subject_id: number;
  subject_name: string;
  node_id: number | null;
  node_title: string | null;
  due_at: string;
  estimated_minutes: number;
  priority: number;
  status: "pending" | "done" | "cancelled";
  task_id: number | null;
}

export interface ExamQuestion {
  sequence_no: number;
  question_id: number | null;
  topic_node_id: number | null;
  answer_key: string | null;
  user_answer: string | null;
  result: "correct" | "wrong" | "unanswered" | null;
}

export interface Exam {
  id: number;
  title: string;
  exam_type: string;
  provider: string | null;
  exam_date: string;
  total_questions: number | null;
  total_score: number | null;
  images_metadata: Record<string, unknown> | null;
  questions: ExamQuestion[];
}

export interface ExamAnalytics {
  exam_id: number;
  correct: number;
  wrong: number;
  unanswered: number;
  ungraded: number;
  unmapped: number;
  subjects: Array<{
    subject_id: number;
    subject_name: string;
    correct: number;
    wrong: number;
    unanswered: number;
  }>;
}
