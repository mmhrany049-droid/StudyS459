import { api } from "./client";
import type {
  Overview,
  QuestionHistory,
  TopicRow,
  TrendPoint,
  Weakness,
} from "@/types/analytics";

export function fetchOverview(): Promise<Overview> {
  return api.get<Overview>("/progress/overview");
}

export function fetchBookTopics(bookId: number): Promise<{ book_id: number; topics: TopicRow[] }> {
  return api.get<{ book_id: number; topics: TopicRow[] }>(`/progress/books/${bookId}`);
}

export function fetchQuestionHistory(questionId: number): Promise<QuestionHistory> {
  return api.get<QuestionHistory>(`/progress/questions/${questionId}`);
}

export function fetchTrends(
  days = 30,
  groupBy: "day" | "week" = "day",
): Promise<{ group_by: string; days: number; points: TrendPoint[] }> {
  return api.get<{ group_by: string; days: number; points: TrendPoint[] }>(
    `/analytics/trends?days=${days}&group_by=${groupBy}`,
  );
}

export function fetchWeaknesses(limit = 20): Promise<{ items: Weakness[] }> {
  return api.get<{ items: Weakness[] }>(`/analytics/weaknesses?limit=${limit}`);
}
