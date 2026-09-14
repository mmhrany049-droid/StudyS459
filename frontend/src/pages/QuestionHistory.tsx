import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchQuestionHistory } from "@/api/analytics";
import type { QuestionHistory as History } from "@/types/analytics";

const RESULT_FA: Record<string, string> = {
  correct: "درست",
  wrong: "غلط",
};

export default function QuestionHistory() {
  const { id } = useParams<{ id: string }>();
  const [history, setHistory] = useState<History | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchQuestionHistory(Number(id))
      .then(setHistory)
      .catch(() => setError("سؤال یافت نشد."));
  }, [id]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!history) return <p>در حال بارگذاری…</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">
        {history.test_set_title} — سؤال {history.sequence_no}
      </h1>
      <div className="flex flex-wrap gap-3 text-sm">
        <span className="rounded bg-emerald-100 px-2 py-1">درست: {history.correct}</span>
        <span className="rounded bg-red-100 px-2 py-1">غلط: {history.wrong}</span>
        <span className="rounded bg-slate-200 px-2 py-1">نزده: {history.unanswered}</span>
        <span className="rounded bg-amber-100 px-2 py-1">در انتظار تصحیح: {history.pending}</span>
      </div>
      <p className="text-sm text-slate-600">
        مباحث: {history.topics.map((t) => t.title).join("، ") || "—"}
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-right text-xs text-slate-500">
            <th className="py-2">آزمون</th>
            <th>پاسخ</th>
            <th>نتیجه</th>
            <th>زمان</th>
          </tr>
        </thead>
        <tbody>
          {history.attempts.map((a, i) => (
            <tr key={i} className="border-t border-slate-100">
              <td className="py-2">
                <Link to={`/test/${a.session_id}/result`} className="text-sky-700 underline">
                  آزمون {a.session_id}
                </Link>
              </td>
              <td>{a.answer ?? "—"}</td>
              <td>{a.result ? (RESULT_FA[a.result] ?? a.result) : "—"}</td>
              <td className="text-xs text-slate-500">
                {new Date(a.answered_at).toLocaleString("fa-IR")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Link to="/progress" className="text-sm text-sky-700 underline">
        بازگشت به پیشرفت
      </Link>
    </div>
  );
}
