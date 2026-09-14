import { api } from "./client";
import type {
  AnswerSubmit,
  CorrectionOut,
  ParityState,
  RecordedAttempt,
  SessionCreate,
  SessionView,
} from "@/types/test";

export function createSession(payload: SessionCreate): Promise<SessionView> {
  return api.post<SessionView>("/test-sessions", payload);
}

export function getSession(sessionId: number): Promise<SessionView> {
  return api.get<SessionView>(`/test-sessions/${sessionId}`);
}

export function submitAnswers(
  sessionId: number,
  answers: AnswerSubmit[],
): Promise<{ attempts: RecordedAttempt[] }> {
  return api.post<{ attempts: RecordedAttempt[] }>(
    `/test-sessions/${sessionId}/answers`,
    { answers },
  );
}

export function finishSession(sessionId: number): Promise<SessionView> {
  return api.post<SessionView>(`/test-sessions/${sessionId}/finish`);
}

export function submitCorrections(
  sessionId: number,
  corrections: Array<{ question_id: number; result: "correct" | "wrong" }>,
): Promise<CorrectionOut> {
  return api.post<CorrectionOut>(`/test-sessions/${sessionId}/corrections`, {
    corrections,
  });
}

export function getParityState(nodeId: number): Promise<ParityState> {
  return api.get<ParityState>(`/nodes/${nodeId}/parity-state`);
}
