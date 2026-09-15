import { useEffect, useState } from "react";
import {
  fetchBadges,
  fetchRewardEvents,
  fetchRewardsSummary,
} from "@/api/rewards";
import type { Badge, RewardEvent, RewardsSummary } from "@/types/rewards";

export default function Rewards() {
  const [summary, setSummary] = useState<RewardsSummary | null>(null);
  const [badges, setBadges] = useState<Badge[]>([]);
  const [events, setEvents] = useState<RewardEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchRewardsSummary(), fetchBadges(), fetchRewardEvents(30)])
      .then(([s, b, e]) => {
        setSummary(s);
        setBadges(b);
        setEvents(e);
      })
      .catch(() => setError("خطا در دریافت جوایز."));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!summary) return <p>در حال بارگذاری…</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">جوایز</h1>

      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-white p-4 text-center shadow-sm">
          <p className="text-xs text-slate-500">امتیاز کل</p>
          <p className="text-2xl font-bold tabular-nums">⭐ {summary.total_points}</p>
        </div>
        <div className="rounded-lg bg-white p-4 text-center shadow-sm">
          <p className="text-xs text-slate-500">استمرار فعلی</p>
          <p className="text-2xl font-bold tabular-nums">🔥 {summary.current_streak} روز</p>
        </div>
        <div className="rounded-lg bg-white p-4 text-center shadow-sm">
          <p className="text-xs text-slate-500">رکورد استمرار</p>
          <p className="text-2xl font-bold tabular-nums">{summary.longest_streak} روز</p>
        </div>
      </div>

      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-bold">نشان‌ها ({summary.badge_count} از {badges.length})</h2>
        <ul className="grid gap-2 md:grid-cols-2">
          {badges.map((b) => (
            <li
              key={b.code}
              className={`rounded border p-2 text-sm ${b.earned ? "border-amber-300 bg-amber-50" : "border-slate-200 opacity-60"}`}
            >
              <p className="font-medium">
                {b.earned ? "🏅" : "🔒"} {b.title}
              </p>
              <p className="text-xs text-slate-500">{b.description}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-bold">تاریخچه امتیاز</h2>
        {events.length === 0 ? (
          <p className="text-sm text-slate-500">هنوز امتیازی کسب نشده.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {events.map((e) => (
              <li key={e.id} className="flex items-center justify-between py-1.5">
                <span>{e.description ?? e.event_type}</span>
                <span className="font-bold text-emerald-700 tabular-nums">+{e.points}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
