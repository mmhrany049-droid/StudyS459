import { api } from "./client";
import type { Badge, RewardEvent, RewardsSummary } from "@/types/rewards";

export function fetchRewardsSummary(): Promise<RewardsSummary> {
  return api.get<RewardsSummary>("/rewards/summary");
}

export function fetchRewardEvents(limit = 50): Promise<RewardEvent[]> {
  return api.get<RewardEvent[]>(`/rewards/events?limit=${limit}`);
}

export function fetchBadges(): Promise<Badge[]> {
  return api.get<Badge[]>("/rewards/badges");
}
