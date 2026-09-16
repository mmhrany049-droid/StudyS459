import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, Card, Chip, ErrorBox, Loading, Modal, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa } from "../lib/api";
import type { Candidate, ReviewQueueData, Task, WeekView } from "../lib/types";

export default function Today() {
  const { data: week, error, loading, reload } = useFetch<WeekView>("/week");
  const { data: cands, reload: reloadC } = useFetch<Candidate[]>("/planning/candidates?limit=8");
  const { data: rq, reload: reloadR } = useFetch<ReviewQueueData>("/review/queue");
  const [interview, setInterview] = useState(false);
  const nav = useNavigate();

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!week) return null;

  const todayIso = new Date().toISOString().slice(0, 10);
  const refreshAll = () => {
    reload();
    reloadC();
    reloadR();
  };

  const generate = async (replace: boolean) => {
    try {
      const r = await api.post<{ created: number; explanation: string; habit_advice: string | null }>(
        `/planning/generate?replace=${replace}`
      );
      toast(r.created ? `${fa(r.created)} کار پیشنهادی ساخته شد` : "کار جدیدی لازم نبود", "ok");
      if (r.habit_advice) setTimeout(() => toast(r.habit_advice!, "info"), 600);
      refreshAll();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const startReview = async () => {
    try {
      const s = await api.post<{ id: number }>("/review-sessions");
      nav(`/test/${s.id}`);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const startCandidate = async (c: Candidate) => {
    try {
      const s = await api.post<{ id: number }>("/test-sessions", {
        node_id: c.node_id,
        count: c.suggested_count,
        parity: c.parity,
      });
      nav(`/test/${s.id}`);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">امروز و هفته</h1>
          <p className="muted mt-1">
            هفته از شنبه تا جمعه • برنامه بر اساس «تعداد کار / وعده» است، نه جدول ساعت اجباری.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={() => setInterview(true)}>
            🗣️ مصاحبه ابتدای هفته
          </button>
          <button className="btn-ghost" onClick={() => generate(true)}>
            🔄 بازسازی برنامه
          </button>
          <button className="btn-primary" onClick={() => generate(false)}>
            ✨ پیشنهاد سیستم برای امروز
          </button>
        </div>
      </div>

      {rq && rq.total > 0 && (
        <Card className="border-rose-200 bg-rose-50">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-bold text-rose-900">🔁 صف مرور</h2>
              <p className="mt-1 text-sm text-rose-800">
                {fa(rq.total)} مورد باز • {fa(rq.items.filter((i) => i.due).length)} سررسیدشده •{" "}
                {fa(rq.items.filter((i) => i.critical).length)} بحرانی
              </p>
            </div>
            <button className="btn-primary" onClick={startReview}>
              شروع جلسه مرور (تا ۲۵ سوال)
            </button>
          </div>
        </Card>
      )}

      {cands && cands.length > 0 && (
        <Card>
          <h2 className="section-title mb-1">پیشنهاد سیستم — و چرا</h2>
          <p className="muted mb-4">وزن‌ها: هدف موضوعی ۳۵، مرور بحرانی ۲۵، کلاس روز ۱۵ (+۱۵ بونوس)، parity ۱۰، deadline ۱۰، تعداد ۵</p>
          <div className="space-y-2.5">
            {cands.map((c) => (
              <div key={c.node_id} className="rounded-xl border border-surface-line p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Chip tone="brand">{c.subject}</Chip>
                      <span className="font-medium">{c.title}</span>
                      <Chip tone="warn">امتیاز {fa(c.score)}</Chip>
                      <Chip tone={c.parity === "odd" ? "sky" : "brand"}>{c.parity === "odd" ? "فرد" : "زوج"}</Chip>
                    </div>
                    <p className="mt-1 truncate text-xs text-ink-mute" title={c.full_title}>
                      {c.full_title}
                    </p>
                    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-soft">
                      {c.reasons.map((r, i) => (
                        <li key={i}>• {r}</li>
                      ))}
                    </ul>
                  </div>
                  <button className="btn-soft btn-xs shrink-0" onClick={() => startCandidate(c)}>
                    شروع {fa(c.suggested_count)} تست
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-7">
        {week.days.map((d) => (
          <DayColumn key={d.date} day={d} isToday={d.date === todayIso} onChange={refreshAll} />
        ))}
      </div>

      <InterviewModal open={interview} onClose={() => setInterview(false)} />
    </div>
  );
}

function DayColumn({
  day,
  isToday,
  onChange,
}: {
  day: WeekView["days"][number];
  isToday: boolean;
  onChange: () => void;
}) {
  const nav = useNavigate();
  const cap = day.capacity;

  const complete = async (t: Task) => {
    await api.patch(`/tasks/${t.id}`, { status: t.status === "completed" ? "pending" : "completed" });
    toast(t.status === "completed" ? "به حالت انجام‌نشده برگشت" : "کار انجام شد 🎉");
    onChange();
  };

  const runTask = async (t: Task) => {
    if (!t.node_id) return toast("این کار به مبحث متصل نیست", "info");
    try {
      const s = await api.post<{ id: number }>("/test-sessions", {
        node_id: t.node_id,
        count: t.quantity,
        parity: t.parity,
        task_id: t.id,
      });
      nav(`/test/${s.id}`);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const move = async (t: Task, dir: number) => {
    const d = new Date(t.planned_date);
    d.setDate(d.getDate() + dir);
    await api.post(`/tasks/${t.id}/move`, { planned_date: d.toISOString().slice(0, 10) });
    onChange();
  };

  const remove = async (t: Task) => {
    await api.del(`/tasks/${t.id}`);
    toast("کار حذف شد");
    onChange();
  };

  return (
    <div
      className={`animate-rise rounded-2xl border p-3 ${
        isToday ? "border-brand-400 bg-brand-50/40 ring-2 ring-brand-100" : "border-surface-line bg-white"
      }`}
    >
      <div className="mb-2.5">
        <div className="flex items-center justify-between">
          <span className={`text-sm font-bold ${isToday ? "text-brand-700" : ""}`}>{day.weekday}</span>
          {isToday && <Chip tone="brand">امروز</Chip>}
        </div>
        <p className="tabular text-xs text-ink-mute">{day.jalali}</p>
      </div>

      <div className="mb-3">
        <div className="mb-1 flex justify-between text-[11px] text-ink-mute">
          <span>{cap.is_school_day ? "مدرسه" : "آزاد"}</span>
          <span className="tabular">
            {fa(cap.planned_minutes)}/{fa(cap.capacity_minutes)}د
          </span>
        </div>
        <Bar
          value={cap.capacity_minutes ? cap.planned_minutes / cap.capacity_minutes : 0}
          tone={cap.over_capacity ? "bad" : "brand"}
          height="h-1"
        />
      </div>

      {cap.classes.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {cap.classes.map((c) => (
            <span key={c.id} className="chip bg-sky-50 text-[10px] text-sky-700">
              🎓 {c.title.replace("کلاس تقویتی ", "")}
            </span>
          ))}
        </div>
      )}

      {day.tasks.length === 0 ? (
        <p className="py-4 text-center text-xs text-ink-mute">کاری نیست</p>
      ) : (
        <div className="space-y-2">
          {day.tasks.map((t) => (
            <div
              key={t.id}
              className={`group rounded-xl border p-2.5 text-xs transition ${
                t.status === "completed" ? "border-emerald-200 bg-emerald-50 opacity-75" : "border-surface-line bg-white"
              }`}
            >
              <div className="flex items-start gap-2">
                <button
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${
                    t.status === "completed" ? "border-emerald-500 bg-emerald-500 text-white" : "border-slate-300"
                  }`}
                  onClick={() => complete(t)}
                >
                  {t.status === "completed" ? "✓" : ""}
                </button>
                <div className="min-w-0 flex-1">
                  <p className={`leading-5 ${t.status === "completed" ? "line-through" : "font-medium"}`}>{t.title}</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {t.subject && (
                      <span className="chip bg-slate-100 text-[10px]" style={{ color: t.subject_color }}>
                        {t.subject}
                      </span>
                    )}
                    <span className="chip bg-slate-100 text-[10px]">{fa(t.estimated_minutes)}د</span>
                    {t.manual_override && <span className="chip bg-amber-50 text-[10px] text-amber-700">دستی</span>}
                    {t.task_type === "exam_prep" && (
                      <span className="chip bg-rose-50 text-[10px] text-rose-700">آمادگی امتحان</span>
                    )}
                  </div>
                  {t.recommendation_reason && (
                    <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-ink-mute" title={t.recommendation_reason}>
                      {t.recommendation_reason}
                    </p>
                  )}
                </div>
              </div>
              <div className="mt-2 flex gap-1 opacity-0 transition group-hover:opacity-100">
                {t.node_id && t.status !== "completed" && (
                  <button className="btn-soft btn-xs flex-1 text-[10px]" onClick={() => runTask(t)}>
                    شروع
                  </button>
                )}
                <button className="btn-ghost btn-xs text-[10px]" onClick={() => move(t, -1)} title="روز قبل">
                  ›
                </button>
                <button className="btn-ghost btn-xs text-[10px]" onClick={() => move(t, 1)} title="روز بعد">
                  ‹
                </button>
                <button className="btn-danger btn-xs text-[10px]" onClick={() => remove(t)}>
                  🗑
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {cap.over_capacity && (
        <p className="mt-2 rounded-lg bg-rose-50 p-2 text-[10px] leading-4 text-rose-700">
          ⚠️ بیش از ظرفیت — هیچ کاری خودکار حذف نشد
        </p>
      )}
    </div>
  );
}

const QUESTIONS: [string, string][] = [
  ["commitments", "این هفته کلاس، مدرسه، آزمون یا قرار مهمی داری؟"],
  ["limited_days", "کدام روزها زمانت محدودتر است؟"],
  ["main_goal", "مهم‌ترین نتیجه‌ای که می‌خواهی آخر هفته داشته باشی چیست؟"],
  ["priority_subject", "کدام درس/موضوع بیشترین اولویت را دارد؟"],
  ["real_time", "این هفته در مجموع چقدر وقت واقعی داری؟"],
  ["energy_days", "کدام روزها انرژی بیشتری داری؟"],
  ["stress", "سطح استرس فعلی چقدر است؟"],
  ["plan_style", "برنامه دقیق می‌خواهی یا انعطاف‌پذیر؟"],
  ["blockers", "چه چیزی ممکن است این هفته باعث عقب‌انداختن کارها شود؟"],
  ["last_week", "هفته قبل چه چیزی خوب پیش رفت و چه چیزی انجام نشد؟"],
];

function InterviewModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const save = async (complete: boolean) => {
    try {
      await api.post("/planning/weekly-interview", { answers, complete });
      toast(complete ? "مصاحبه هفتگی تکمیل شد" : "پاسخ‌ها ذخیره شد");
      if (complete) onClose();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="مصاحبه برنامه‌ریزی ابتدای هفته" wide>
      <div className="space-y-4">
        <p className="rounded-xl bg-surface-alt p-3 text-xs leading-6 text-ink-soft">
          پاسخ‌ها به Planner به عنوان ورودی داده می‌شوند و برنامه را قفل نمی‌کنند. تصمیم نهایی همیشه با توست.
        </p>
        <div className="grid max-h-[55vh] gap-3 overflow-y-auto sm:grid-cols-2">
          {QUESTIONS.map(([k, q]) => (
            <div key={k}>
              <label className="label">{q}</label>
              <input className="input" value={answers[k] || ""} onChange={(e) => setAnswers({ ...answers, [k]: e.target.value })} />
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <button className="btn-primary flex-1" onClick={() => save(true)}>
            ثبت و تکمیل
          </button>
          <button className="btn-ghost" onClick={() => save(false)}>
            ذخیره موقت
          </button>
        </div>
      </div>
    </Modal>
  );
}
