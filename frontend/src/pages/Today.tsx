import { useEffect, useState } from "react";
import { api, TaskRow } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat } from "../components/ui";
import { faNumber, minutes, statusLabel, taskTypeLabel, toPersianDigits } from "../lib/format";

type TasksPayload = {
  date: string;
  date_long: string;
  weekday: string;
  tasks: TaskRow[];
  capacity: any;
  over_capacity: boolean;
};

export default function Today() {
  const [data, setData] = useState<TasksPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [finishId, setFinishId] = useState<number | null>(null);
  const [actualMinutes, setActualMinutes] = useState<string>("");
  const [recovery, setRecovery] = useState<any>(null);

  function load() {
    setError(null);
    api.get<TasksPayload>("/tasks").then(setData).catch((err) => setError(err.message));
    api.post<any>("/tasks/recovery", {}).then(setRecovery).catch(() => undefined);
  }
  useEffect(load, []);

  async function act(id: number, action: "complete" | "skip" | "uncomplete", minutes?: number) {
    setBusy(id);
    try {
      await api.post(`/tasks/${id}/${action}`, { actual_minutes: minutes });
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(null);
      setFinishId(null);
      setActualMinutes("");
    }
  }

  if (error) return <ErrorBox message={error} onRetry={load} />;
  if (!data) return <Spinner />;

  const capacity = data.capacity ?? {};
  const tasks = data.tasks ?? [];
  const remaining = tasks.filter((task) => task.status !== "completed" && task.status !== "skipped");

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="grid gap-5 lg:col-span-2">
        <Card title={`کارهای امروز — ${data.date_long ?? ""}`}>
          {tasks.length === 0 ? (
            <Empty
              title="برای امروز کاری نیست"
              hint="اگر برنامه هفته را ساخته‌ای، کارها به‌صورت خودکار در روزها پخش می‌شوند."
            />
          ) : (
            <ul className="grid gap-2">
              {tasks.map((task) => (
                <li key={task.id} className="rounded-xl border border-ink-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{task.title}</span>
                        {task.manual_override && <Badge tone="warn">دستی</Badge>}
                        <Badge tone="muted">{taskTypeLabel(task.task_type)}</Badge>
                      </div>
                      <div className="muted mt-0.5">
                        {task.duration_label || `${minutes(task.duration_low)} تا ${minutes(task.duration_high)}`}
                        {task.override_reason ? ` — ${task.override_reason}` : ""}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        tone={
                          task.status === "completed" ? "ok" : task.status === "skipped" ? "bad" : "muted"
                        }
                      >
                        {statusLabel(task.status)}
                      </Badge>
                      {task.status !== "completed" && (
                        <button
                          className="btn-primary btn-xs"
                          disabled={busy === task.id}
                          onClick={() => setFinishId(task.id)}
                        >
                          انجام شد
                        </button>
                      )}
                      {task.status === "completed" && (
                        <button
                          className="btn-ghost btn-xs"
                          disabled={busy === task.id}
                          onClick={() => act(task.id, "uncomplete")}
                        >
                          برگرداندن
                        </button>
                      )}
                      {task.status !== "completed" && task.status !== "skipped" && (
                        <button className="btn-ghost btn-xs" disabled={busy === task.id} onClick={() => act(task.id, "skip")}>
                          رد کردن
                        </button>
                      )}
                    </div>
                  </div>

                  {finishId === task.id && (
                    <div className="mt-3 rounded-xl bg-ink-50 p-3">
                      <label className="label">چند دقیقه طول کشید؟ (کاربر هیچ‌وقت زمان را از قبل حدس نمی‌زند)</label>
                      <div className="flex items-center gap-2">
                        <input
                          className="input max-w-[140px]"
                          inputMode="numeric"
                          value={actualMinutes}
                          onChange={(event) => setActualMinutes(event.target.value.replace(/[^0-9]/g, ""))}
                          placeholder="مثلاً 35"
                        />
                        <span className="muted">دقیقه</span>
                        <button
                          className="btn-primary btn-xs"
                          disabled={busy === task.id}
                          onClick={() => act(task.id, "complete", Number(actualMinutes) || undefined)}
                        >
                          ثبت
                        </button>
                        <button className="btn-ghost btn-xs" onClick={() => setFinishId(null)}>
                          انصراف
                        </button>
                      </div>
                      <p className="muted mt-2">اگر خالی بماند، برآورد بعدی از داده واقعی به‌روزرسانی می‌شود.</p>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="بازیابی کارهای عقب‌افتاده">
          {recovery && (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <Stat label="کار عقب‌افتاده" value={toPersianDigits(recovery.missed ?? 0)} />
                <Stat label="پیشنهاد جابه‌جایی" value={toPersianDigits((recovery.moves ?? []).length)} />
                <Stat label="حذف خودکار" value="هیچ" hint="کار عقب‌افتاده پاک نمی‌شود؛ فقط توزیع می‌شود." />
              </div>
              <p className="muted mt-3">{recovery.message}</p>
              {(recovery.moves ?? []).length > 0 && (
                <ul className="mt-3 grid gap-2 text-xs text-ink-600">
                  {(recovery.moves ?? []).slice(0, 5).map((move: any, index: number) => (
                    <li key={index} className="rounded-xl bg-ink-50 p-2">
                      {move.title ?? move.task_id} → {move.to_date ?? move.suggested_date}
                      {move.reason ? ` (${move.reason})` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          {!recovery && <p className="muted">در حال بررسی…</p>}
        </Card>

        <Card title="ظرفیت امروز">
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="واقع‌بینانه" value={minutes(capacity.realistic_minutes)} />
            <Stat label="وقت آزاد تقویمی" value={minutes(capacity.theoretical_minutes)} hint="وقت آزاد ≠ ظرفیت" />
            <Stat label="برنامه‌ریزی‌شده" value={minutes(capacity.planned_minutes)} />
            <Stat label="انجام‌شده" value={minutes(capacity.completed_minutes)} />
          </div>
          <p className="muted mt-3">{capacity.explanation}</p>
          {capacity.overloaded && (
            <p className="mt-2 rounded-xl bg-warn-100/70 p-3 text-xs text-warn-600">
              امروز بیش از ظرفیت واقع‌بینانه پر شده است. پیشنهاد جابه‌جایی داده می‌شود، ولی هیچ کاری خودکار حذف نمی‌شود.
            </p>
          )}
          <p className="muted mt-2">{capacity.overload_policy}</p>
        </Card>
      </div>

      <div className="grid gap-5">
        <Card title="خلاصه">
          <div className="grid gap-3">
            <Stat label="کار باقی‌مانده" value={toPersianDigits(remaining.length)} />
            <Stat label="نسبت بار به ظرفیت" value={faNumber((capacity.overload_ratio ?? 0) * 100, 0) + "٪"} />
            <Stat label="روز مدرسه" value={capacity.is_school_day ? "بله" : "خیر"} hint={capacity.school_source === "override" ? "بر اساس تغییر دستی" : undefined} />
          </div>
        </Card>
        <Card title="شکستن کار بزرگ">
          <p className="muted">
            کاری که از حد آستانه طولانی‌تر باشد پیشنهاد شکستن می‌گیرد؛ چون یک بلوک غیرواقعی باعث رهاکردن کار می‌شود.
          </p>
        </Card>
      </div>
    </div>
  );
}
