import { api } from "./client";
import type { CandidateTask, GoalItemIn, WeekGoal } from "@/types/goals";

export function fetchWeekGoal(week: string): Promise<WeekGoal> {
  return api.get<WeekGoal>(`/goals/weeks/${week}`);
}

export function createWeekGoal(week: string, items: GoalItemIn[]): Promise<WeekGoal> {
  return api.post<WeekGoal>(`/goals/weeks/${week}`, { items });
}

export function patchGoal(
  goalId: number,
  payload: { items?: GoalItemIn[]; active?: boolean },
): Promise<WeekGoal> {
  return api.patch<WeekGoal>(`/goals/${goalId}`, payload);
}

export function fetchCandidates(goalId: number): Promise<{ goal_id: number; items: CandidateTask[] }> {
  return api.get<{ goal_id: number; items: CandidateTask[] }>(`/goals/${goalId}/candidate-tasks`);
}
