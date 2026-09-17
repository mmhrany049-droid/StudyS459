import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat } from "../components/ui";
import { JalaliDateInput } from "../components/JalaliDateInput";
import { todayJalali, toPersianDigits } from "../lib/format";

export default function Exams() {
  const [exams, setExams] = useState<any[]>([]);
  const [calendar, setCalendar] = useState<any>(null);
  const [retakes, setRetakes] = useState<any[]>([]);
  const [quiet, setQuiet] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    exam_type: "school",
    date: todayJalali(),
    total_questions: "",
    planned_duration_minutes: "",
    keep_for_retake: false,
  });

  function load() {
    setError(null);
    api.get<any>("/exams").then((payload) => setExams(payload.exams ?? [])).catch((err) => setError(err.message));
    api.get<any>("/exams/calendar").then(setCalendar).catch(() => undefined);
    api.get<any>("/mocks/retake-list").then((payload) => setRetakes(payload.mocks ?? [])).catch(() => undefined);
    api.get<any>("/mocks/quiet-suggestions").then(setQuiet).catch(() => undefined);
  }
  useEffect(load, []);

  async function create() {
    if (!form.title) {
      setError("عنوان امتحان را وارد کن.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/exams", {
        title: form.title,
        exam_type: form.exam_type,
        date: form.date,
        total_questions: form.total_questions ? Number(form.total_questions) : undefined,
        planned_duration_minutes: form.planned_duration_minutes ? Number(form.planned_duration_minutes) : undefined,
        keep_for_retake: form.keep_for_retake,
      });
      setNotice("امتحان ثبت شد؛ حالا در اولویت‌بندی و برنامه هفته اثر می‌گذارد.");
      setForm({ ...form, title: "", total_questions: "", planned_duration_minutes: "" });
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (error && exams.length === 0) return <ErrorBox message={error} onRetry={load} />;

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="lg:col-span-2 grid gap-5">
        <Card title="امتحان‌های پیش‌رو" action={<span className="muted">{calendar ? `${calendar.from} تا ${calendar.to}` : ""}</span>}>
          {exams.length === 0 ? (
            <Empty
              title="امتحانی ثبت نشده"
              hint="امتحان‌های مدرسه و آزمون‌های آزمایشی رویدادهای درجه‌یک‌اند؛ بدون آن‌ها اولویت‌ها خوش‌بینانه می‌شوند."
            />
          ) : (
            <ul className="grid gap-2">
              {exams.map((exam) => (
                <li key={exam.id} className="rounded-xl border border-ink-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{exam.title}</span>
                        <Badge tone={exam.exam_type === "mock" ? "warn" : "muted"}>
                          {exam.exam_type === "mock" ? "آزمون آزمایشی" : "امتحان مدرسه"}
                        </Badge>
                        {exam.retake_of_id && <Badge tone="warn">نوبت تکرار</Badge>}
                        {exam.keep_for_retake && <Badge tone="muted">برای تکرار نگه داشته شده</Badge>}
                      </div>
                      <div className="muted mt-1">
                        {exam.date}
                        {exam.days_left !== undefined && exam.days_left !== null
                          ? exam.days_left >= 0
                            ? ` — ${toPersianDigits(exam.days_left)} روز مانده`
                            : ` — ${toPersianDigits(Math.abs(exam.days_left))} روز گذشته`
                          : ""}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {exam.percentage !== null && exam.percentage !== undefined ? (
                        <span className="muted">درصد {toPersianDigits(Math.round(exam.percentage))}</span>
                      ) : exam.planned_duration_minutes ? (
                        <span className="muted">{toPersianDigits(exam.planned_duration_minutes)} دقیقه</span>
                      ) : null}
                      <button
                        className="btn-ghost btn-xs"
                        onClick={async () => {
                          await api.post(`/exams/${exam.id}/retake`, {});
                          setNotice("نوبت جدید ساخته شد؛ تاریخچه نوبت قبلی دست‌نخورده ماند.");
                          load();
                        }}
                      >
                        نوبت جدید
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {calendar?.exams?.length > 0 && (
          <Card title="تقویم امتحان‌ها">
            <ul className="grid gap-2">
              {calendar.exams.map((exam: any) => (
                <li key={exam.id} className="flex items-center justify-between rounded-xl bg-ink-50 p-2 text-sm">
                  <span>{exam.title}</span>
                  <span className="muted">
                    {exam.date} — {toPersianDigits(exam.day_index)} روز دیگر
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {retakes.length > 0 && (
          <Card title="آزمون‌های آزمایشی نگه‌داشته‌شده برای تکرار">
            <ul className="grid gap-2">
              {retakes.map((exam) => (
                <li key={exam.id} className="flex items-center justify-between rounded-xl border border-ink-200 p-2 text-sm">
                  <span>{exam.title}</span>
                  <span className="muted">{exam.date}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {quiet?.suggestions?.length > 0 && (
          <Card title="پیشنهادهای کم‌حرف">
            <ul className="grid gap-2 text-xs text-ink-600">
              {quiet.suggestions.slice(0, 3).map((item: any, index: number) => (
                <li key={index} className="rounded-xl bg-ink-50 p-3">
                  <span className="font-medium text-ink-800">{item.topic_title ?? "پیشنهاد"}</span>
                  {item.questions ? ` — ${toPersianDigits(item.questions)} سؤال` : ""}
                  <div className="muted mt-1">{item.short_reason ?? ""}</div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      <div className="grid gap-5">
        <Card title="ثبت امتحان">
          <div className="grid gap-3">
            <div>
              <label className="label">عنوان</label>
              <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div>
              <label className="label">نوع</label>
              <select className="input" value={form.exam_type} onChange={(e) => setForm({ ...form, exam_type: e.target.value })}>
                <option value="school">امتحان مدرسه</option>
                <option value="mock">آزمون آزمایشی</option>
                <option value="quiz">آزمون کلاسی</option>
              </select>
            </div>
            <JalaliDateInput value={form.date} onChange={(value) => setForm({ ...form, date: value })} label="تاریخ (شمسی)" required />
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="label">تعداد سؤال</label>
                <input
                  className="input"
                  inputMode="numeric"
                  value={form.total_questions}
                  onChange={(e) => setForm({ ...form, total_questions: e.target.value.replace(/[^0-9]/g, "") })}
                />
              </div>
              <div>
                <label className="label">مدت (دقیقه)</label>
                <input
                  className="input"
                  inputMode="numeric"
                  value={form.planned_duration_minutes}
                  onChange={(e) => setForm({ ...form, planned_duration_minutes: e.target.value.replace(/[^0-9]/g, "") })}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-xs text-ink-600">
              <input
                type="checkbox"
                className="h-4 w-4 accent-brand-600"
                checked={form.keep_for_retake}
                onChange={(e) => setForm({ ...form, keep_for_retake: e.target.checked })}
              />
              برای تکرار در آینده نگه داشته شود
            </label>
            <button className="btn-primary" disabled={busy} onClick={create}>
              ثبت امتحان
            </button>
            {notice && <div className="rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}
            {error && <div className="rounded-xl bg-bad-100/60 p-3 text-xs text-bad-600">{error}</div>}
          </div>
        </Card>

        <Card title="نکته">
          <p className="muted">
            پوشش «برنامه‌ریزی‌شده» و «واقعی» هر امتحان جدا نگه داشته می‌شود؛ امتحان پایانی که همه مباحث را اعلام می‌کند با
            پوشش واقعی سنجیده می‌شود، نه با ادعای برنامه.
          </p>
        </Card>
      </div>
    </div>
  );
}
