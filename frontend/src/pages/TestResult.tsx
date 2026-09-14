import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getSession, submitCorrections } from "@/api/tests";
import type { SessionView } from "@/types/test";
import { parityLabel } from "@/features/tests";
import { cn } from "@/utils/cn";
import { formatMMSS, formatPercent } from "@/utils/format";

export default function TestResult() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);
  const [view, setView] = useState<SessionView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [correcting, setCorrecting] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!Number.isInteger(sessionId)) {
      setError("شناسه نشست نامعتبر است.");
      return;
    }
    try {
      setView(await getSession(sessionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const correct = async (questionId: number, result: "correct" | "wrong") => {
    setCorrecting(questionId);
    try {
      await submitCorrections(sessionId, [{ question_id: questionId, result }]);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    } finally {
      setCorrecting(null);
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
  if (!view) return <p className="text-sm text-slate-500">در حال بارگذاری…</p>;

  const { session, questions, result } = view;
  if (!result) {
    return (
      <div className="space-y-2">
        <p>این نشست هنوز تمام نشده است.</p>
        <Link to={`/test/${session.id}`} className="text-blue-700 hover:underline">
          ادامه نشست
        </Link>
      </div>
    );
  }

  const cells = [
    { label: "درست", value: result.correct, cls: "text-green-700" },
    { label: "غلط", value: result.wrong, cls: "text-red-700" },
    { label: "نزده", value: result.unanswered, cls: "text-slate-600" },
    { label: "در انتظار تصحیح", value: result.pending, cls: "text-amber-600" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">نتیجه تست</h1>
        <Link to="/test" className="rounded bg-slate-900 px-4 py-1 text-sm text-white">
          تست جدید
        </Link>
      </div>

      <div className="flex flex-wrap gap-2 text-sm">
        <span className="rounded bg-slate-200 px-2 py-1">
          {result.status === "completed" ? "✅ تکمیل‌شده" : "⏳ در انتظار تصحیح دستی"}
        </span>
        <span className="rounded bg-slate-200 px-2 py-1">زوج/فرد: {parityLabel(result.parity)}</span>
        {(result.sequence_from !== null || result.sequence_to !== null) && (
          <span className="rounded bg-slate-200 px-2 py-1">
            بازه: {result.sequence_from ?? "…"} تا {result.sequence_to ?? "…"}
          </span>
        )}
        <span className="rounded bg-slate-200 px-2 py-1">
          {result.timed ? `زمان‌دار (${(result.time_limit_seconds ?? 0) / 60} دقیقه)` : "بدون‌زمان"}
        </span>
        <span className="rounded bg-slate-200 px-2 py-1">مدت: {formatMMSS(result.duration_seconds)}</span>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {cells.map((c) => (
          <div key={c.label} className="rounded bg-white p-3 text-center shadow">
            <div className={cn("text-2xl font-bold", c.cls)}>{c.value}</div>
            <div className="text-xs text-slate-500">{c.label}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        <div className="rounded bg-white p-3 text-center shadow">
          <div className="text-xl font-bold">{formatPercent(result.accuracy)}</div>
          <div className="text-xs text-slate-500">دقت (بدون نزده و pending)</div>
        </div>
        <div className="rounded bg-white p-3 text-center shadow">
          <div className="text-xl font-bold">
            {result.average_response_time_seconds !== null
              ? `${Math.round(result.average_response_time_seconds)} ثانیه`
              : "—"}
          </div>
          <div className="text-xs text-slate-500">میانگین زمان پاسخ</div>
        </div>
        <div className="rounded bg-white p-3 text-center shadow">
          <div className="text-xl font-bold">{result.total}</div>
          <div className="text-xs text-slate-500">مجموع سؤال</div>
        </div>
      </div>

      <div className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 font-semibold">تفکیک مبحثی</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-right text-slate-500">
              <th className="py-1">مبحث</th>
              <th>کل</th>
              <th>درست</th>
              <th>غلط</th>
              <th>نزده</th>
              <th>pending</th>
            </tr>
          </thead>
          <tbody>
            {result.topic_breakdown.map((t) => (
              <tr key={t.node_id} className="border-t border-slate-100">
                <td className="py-1">{t.title}</td>
                <td className="text-center">{t.total}</td>
                <td className="text-center text-green-700">{t.correct}</td>
                <td className="text-center text-red-700">{t.wrong}</td>
                <td className="text-center">{t.unanswered}</td>
                <td className="text-center text-amber-600">{t.pending}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.difficulty_breakdown.length > 0 && (
        <div className="rounded bg-white p-4 shadow">
          <h2 className="mb-2 font-semibold">تفکیک دشواری</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-right text-slate-500">
                <th className="py-1">سطح</th>
                <th>کل</th>
                <th>درست</th>
                <th>غلط</th>
                <th>نزده</th>
                <th>pending</th>
              </tr>
            </thead>
            <tbody>
              {result.difficulty_breakdown.map((d, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="py-1">{d.difficulty ?? "—"}</td>
                  <td className="text-center">{d.total}</td>
                  <td className="text-center text-green-700">{d.correct}</td>
                  <td className="text-center text-red-700">{d.wrong}</td>
                  <td className="text-center">{d.unanswered}</td>
                  <td className="text-center text-amber-600">{d.pending}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 font-semibold">سؤال‌ها</h2>
        <ul className="space-y-1 text-sm">
          {questions.map((q) => (
            <li key={q.question_id} className="flex flex-wrap items-center gap-2 border-t border-slate-100 py-1">
              <span className="font-semibold">#{q.display_order}</span>
              <Link
                to={`/questions/${q.question_id}`}
                className="text-slate-500 hover:text-blue-700 hover:underline"
              >
                {q.test_set_title} — سؤال {q.sequence_no} (سابقه)
              </Link>
              <span>
                پاسخ شما: <strong>{q.answer ?? "نزده"}</strong>
              </span>
              {q.result === "correct" && <span className="text-green-700">✅ درست</span>}
              {q.result === "wrong" && <span className="text-red-700">❌ غلط</span>}
              {q.answer === null && <span className="text-slate-500">— نزده</span>}
              {q.answer !== null && q.result === null && (
                <span className="text-amber-600">⏳ در انتظار تصحیح (بدون کلید)</span>
              )}
              {q.answer !== null && q.result === null && result.status === "pending_correction" && (
                <span className="flex gap-1">
                  <button
                    type="button"
                    disabled={correcting === q.question_id}
                    onClick={() => void correct(q.question_id, "correct")}
                    className="rounded bg-green-100 px-2 py-0.5 text-green-800 disabled:opacity-50"
                  >
                    درست بود
                  </button>
                  <button
                    type="button"
                    disabled={correcting === q.question_id}
                    onClick={() => void correct(q.question_id, "wrong")}
                    className="rounded bg-red-100 px-2 py-0.5 text-red-800 disabled:opacity-50"
                  >
                    غلط بود
                  </button>
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
