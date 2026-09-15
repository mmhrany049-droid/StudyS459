import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { completeTask, fetchDay, patchTask, setOverride } from "@/api/planner";
import { createSession } from "@/api/tests";
import type { DayPlan, Task } from "@/types/planner";

const WEEKDAY_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"];

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function Today() {
  const [day, setDay] = useState(todayISO());
  const [plan, setPlan] = useState<DayPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [earned, setEarned] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = useCallback(async (d: string) => {
    setError(null);
    try {
      setPlan(await fetchDay(d));
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  }, []);

  useEffect(() => {
    void load(day);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const shift = (delta: number) => {
    const d = new Date(day);
    d.setDate(d.getDate() + delta);
    const iso = d.toISOString().slice(0, 10);
    setDay(iso);
    void load(iso);
  };

  const toggleOverride = async () => {
    if (!plan) return;
    try {
      await setOverride(
        plan.date,
        !plan.is_school_day,
        plan.is_school_day ? "مدرسه نمی‌روم" : "روز مدرسه",
      );
      await load(plan.date);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  const startTest = async (task: Task) => {
    if (!task.node_id || !task.question_count) return;
    try {
      const view = await createSession({
        node_id: task.node_id,
        count: task.question_count,
        sequence_from: task.sequence_from,
        sequence_to: task.sequence_to,
        parity: (task.parity as "odd" | "even" | "any") ?? "any",
        timed: false,
        task_id: task.id,
      });
      navigate(`/test/${view.session.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  const act = async (task: Task, action: "start" | "progress" | "complete") => {
    try {
      if (action === "start") {
        await startTest(task);
        return;
      }
      if (action === "progress") {
        await patchTask(task.id, { status: "in_progress" });
      } else {
        const done = await completeTask(task.id);
        if (done.points_earned !== null && done.points_earned !== undefined) {
          setEarned(
            done.points_earned > 0
              ? `🎉 «${task.title}» تمام شد — +${done.points_earned} امتیاز!`
              : `✅ «${task.title}» تمام شد.`,
          );
        }
      }
      await load(day);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  if (error) return <p className="text-red-600">{error}</p>;
  if (!plan) return <p>در حال بارگذاری…</p>;

  const pct = Math.min(100, (plan.workload_minutes / Math.max(1, plan.capacity_minutes)) * 100);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button type="button" onClick={() => shift(-1)} className="rounded bg-slate-200 px-2 py-1">→</button>
        <h1 className="text-xl font-bold">
          {WEEKDAY_FA[plan.weekday]} {plan.date}
        </h1>
        <button type="button" onClick={() => shift(1)} className="rounded bg-slate-200 px-2 py-1">←</button>
      </div>

      {earned && (
        <div className="rounded bg-amber-100 p-3 text-center font-bold text-amber-900">
          {earned}
        </div>
      )}

      <div className="rounded-lg bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between text-sm">
          <span>{plan.is_school_day ? "🏫 روز مدرسه" : "🏖️ روز آزاد"}</span>
          <button type="button" onClick={() => void toggleOverride()} className="rounded bg-slate-200 px-2 py-1 text-xs">
            {plan.is_school_day ? "مدرسه نمی‌روم" : "ثبت به‌عنوان روز مدرسه"}
          </button>
        </div>
        <div className="mt-2 flex justify-between text-xs text-slate-500">
          <span>ظرفیت: {plan.capacity_minutes} دقیقه</span>
          <span>بار کاری: {plan.workload_minutes} دقیقه</span>
        </div>
        {plan.schedules.length > 0 && (
          <p className="mt-1 text-xs text-slate-500">
            🏫 کلاس‌ها ({plan.scheduled_minutes}′):{" "}
            {plan.schedules.map((s) => `${s.title} ${s.start_time.slice(0, 5)}–${s.end_time.slice(0, 5)}`).join("، ")}
          </p>
        )}
        <div className="mt-1 h-2 overflow-hidden rounded bg-slate-200">
          <div
            className={plan.over_capacity ? "h-full bg-red-500" : "h-full bg-emerald-500"}
            style={{ width: `${pct}%` }}
          />
        </div>
        {plan.over_capacity && (
          <p className="mt-2 text-sm text-red-700">
            ⚠️ بار کاری از ظرفیت بیشتر است — چیزی حذف نمی‌شود؛ خودت جابه‌جا کن:
            {plan.workload.map((w) => ` ${w.title} (${w.estimated_minutes}′)`).join("،")}
          </p>
        )}
      </div>

      <div className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-bold">برنامه روز</h2>
        {plan.placements.length === 0 ? (
          <p className="text-sm text-slate-500">کاری برای این روز قرار داده نشده.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {plan.placements.map(({ task }) => (
              <li key={task.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                <span className="font-medium">{task.title}</span>
                <span className="text-xs text-slate-500">
                  {task.task_type === "test" ? "📝 تست" : task.task_type === "review" ? "🔁 مرور" : "📖 مطالعه"}
                  {" "}— {task.estimated_minutes}′
                </span>
                {task.is_overdue && <span className="text-xs text-red-600">⏰ عقب‌افتاده</span>}
                {task.status === "completed" ? (
                  <span className="text-green-700">✅</span>
                ) : (
                  <span className="flex gap-1">
                    {task.task_type === "test" && (
                      <button
                        type="button"
                        onClick={() => void act(task, "start")}
                        className="rounded bg-slate-900 px-2 py-0.5 text-white"
                      >
                        شروع تست
                      </button>
                    )}
                    {task.status === "planned" && (
                      <button
                        type="button"
                        onClick={() => void act(task, "progress")}
                        className="rounded bg-slate-200 px-2 py-0.5"
                      >
                        شروع کردم
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => void act(task, "complete")}
                      className="rounded bg-green-100 px-2 py-0.5 text-green-800"
                    >
                      تمام شد
                    </button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
