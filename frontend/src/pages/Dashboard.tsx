import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, Card, Chip, ErrorBox, Loading, Modal, Stat, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa, pct } from "../lib/api";
import type { Dashboard as D } from "../lib/types";

export default function Dashboard() {
  const { data, error, loading, reload } = useFetch<D>("/dashboard");
  const [checkIn, setCheckIn] = useState(false);

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const wakeUp = async () => {
    try {
      const r = await api.post<{ message: string; points: number }>("/rewards/wake-up", {});
      toast(r.message, r.points > 0 ? "ok" : "info");
      reload();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const s = data.state;
  const stateBars: [string, number, string][] = [
    ["انرژی", s.energy, "brand"],
    ["تمرکز", s.focus, "brand"],
    ["انگیزه", s.motivation, "good"],
    ["استرس", s.stress, "warn"],
    ["خستگی", s.fatigue, "bad"],
  ];

  return (
    <div className="space-y-5">
      {/* header */}
      <div className="card animate-rise flex flex-wrap items-center justify-between gap-4 bg-gradient-to-l from-brand-600 to-brand-500 text-white">
        <div>
          <p className="text-xs opacity-80">{data.today.jalali_long}</p>
          <h1 className="mt-1 text-2xl font-black">سلام 👋 {data.user.display_name}</h1>
          <p className="mt-1.5 text-sm opacity-90">{data.week.label}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!data.rewards.wake_up_today ? (
            <button className="btn bg-white/20 text-white hover:bg-white/30" onClick={wakeUp}>
              ⏰ بیدار شدم
            </button>
          ) : (
            <span className="chip bg-white/20 text-white">
              ⏰ بیدار شدن ثبت شد: {fa(data.rewards.wake_up_time || "")}
            </span>
          )}
          <button className="btn bg-white/20 text-white hover:bg-white/30" onClick={() => setCheckIn(true)}>
            🧭 ثبت وضعیت امروز
          </button>
        </div>
      </div>

      {/* stats */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat icon="🪙" label="سکه مطالعه" value={fa(data.rewards.coins)} tone="brand"
              sub={`امروز +${fa(data.rewards.today_points)}`} />
        <Stat icon="🔥" label="Streak" value={fa(data.rewards.current_streak)} tone="warn"
              sub={`رکورد: ${fa(data.rewards.longest_streak)} روز`} />
        <Stat icon="✅" label="کارهای امروز" value={`${fa(data.tasks.done)}/${fa(data.tasks.total)}`}
              sub={`${fa(data.tasks.pending)} باقی‌مانده`} />
        <Stat icon="🎯" label="دقت کلی" value={pct(data.quality.accuracy)} tone="good"
              sub={`${fa(data.quality.correct)} درست از ${fa(data.quality.correct + data.quality.wrong)}`} />
        <Stat icon="📥" label="تست این هفته" value={fa(data.attempts.week)}
              sub={`امروز ${fa(data.attempts.today)}`} />
        <Stat icon="🔁" label="صف مرور" value={fa(data.review.open)} tone={data.review.due ? "bad" : "default"}
              sub={`${fa(data.review.due)} سررسیدشده`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* capacity + habit */}
        <Card className="lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="section-title">ظرفیت امروز</h2>
            <Chip tone={data.capacity.is_school_day ? "sky" : "good"}>
              {data.capacity.is_school_day ? "روز مدرسه" : "روز آزاد"}
            </Chip>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="muted">ظرفیت تخمینی</p>
              <p className="tabular text-xl font-bold">{fa(data.capacity.capacity_minutes)} دقیقه</p>
            </div>
            <div>
              <p className="muted">برنامه‌ریزی‌شده</p>
              <p className={`tabular text-xl font-bold ${data.capacity.over_capacity ? "text-rose-600" : ""}`}>
                {fa(data.capacity.planned_minutes)} دقیقه
              </p>
            </div>
            <div>
              <p className="muted">وعده پیشنهادی</p>
              <p className="tabular text-xl font-bold">{fa(data.capacity.suggested_blocks)} وعده</p>
            </div>
          </div>
          <div className="mt-4">
            <Bar
              value={data.capacity.capacity_minutes ? data.capacity.planned_minutes / data.capacity.capacity_minutes : 0}
              tone={data.capacity.over_capacity ? "bad" : "brand"}
            />
          </div>
          {data.capacity.over_capacity && (
            <p className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">
              ⚠️ برنامه امروز از ظرفیت بیشتر است. هیچ کاری خودکار حذف نمی‌شود — می‌توانی کم‌اولویت‌ها را جابه‌جا کنی.
            </p>
          )}
          {data.capacity.classes.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {data.capacity.classes.map((c) => (
                <Chip key={c.id} tone="brand">
                  🎓 {c.title}
                  {c.start_time ? ` — ${fa(c.start_time)}` : ""}
                </Chip>
              ))}
            </div>
          )}
          {data.habit_advice && (
            <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm leading-6 text-amber-800">
              💡 {data.habit_advice}
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-2 text-xs text-ink-mute">
            <Chip>روزهای فعال: {fa(data.habit.active_days)}/{fa(data.habit.threshold)}</Chip>
            <Chip>میانگین روز مدرسه: {fa(data.habit.avg_tasks_school_day)} کار</Chip>
            <Chip>میانگین روز آزاد: {fa(data.habit.avg_tasks_free_day)} کار</Chip>
          </div>
        </Card>

        {/* state */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="section-title">وضعیت فعلی</h2>
            <Chip tone={s.source === "self_report" ? "good" : "slate"}>
              {s.source === "self_report" ? "خوداظهاری" : "تخمینی"}
            </Chip>
          </div>
          <div className="mb-4 text-center">
            <div className="tabular text-4xl font-black text-brand-600">{fa(s.readiness.toFixed(2))}</div>
            <p className="muted mt-1">آمادگی</p>
            <p className="mt-1 text-xs text-ink-mute">
              اطمینان {fa(s.confidence.toFixed(2))} • شواهد {fa(s.evidence_count)}
            </p>
          </div>
          <div className="space-y-2.5">
            {stateBars.map(([label, v, tone]) => (
              <div key={label}>
                <div className="mb-1 flex justify-between text-xs text-ink-soft">
                  <span>{label}</span>
                  <span className="tabular">{fa(v.toFixed(2))}</span>
                </div>
                <Bar value={v} tone={tone} height="h-1.5" />
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* V2.2 cards */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="section-title mb-3">🎯 پوشش امتحانات پیش‌رو</h2>
          {data.exam_coverage_card.items.length === 0 ? (
            <p className="muted">
              هنوز آمادگی امتحانی تعریف نکرده‌ای.{" "}
              <Link to="/readiness" className="font-medium text-brand-600">
                ساخت آمادگی امتحان
              </Link>
            </p>
          ) : (
            <div className="space-y-3">
              {data.exam_coverage_card.items.map((x) => (
                <Link
                  key={x.id}
                  to="/readiness"
                  className="block rounded-xl border border-surface-line p-3 transition hover:border-brand-300 hover:bg-brand-50/40"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">{x.title}</span>
                    <Chip tone={x.days_left <= 7 ? "bad" : x.days_left <= 14 ? "warn" : "slate"}>
                      {fa(x.days_left)} روز مانده
                    </Chip>
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <Bar value={x.avg_coverage} tone={x.avg_coverage < 0.3 ? "bad" : "good"} height="h-1.5" />
                    <span className="tabular shrink-0 text-xs text-ink-soft">{pct(x.avg_coverage)}</span>
                  </div>
                  <p className="mt-1.5 text-xs text-ink-mute">
                    {fa(x.low_coverage_topics)} مبحث از {fa(x.topic_count)} زیر ۳۰٪ • {x.exam_date_jalali}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <h2 className="section-title mb-3">🎓 تدریس‌شده</h2>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="کل" value={fa(data.taught_counts.total || 0)} />
            <Stat label="کم‌تمرین" value={fa(data.taught_counts.under_practiced || 0)} tone="warn" />
            <Stat label="با ضعف" value={fa(data.taught_counts.weak || 0)} tone="bad" />
            <Stat label="بدون بانک" value={fa(data.taught_counts.no_bank || 0)} tone="bad" />
          </div>
          {data.taught_warnings.length > 0 && (
            <div className="mt-3 space-y-2">
              {data.taught_warnings.map((w, i) => (
                <p key={i} className="rounded-xl bg-amber-50 p-2.5 text-xs leading-5 text-amber-800">
                  ⚠️ {w}
                </p>
              ))}
            </div>
          )}
          <Link to="/taught" className="btn-soft mt-3 w-full">
            مشاهده داشبورد تدریس‌شده
          </Link>
        </Card>
      </div>

      {data.upcoming_reminders.length > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <h2 className="section-title mb-2">🔔 یادآوری امتحان</h2>
          {data.upcoming_reminders.map((u) => (
            <p key={u.id} className="text-sm text-amber-900">
              «{u.title}» {u.days_left === 0 ? "امروز" : `${fa(u.days_left)} روز دیگر`} — {u.exam_date_jalali}
            </p>
          ))}
        </Card>
      )}

      {data.rewards.badges.length > 0 && (
        <Card>
          <h2 className="section-title mb-3">🏅 نشان‌ها</h2>
          <div className="flex flex-wrap gap-2">
            {data.rewards.badges.map((b, i) => (
              <Chip key={i} tone="good">
                🏅 {b.title}
              </Chip>
            ))}
          </div>
        </Card>
      )}

      <CheckInModal open={checkIn} onClose={() => setCheckIn(false)} onDone={reload} />
    </div>
  );
}

function CheckInModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const [v, setV] = useState({ energy: 0.5, focus: 0.5, motivation: 0.5, stress: 0.5, fatigue: 0.5 });
  const fields: [keyof typeof v, string][] = [
    ["energy", "انرژی"],
    ["focus", "تمرکز"],
    ["motivation", "انگیزه"],
    ["stress", "استرس"],
    ["fatigue", "خستگی"],
  ];
  const save = async () => {
    try {
      await api.post("/state/check-in", v);
      toast("وضعیت امروز ثبت شد");
      onClose();
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="ثبت وضعیت امروز">
      <div className="space-y-4">
        {fields.map(([k, label]) => (
          <div key={k}>
            <div className="mb-1.5 flex justify-between text-sm">
              <span>{label}</span>
              <span className="tabular font-semibold text-brand-600">{fa(v[k].toFixed(2))}</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={v[k]}
              onChange={(e) => setV({ ...v, [k]: +e.target.value })}
              className="w-full accent-brand-600"
            />
          </div>
        ))}
        <p className="rounded-xl bg-surface-alt p-3 text-xs leading-5 text-ink-soft">
          این خوداظهاری جدا از رفتار مشاهده‌شده ذخیره می‌شود و فقط توصیه‌ها را تغذیه می‌کند — هیچ Taskی خودکار
          ساخته یا حذف نمی‌شود.
        </p>
        <div className="flex gap-2">
          <button className="btn-primary flex-1" onClick={save}>
            ثبت وضعیت
          </button>
          <button className="btn-ghost" onClick={onClose}>
            انصراف
          </button>
        </div>
      </div>
    </Modal>
  );
}
