import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { finishSession, getSession, submitAnswers } from "@/api/tests";
import { useCountdown, useElapsed } from "@/hooks/useCountdown";
import type { SessionView } from "@/types/test";
import { parityLabel } from "@/features/tests";
import { cn } from "@/utils/cn";
import { formatMMSS } from "@/utils/format";
import { newAttemptId } from "@/utils/uuid";

const OPTIONS = ["1", "2", "3", "4"];

export default function TestSession() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const sessionId = Number(id);
  const [view, setView] = useState<SessionView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [saving, setSaving] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const questionShownAt = useRef<number>(Date.now());

  const load = useCallback(async () => {
    if (!Number.isInteger(sessionId)) {
      setError("شناسه نشست نامعتبر است.");
      return;
    }
    try {
      const v = await getSession(sessionId);
      setView(v);
      if (v.result) navigate(`/test/${sessionId}/result`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  }, [sessionId, navigate]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    questionShownAt.current = Date.now();
  }, [index]);

  const session = view?.session ?? null;
  const questions = view?.questions ?? [];
  const current = questions[index] ?? null;

  const countdown = useCountdown(session?.timed ? (session.remaining_seconds ?? null) : null);
  const elapsed = useElapsed(!session?.timed && session?.status === "in_progress");

  // Timed out locally -> finalize on the server (server is the enforcer).
  useEffect(() => {
    if (session?.timed && countdown === 0 && session.status === "in_progress" && !finishing) {
      setFinishing(true);
      finishSession(sessionId)
        .then(() => navigate(`/test/${sessionId}/result`))
        .catch(() => navigate(`/test/${sessionId}/result`));
    }
  }, [countdown, session, finishing, sessionId, navigate]);

  const localAnswers = useRef<Record<number, string | null>>({});
  const [tick, setTick] = useState(0);

  const answerOf = (questionId: number): string | null => {
    if (questionId in localAnswers.current) return localAnswers.current[questionId];
    return questions.find((q) => q.question_id === questionId)?.answer ?? null;
  };

  const choose = async (questionId: number, answer: string | null) => {
    if (!session || session.status !== "in_progress" || saving) return;
    setSaving(true);
    const rt = Math.max(0, Math.round((Date.now() - questionShownAt.current) / 1000));
    try {
      await submitAnswers(session.id, [
        { question_id: questionId, answer, response_time_seconds: rt, client_attempt_id: newAttemptId() },
      ]);
      localAnswers.current[questionId] = answer;
      setTick((t) => t + 1);
    } catch (err) {
      if (err instanceof ApiError && err.code === "session_expired") {
        navigate(`/test/${session.id}/result`);
        return;
      }
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    } finally {
      setSaving(false);
    }
  };

  const finish = async () => {
    if (!session || finishing) return;
    if (!window.confirm("نشست به پایان برسد؟")) return;
    setFinishing(true);
    try {
      await finishSession(session.id);
      navigate(`/test/${session.id}/result`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
      setFinishing(false);
    }
  };

  if (error) {
    return (
      <div className="space-y-2">
        <Link to="/test" className="text-sm text-blue-700 hover:underline">→ تست جدید</Link>
        <p className="text-red-600">{error}</p>
      </div>
    );
  }
  if (!view || !session || !current) {
    return <p className="text-sm text-slate-500">در حال بارگذاری…</p>;
  }

  const answeredCount = questions.filter((q) => answerOf(q.question_id) !== null).length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-slate-600">
          سؤال {index + 1} از {questions.length} — پاسخ‌داده‌شده: {answeredCount} —{" "}
          {parityLabel(session.parity)}
          {session.sequence_from !== null && session.sequence_to !== null
            ? ` — بازه ${session.sequence_from} تا ${session.sequence_to}`
            : ""}
        </div>
        <div
          className={cn(
            "rounded px-3 py-1 font-mono text-lg",
            session.timed ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-700",
          )}
          title={session.timed ? "زمان باقی‌مانده" : "زمان سپری‌شده"}
        >
          {session.timed ? formatMMSS(countdown) : formatMMSS(elapsed)}
        </div>
      </div>

      <div className="h-2 overflow-hidden rounded bg-slate-200">
        <div
          className="h-full bg-blue-600"
          style={{ width: `${(answeredCount / questions.length) * 100}%` }}
        />
      </div>

      <div className="rounded bg-white p-4 shadow">
        <div className="mb-1 text-xs text-slate-500">
          {current.test_set_title} — سؤال {current.sequence_no}
          {current.difficulty ? ` — سطح ${current.difficulty}` : ""}
          {!current.has_answer_key && <span className="mr-2 text-amber-600">— بدون کلید (تصحیح دستی)</span>}
        </div>
        <h2 className="mb-4 text-lg font-bold">
          سؤال {current.display_order} <span className="text-sm font-normal text-slate-400">(متن سؤال در کتاب)</span>
        </h2>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4" key={tick}>
          {OPTIONS.map((opt) => {
            const mine = answerOf(current.question_id);
            return (
              <button
                key={opt}
                type="button"
                disabled={saving}
                onClick={() => void choose(current.question_id, opt)}
                className={cn(
                  "rounded border-2 px-4 py-3 text-xl font-bold disabled:opacity-50",
                  mine === opt
                    ? "border-blue-600 bg-blue-50 text-blue-800"
                    : "border-slate-200 hover:border-slate-400",
                )}
              >
                {opt}
              </button>
            );
          })}
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            disabled={saving || answerOf(current.question_id) === null}
            onClick={() => void choose(current.question_id, null)}
            className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50"
          >
            پاک کردن پاسخ (نزده)
          </button>
        </div>
        <div className="mt-2 text-xs text-slate-400">
          مباحث: {current.topics.map((t) => t.title).join("، ") || "—"}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <button
          type="button"
          disabled={index === 0}
          onClick={() => setIndex(index - 1)}
          className="rounded border border-slate-300 bg-white px-4 py-1 text-sm disabled:opacity-50"
        >
          قبلی
        </button>
        <button
          type="button"
          onClick={() => void finish()}
          disabled={finishing}
          className="rounded bg-green-700 px-6 py-2 text-white hover:bg-green-600 disabled:opacity-50"
        >
          {finishing ? "در حال اتمام…" : "پایان و تصحیح"}
        </button>
        <button
          type="button"
          disabled={index >= questions.length - 1}
          onClick={() => setIndex(index + 1)}
          className="rounded border border-slate-300 bg-white px-4 py-1 text-sm disabled:opacity-50"
        >
          بعدی
        </button>
      </div>

      <div className="flex flex-wrap gap-1">
        {questions.map((q, i) => (
          <button
            key={q.question_id}
            type="button"
            onClick={() => setIndex(i)}
            className={cn(
              "h-8 w-8 rounded text-sm",
              i === index
                ? "bg-slate-900 text-white"
                : answerOf(q.question_id) !== null
                  ? "bg-blue-100 text-blue-800"
                  : "bg-white text-slate-600",
            )}
          >
            {q.display_order}
          </button>
        ))}
      </div>
    </div>
  );
}
