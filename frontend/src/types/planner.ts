/** Planner types — mirrors backend schemas/planner.py. */

export type TaskType = "test" | "review" | "study";
export type TaskStatus = "planned" | "in_progress" | "completed" | "cancelled";

export interface Task {
  id: number;
  task_type: TaskType;
  title: string;
  source_type: string;
  source_id: number | null;
  node_id: number | null;
  question_count: number | null;
  sequence_from: number | null;
  sequence_to: number | null;
  parity: string | null;
  priority: number;
  estimated_minutes: number;
  due_at: string | null;
  status: TaskStatus;
  is_overdue: boolean;
  recommendation_reason: string | null;
  created_at: string;
  completed_at: string | null;
  placed_on: string | null;
}

export interface PlacedTask {
  position: number;
  task: Task;
}

export interface DayPlan {
  date: string;
  weekday: number;
  is_school_day: boolean;
  override: boolean;
  capacity_minutes: number;
  scheduled_minutes: number;
  workload_minutes: number;
  over_capacity: boolean;
  workload: Array<{ task_id: number; title: string; estimated_minutes: number }>;
  placements: PlacedTask[];
  schedules: Array<{
    id: number;
    schedule_type: string;
    title: string;
    start_time: string;
    end_time: string;
    duration_minutes: number;
  }>;
}

export interface WeekPlan {
  week_start: string;
  week_end: string;
  days: DayPlan[];
  unplaced: Task[];
  catch_up: Task[];
}
