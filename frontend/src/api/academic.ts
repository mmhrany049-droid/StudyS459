import { api } from "./client";
import type {
  ClassSession,
  Exam,
  ExamAnalytics,
  Homework,
  Schedule,
  TaughtLesson,
} from "@/types/academic";

export function listSchedules(): Promise<Schedule[]> {
  return api.get<Schedule[]>("/schedules");
}

export function createSchedule(payload: Record<string, unknown>): Promise<Schedule> {
  return api.post<Schedule>("/schedules", payload);
}

export function listClassSessions(): Promise<ClassSession[]> {
  return api.get<ClassSession[]>("/class-sessions");
}

export function createClassSession(payload: Record<string, unknown>): Promise<ClassSession> {
  return api.post<ClassSession>("/class-sessions", payload);
}

export function listTaught(): Promise<TaughtLesson[]> {
  return api.get<TaughtLesson[]>("/taught-lessons");
}

export function createTaught(payload: Record<string, unknown>): Promise<TaughtLesson> {
  return api.post<TaughtLesson>("/taught-lessons", payload);
}

export function listHomework(status?: string): Promise<Homework[]> {
  return api.get<Homework[]>(status ? `/homework?status=${status}` : "/homework");
}

export function createHomework(payload: Record<string, unknown>): Promise<Homework> {
  return api.post<Homework>("/homework", payload);
}

export function patchHomework(
  homeworkId: number,
  payload: Record<string, unknown>,
): Promise<Homework> {
  return api.patch<Homework>(`/homework/${homeworkId}`, payload);
}

export function listExams(): Promise<Exam[]> {
  return api.get<Exam[]>("/exams");
}

export function createExam(payload: Record<string, unknown>): Promise<Exam> {
  return api.post<Exam>("/exams", payload);
}

export function getExam(examId: number): Promise<Exam> {
  return api.get<Exam>(`/exams/${examId}`);
}

export function addExamQuestions(
  examId: number,
  questions: Array<Record<string, unknown>>,
): Promise<Exam> {
  return api.post<Exam>(`/exams/${examId}/questions`, { questions });
}

export function getExamAnalytics(examId: number): Promise<ExamAnalytics> {
  return api.get<ExamAnalytics>(`/exams/${examId}/analytics`);
}
