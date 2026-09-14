import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchBookTopics,
  fetchOverview,
  fetchTrends,
  fetchWeaknesses,
} from "@/api/analytics";
import { MetricBar } from "@/features/progress";
import type {
  Overview,
  TopicRow,
  TrendPoint,
  Weakness,
} from "@/types/analytics";

function TrendChart({ points }: { points: TrendPoint[] }) {
  const max = Math.max(1, ...points.map((p) => p.volume));
  return (
    <div className="flex h-28 items-end gap-1" dir="ltr">
      {points.map((p) => (
        <div
          key={p.period_start}
          className="flex-1 rounded-t bg-sky-500/80"
          style={{ height: `${Math.max(p.volume > 0 ? 8 : 2, (p.volume / max) * 100)}%` }}
          title={`${p.period_start}: حجم ${p.volume}، دقت ${p.accuracy === null ? "—" : Math.round(p.accuracy * 100) + "٪"}`}
        />
      ))}
    </div>
  );
}

function TopicTable({ topics }: { topics: TopicRow[] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-right text-xs text-slate-500">
          <th className="py-2">مبحث</th>
          <th>پوشش</th>
          <th>دقت</th>
          <th>حجم</th>
          <th>غلط/نزده</th>
        </tr>
      </thead>
      <tbody>
        {topics.map((t) => (
          <tr key={t.node_id} className="border-t border-slate-100">
            <td className="py-2">
              <span style={{ paddingRight: t.depth * 16 }}>
                {t.is_leaf ? "• " : "▸ "}
                {t.title}
              </span>
            </td>
            <td className="w-28 px-2">
              <MetricBar label="" value={t.coverage} barClass="bg-emerald-500" />
            </td>
            <td className="w-28 px-2">
              <MetricBar label="" value={t.accuracy} barClass="bg-sky-500" />
            </td>
            <td className="text-center tabular-nums">{t.volume}</td>
            <td className="text-center tabular-nums">
              {t.wrong}/{t.unanswered}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Progress() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [bookId, setBookId] = useState<number | null>(null);
  const [topics, setTopics] = useState<TopicRow[]>([]);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [weak, setWeak] = useState<Weakness[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchOverview(), fetchTrends(30, "day"), fetchWeaknesses(10)])
      .then(([ov, tr, w]) => {
        setOverview(ov);
        setTrends(tr.points);
        setWeak(w.items);
        if (ov.books.length > 0) setBookId(ov.books[0].book_id);
      })
      .catch(() => setError("خطا در دریافت آمار پیشرفت."));
  }, []);

  useEffect(() => {
    if (bookId === null) return;
    fetchBookTopics(bookId)
      .then((b) => setTopics(b.topics))
      .catch(() => setError("خطا در دریافت جدول مباحث."));
  }, [bookId]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!overview) return <p>در حال بارگذاری…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">پیشرفت</h1>

      {/* Overview cards */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <p className="text-xs text-slate-500">آزمون‌های تمام‌شده</p>
          <p className="text-2xl font-bold tabular-nums">{overview.sessions_completed}</p>
        </div>
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <p className="text-xs text-slate-500">حجم پاسخ (کتاب‌های فعال)</p>
          <p className="text-2xl font-bold tabular-nums">{overview.volume}</p>
        </div>
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <p className="text-xs text-slate-500">پوشش کلی</p>
          <MetricBar label="" value={overview.coverage} barClass="bg-emerald-500" />
        </div>
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <p className="text-xs text-slate-500">دقت کلی</p>
          <MetricBar label="" value={overview.accuracy} barClass="bg-sky-500" />
        </div>
      </div>

      {/* Per-book topic table */}
      <section className="rounded-lg bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center gap-3">
          <h2 className="font-bold">پیشرفت مباحث</h2>
          <select
            value={bookId ?? ""}
            onChange={(e) => setBookId(Number(e.target.value))}
            className="rounded border border-slate-300 px-2 py-1"
          >
            {overview.books.map((b) => (
              <option key={b.book_id} value={b.book_id}>
                {b.title}
                {b.active ? "" : " (غیرفعال)"}
              </option>
            ))}
          </select>
        </div>
        {topics.length === 0 ? <p className="text-sm text-slate-500">مبحثی ثبت نشده.</p> : <TopicTable topics={topics} />}
      </section>

      {/* Trends */}
      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-bold">روند ۳۰ روز اخیر (حجم روزانه)</h2>
        <TrendChart points={trends} />
      </section>

      {/* Weaknesses */}
      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-bold">نقاط ضعف</h2>
        {weak.length === 0 ? (
          <p className="text-sm text-slate-500">هنوز داده‌ای برای تحلیل ضعف وجود ندارد.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {weak.map((w) => (
              <li key={w.node_id} className="flex items-center justify-between py-2">
                <div>
                  <p className="font-medium">{w.title}</p>
                  <p className="text-xs text-slate-500">{w.path}</p>
                </div>
                <div className="text-left text-xs text-slate-600 tabular-nums">
                  <p>غلط {w.wrong} / نزده {w.unanswered} / حجم {w.volume}</p>
                  <p>نمره ضعف: {Math.round(w.score * 100)}٪</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Link to="/" className="text-sm text-sky-700 underline">
        بازگشت به خانه
      </Link>
    </div>
  );
}
