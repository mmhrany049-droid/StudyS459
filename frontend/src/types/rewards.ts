/** Reward types — mirrors backend schemas/rewards.py. */

export interface Badge {
  code: string;
  title: string;
  description: string | null;
  earned: boolean;
  earned_at: string | null;
}

export interface RewardEvent {
  id: number;
  event_type: string;
  points: number;
  description: string | null;
  related_entity_type: string | null;
  related_entity_id: number | null;
  created_at: string;
}

export interface RewardsSummary {
  user_id: number;
  total_points: number;
  current_streak: number;
  longest_streak: number;
  badge_count: number;
  badges: Badge[];
  recent_events: RewardEvent[];
}
