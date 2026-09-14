import { api } from "./client";
import type { DayPlan, Task, WeekPlan } from "@/types/planner";

export interface TaskCreatePayload {
  task_type: "test" | "review" | "study";
  title: string;
  source_type?: string;
  source_id?: number | null;
  node_id?: number | null;
  question_count?: number | null;
  sequence_from?: number | null;
  sequence_to?: number | null;
  parity?: "odd" | "even" | "any" | null;
  priority?: number;
  estimated_minutes?: number;
  due_at?: string | null;
  recommendation_reason?: string | null;
}

export function createTask(payload: TaskCreatePayload): Promise<Task> {
  return api.post<Task>("/tasks", payload);
}

export function patchTask(
  taskId: number,
  payload: Record<string, unknown>,
): Promise<Task> {
  return api.patch<Task>(`/tasks/${taskId}`, payload);
}

export function completeTask(taskId: number): Promise<Task> {
  return api.post<Task>(`/tasks/${taskId}/complete`);
}

export function putPlacements(
  placements: Array<{ task_id: number; date: string; position?: number }>,
  dates?: string[],
): Promise<DayPlan[]> {
  return api.put<DayPlan[]>("/planner/placements", { placements, dates: dates ?? [] });
}

export function fetchDay(day: string): Promise<DayPlan> {
  return api.get<DayPlan>(`/planner/day/${day}`);
}

export function fetchWeek(week: string): Promise<WeekPlan> {
  return api.get<WeekPlan>(`/planner/week/${week}`);
}

export function setOverride(
  day: string,
  isSchoolDay: boolean,
  reason?: string,
): Promise<{ date: string; is_school_day: boolean; reason: string | null }> {
  return api.post("/school-day-overrides", {
    date: day,
    is_school_day: isSchoolDay,
    reason: reason ?? null,
  });
}
