import { useEffect, useState } from "react";
import {
  completeTask,
  createTask,
  fetchWeek,
  putPlacements,
} from "@/api/planner";
import type { Task, WeekPlan } from "@/types/planner";

const WEEKDAY_SHORT = ["د", "س", "چ", "پ", "ج", "ش", "ی"];

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function Week() {
  const [week, setWeek] = useState(todayISO());
  const [plan, setPlan] = useState<WeekPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [minutes, setMinutes] = useState("30");
  const [placeDay, setPlaceDay] = useState<Record<number, string>>({});

  const load = async (w: string) => {
    setError(null);
    try {
      setPlan(await fetchWeek(w));
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  useEffect(() => {
    void load(week);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addStudy = async () => {
    if (!title.trim()) return;
    try {
      await createTask({
        task_type: "study",
        title: title.trim(),
        estimated_minutes: Number(minutes) || 0,
      });
      setTitle("");
      await load(week);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  /** Place an unplaced task onto a day (keeps that day's other rows). */
  const place = async (task: Task, dayISO: string) => {
    if (!plan || !dayISO) return;
    try {
      const dayPlan = plan.days.find((d) => d.date === dayISO);
      const rows = (dayPlan?.placements ?? []).map((p, i) => ({
        task_id: p.task.id,
        date: dayISO,
        position: p.position ?? i,
      }));
      rows.push({ task_id: task.id, date: dayISO, position: rows.length });
      await putPlacements(rows, [dayISO]);
      await load(week);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  /** Move a placed task between days (resends both days' rows). */
  const move = async (task: Task, from: string, to: string) => {
    if (!plan || !to || from === to) return;
    try {
      const rows: Array<{ task_id: number; date: string; position: number }> = [];
      for (const d of [from, to]) {
        const dayPlan = plan.days.find((x) => x.date === d);
        let pos = 0;
        for (const p of dayPlan?.placements ?? []) {
          if (p.task.id === task.id) continue;
          rows.push({ task_id: p.task.id, date: d, position: pos++ });
        }
        if (d === to) rows.push({ task_id: task.id, date: to, position: pos });
      }
      await putPlacements(rows, [from, to]);
      await load(week);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  if (error) return <p className="text-red-600">{error}</p>;
  if (!plan) return <p>در حال بارگذاری…</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">هفته</h1>
        <input
          type="date"
          value={week}
          onChange={(e) => {
            setWeek(e.target.value);
            void load(e.target.value);
          }}
          className="rounded border border-slate-300 px-2 py-1"
        />
        <span className="text-sm text-slate-500">
          {plan.week_start} تا {plan.week_end}
        </span>
      </div>

      <div className="grid gap-2 md:grid-cols-7">
        {plan.days.map((d) => (
          <div key={d.date} className="rounded-lg bg-white p-2 shadow-sm">
            <p className="text-xs font-bold">
              {WEEKDAY_SHORT[d.weekday]} {d.date.slice(5)}
              {!d.is_school_day && " ☀️"}
            </p>
            <p className={`text-xs tabular-nums ${d.over_capacity ? "text-red-600" : "text-slate-500"}`}>
              {d.workload_minutes}/{d.capacity_minutes}′
            </p>
            <ul className="mt-1 space-y-1 text-xs">
              {d.placements.map(({ task }) => (
                <li key={task.id} className="rounded bg-slate-100 p-1">
                  <span className={task.status === "completed" ? "line-through" : ""}>
                    {task.title}
                  </span>
                  {task.status !== "completed" && (
                    <select
                      value=""
                      onChange={(e) => void move(task, d.date, e.target.value)}
                      className="mt-1 w-full rounded border border-slate-300 text-xs"
                    >
                      <option value="">انتقال…</option>
                      {plan.days.map((x) => (
                        <option key={x.date} value={x.date}>
                          {WEEKDAY_SHORT[x.weekday]} {x.date.slice(5)}
                        </option>
                      ))}
                    </select>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-lg bg-white p-4 shadow-sm">
          <h2 className="mb-2 font-bold">بدون قرار ({plan.unplaced.length})</h2>
          {plan.unplaced.length === 0 ? (
            <p className="text-sm text-slate-500">همه قرار گرفته‌اند.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {plan.unplaced.map((t) => (
                <li key={t.id} className="flex flex-wrap items-center gap-2">
                  <span>{t.title} ({t.estimated_minutes}′)</span>
                  <select
                    value={placeDay[t.id] ?? ""}
                    onChange={(e) => {
                      setPlaceDay({ ...placeDay, [t.id]: e.target.value });
                      void place(t, e.target.value);
                    }}
                    className="rounded border border-slate-300 px-1 py-0.5 text-xs"
                  >
                    <option value="">قرار در…</option>
                    {plan.days.map((x) => (
                      <option key={x.date} value={x.date}>
                        {WEEKDAY_SHORT[x.weekday]} {x.date.slice(5)}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => void completeTask(t.id).then(() => load(week))}
                    className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-800"
                  >
                    تمام شد
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex gap-2">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="کار مطالعاتی جدید…"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <input
              type="number"
              value={minutes}
              onChange={(e) => setMinutes(e.target.value)}
              className="w-16 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <button
              type="button"
              onClick={() => void addStudy()}
              className="rounded bg-slate-900 px-3 py-1 text-sm text-white"
            >
              افزودن
            </button>
          </div>
        </section>

        <section className="rounded-lg bg-white p-4 shadow-sm">
          <h2 className="mb-2 font-bold">صف جبران (پنج‌شنبه/جمعه)</h2>
          {plan.catch_up.length === 0 ? (
            <p className="text-sm text-slate-500">کار بازی وجود ندارد. 🎉</p>
          ) : (
            <ol className="list-decimal space-y-1 pr-5 text-sm">
              {plan.catch_up.slice(0, 10).map((t) => (
                <li key={t.id}>
                  {t.title}
                  {t.is_overdue && <span className="text-red-600"> (عقب‌افتاده)</span>}
                  <span className="text-xs text-slate-500"> — {t.placed_on ?? "بدون قرار"}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
