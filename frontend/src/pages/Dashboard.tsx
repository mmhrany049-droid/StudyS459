import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchWeaknesses } from "@/api/analytics";
import { fetchWeekGoal } from "@/api/goals";
import { fetchDay, fetchWeek } from "@/api/planner";
import { fetchRewardsSummary } from "@/api/rewards";
import { useHealth } from "@/hooks/useHealth";
import type { Weakness } from "@/types/analytics";
import type { WeekGoal } from "@/types/goals";
import type { DayPlan, WeekPlan } from "@/types/planner";
import type { RewardsSummary } from "@/types/rewards";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function Card({ title, to, children }: { title: string; to: string; children: React.ReactNode }) {
  return (
    <section className="rounded bg-white p-4 shadow">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-semibold">{title}</h2>
        <Link to={to} className="text-sm text-blue-700 hover:underline">مشاهده ←</Link>
      </div>
      {children}
    </section>
  );
}

/** Dashboard: today strip, week goal, weaknesses, attention, rewards, health. */
export default function Dashboard() {
  const health = useHealth();
  const [rewards, setRewards] = useState<RewardsSummary | null>(null);
  const [day, setDay] = useState<DayPlan | null>(null);
  const [weekPlan, setWeekPlan] = useState<WeekPlan | null>(null);
  const [goal, setGoal] = useState<WeekGoal | null | undefined>(undefined);
  const [weak, setWeak] = useState<Weakness[]>([]);

  useEffect(() => {
    const today = todayISO();
    fetchRewardsSummary().then(setRewards).catch(() => undefined);
    fetchDay(today).then(setDay).catch(() => undefined);
    fetchWeek(today).then(setWeekPlan).catch(() => undefined);
    fetchWeekGoal(today).then(setGoal).catch(() => setGoal(null));
    fetchWeaknesses(3).then((w) => setWeak(w.items)).catch(() => undefined);
  }, []);

  const attention: string[] = [];
  if (!day) attention.push("…");
  else {
    if (day.over_capacity) attention.push(`امروز بیش‌ظرفیت: ${day.scheduled_minutes} از ${day.capacity_minutes} دقیقه`);
    const open = day.placements.filter((p) => p.task.status !== "completed").length;
    if (open > 0) attention.push(`${open} تسک باز امروز`);
  }
  if (weekPlan) {
    if (weekPlan.catch_up.length > 0) attention.push(`${weekPlan.catch_up.length} تسک عقب‌افتاده`);
    if (weekPlan.unplaced.length > 0) attention.push(`${weekPlan.unplaced.length} تسک بدون جای‌گذاری`);
  }
  if (goal === null) attention.push("هدف هفتگی تعریف نشده");
  const pills = attention.filter((a) => a !== "…");

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">داشبورد</h1>
      {rewards && (
        <Link
          to="/rewards"
          className="flex items-center justify-between rounded bg-white p-4 shadow hover:bg-slate-50"
        >
          <span className="text-lg font-bold tabular-nums">⭐ {rewards.total_points}</span>
          <span className="text-sm tabular-nums">🔥 {rewards.current_streak} روز</span>
          <span className="text-sm text-slate-600">
            🏅 {rewards.badges.slice(0, 2).map((b) => b.title).join("، ") || "بدون نشان"}
            {rewards.badge_count > 2 ? ` (+${rewards.badge_count - 2})` : ""}
          </span>
        </Link>
      )}

      {pills.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {pills.map((p) => (
            <span key={p} className="rounded-full bg-amber-100 px-3 py-1 text-sm text-amber-900">⚠ {p}</span>
          ))}
        </div>
      )}

      <Card title="امروز" to="/today">
        {!day && <p className="text-sm text-slate-500">در حال بارگذاری…</p>}
        {day && (
          <div className="text-sm">
            <p>
              {day.scheduled_minutes} از {day.capacity_minutes} دقیقه برنامه‌ریزی شده
              {day.over_capacity && <span className="font-bold text-red-600"> (بیش‌ظرفیت!)</span>}
            </p>
            <p className="text-slate-600">
              {day.placements.length} تسک قرارگرفته
              {day.is_school_day ? " • روز مدرسه" : " • روز آزاد"}
            </p>
          </div>
        )}
      </Card>

      <Card title="هدف هفته" to="/goals">
        {goal === undefined && <p className="text-sm text-slate-500">در حال بارگذاری…</p>}
        {goal === null && <p className="text-sm">هدفی برای این هفته ثبت نشده — <Link to="/goals" className="text-blue-700 hover:underline">بساز</Link></p>}
        {goal && (
          <ul className="space-y-1 text-sm">
            {goal.items.map((it) => (
              <li key={it.id} className="flex justify-between">
                <span>{it.title}</span>
                <span className="tabular-nums text-slate-600">
                  {it.progress.done ? "✅" : `${it.progress.attempted}/${it.progress.target}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="ضعیف‌ترین‌ها" to="/progress">
        {weak.length === 0 && <p className="text-sm text-slate-500">داده‌ای برای تحلیل ضعف نیست.</p>}
        {weak.length > 0 && (
          <ul className="space-y-1 text-sm">
            {weak.map((w) => (
              <li key={w.node_id} className="flex justify-between">
                <span className="truncate">{w.title}</span>
                <span className="shrink-0 tabular-nums text-slate-600">
                  خطا {w.error_rate === null ? "—" : `${Math.round(w.error_rate * 100)}٪`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 font-semibold">وضعیت اتصال به سرور</h2>
        {health.status === "loading" && <p>در حال بررسی…</p>}
        {health.status === "error" && (
          <p className="text-red-600">عدم اتصال به سرور: {health.message}</p>
        )}
        {health.status === "ok" && (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-slate-500">وضعیت</dt>
            <dd className="font-semibold text-green-700">{health.data.status}</dd>
            <dt className="text-slate-500">نسخه</dt>
            <dd>{health.data.version}</dd>
            <dt className="text-slate-500">محیط</dt>
            <dd>{health.data.env}</dd>
            <dt className="text-slate-500">منطقه زمانی</dt>
            <dd>{health.data.timezone}</dd>
          </dl>
        )}
      </div>
    </div>
  );
}
