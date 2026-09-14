/** Goal types — mirrors backend schemas/goals.py. */

export type GoalType = "count" | "topic";

export interface GoalItemIn {
  goal_type: GoalType;
  target_value: number;
  subject_id?: number | null;
  book_id?: number | null;
  node_id?: number | null;
}

export interface ItemProgress {
  volume: number;
  attempted: number;
  pool_total: number;
  coverage: number | null;
  target: number;
  remaining: number;
  done: boolean;
}

export interface GoalItem {
  id: number;
  goal_type: GoalType;
  target_value: number;
  subject_id: number | null;
  book_id: number | null;
  node_id: number | null;
  title: string;
  progress: ItemProgress;
}

export interface WeekGoal {
  id: number;
  week_start: string;
  week_end: string;
  active: boolean;
  items: GoalItem[];
  sessions_in_week: number;
  week_volume_unique: number;
  week_attempted_unique: number;
}

export interface CandidateTask {
  kind: "test" | "review";
  sources: string[];
  source_item_ids: number[];
  node_id: number;
  book_id: number;
  title: string;
  path: string;
  suggested_count: number;
  suggested_parity: "odd" | "even" | "any";
  priority_score: number;
  recommendation_reason: string;
  pool_total: number;
  remaining_never: number;
  remaining_week: number;
  volume_week: number;
  weakness_score: number;
}
