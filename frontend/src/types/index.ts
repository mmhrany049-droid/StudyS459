export interface User {
  id: number
  email: string
  username: string
  full_name?: string
  is_active: boolean
  created_at: string
}

export interface Subject {
  id: number
  stable_id: string
  name: string
  name_fa?: string
  color?: string
}

export interface Book {
  id: number
  stable_id: string
  subject_id: number
  title: string
  title_fa?: string
  publisher?: string
  hierarchy_config?: any
  is_active: boolean
  subject?: Subject
}

export interface BookNode {
  id: number
  book_id: number
  stable_id: string
  parent_id?: number
  node_type: string
  title: string
  title_fa?: string
  order_index: number
  level: number
  children: BookNode[]
}

export interface TestSet {
  id: number
  book_id: number
  stable_id: string
  node_id?: number
  title: string
  title_fa?: string
  test_type: string
  difficulty_level?: number
  is_comprehensive: boolean
  question_count: number
}

export interface Question {
  id: number
  book_id: number
  test_set_id?: number
  stable_id: string
  question_text?: string
  question_text_fa?: string
  image_url?: string
  option_a?: string
  option_b?: string
  option_c?: string
  option_d?: string
  correct_option?: string
  difficulty_level?: number
  is_concours: boolean
  concours_year?: number
  topic_node_ids: number[]
}

export interface TestSession {
  id: number
  user_id: number
  book_id?: number
  test_set_id?: number
  task_id?: number
  title?: string
  test_type: string
  status: string
  mode: string
  time_limit_seconds?: number
  elapsed_seconds?: number
  started_at: string
  finished_at?: string
  total_questions: number
  correct_count: number
  wrong_count: number
  unanswered_count: number
  questions: TestSessionQuestion[]
}

export interface TestSessionQuestion {
  id: number
  test_session_id: number
  question_id: number
  order_index: number
  user_answer?: string
  is_correct?: boolean
  is_answered: boolean
  answered_at?: string
  time_spent_seconds?: number
  question?: {
    id: number
    stable_id: string
    question_text?: string
    question_text_fa?: string
    image_url?: string
    option_a?: string
    option_b?: string
    option_c?: string
    option_d?: string
    difficulty_level?: number
    book_id: number
    test_set_id?: number
  }
}

export interface Task {
  id: number
  user_id: number
  title: string
  title_fa?: string
  description?: string
  source: string
  source_id?: number
  book_id?: number
  book_node_id?: number
  test_set_id?: number
  weekly_goal_id?: number
  task_type: string
  status: string
  priority: number
  estimated_duration_minutes: number
  reason?: string
  reason_structured?: string
  due_date?: string
  completed_at?: string
  book_title?: string
  node_title?: string
}

export interface DailyPlacement {
  id: number
  user_id: number
  task_id: number
  date: string
  day_of_week?: string
  order_index: number
  is_catchup: boolean
  task?: Task
}

export interface PlannerDay {
  date: string
  day_of_week: string
  is_catchup_day: boolean
  available_capacity_minutes: number
  planned_minutes: number
  is_over_capacity: boolean
  placements: DailyPlacement[]
}

export interface WeeklyGoal {
  id: number
  user_id: number
  week_start_date: string
  week_end_date: string
  test_count_goal?: number
  topic_goal_enabled: boolean
  status: string
  items: WeeklyGoalItem[]
  total_completed_tests: number
  progress_percent?: number
}

export interface WeeklyGoalItem {
  id: number
  weekly_goal_id: number
  book_id: number
  book_node_id?: number
  target_tests?: number
  completed_tests: number
  priority: number
  book_title?: string
  node_title?: string
}
