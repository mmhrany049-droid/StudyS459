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
  const [uploading, setUploading] = useState<number | null>(null);
  const [retakeFor, setRetakeFor] = useState<number | null>(null);
  const [retakeDate, setRetakeDate] = useState<string>("");
  const [topicsFor, setTopicsFor] = useState<number | null>(null);
  const [topicsData, setTopicsData] = useState<any>(null);
  const [bookId, setBookId] = useState<number | null>(null);
  const [tree, setTree] = useState<any>(null);
  const [prep, setPrep] = useState<any[]>([]);
  const [form, setForm] = useState({
    title: "",
    exam_type: "school",
    date: todayJalali(),
    start_hour: "",
    start_minute: "00",
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
    api
      .get<any>("/exams/prep-suggestions")
      .then((payload) => setPrep(payload.suggestions ?? []))
      .catch(() => undefined);
    api
      .get<any>("/books")
      .then((payload) => {
        const first = payload.books?.[0];
        if (first) {
          setBookId(first.id);
          api.get<any>(`/books/${first.id}/tree`).then(setTree).catch(() => undefined);
        }
      })
      .catch(() => undefined);
  }

  async function openTopics(examId: number) {
    setTopicsFor(topicsFor === examId ? null : examId);
    const data = await api.get<any>(`/exams/${examId}/topics`);
    setTopicsData(data);
  }

  async function markTopic(examId: number, topicId: number, checked: boolean) {
    await api.post(`/exams/${examId}/topics`, { topic_id: topicId, mark_kind: "planned", checked, cascade: true });
    openTopics(examId);
  }
  useEffect(load, []);

  async function upload(examId: number, file: File) {
    setUploading(examId);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      await api.upload(`/exams/${examId}/files`, body);
      setNotice("فایل ضمیمه شد؛ روی همین دستگاه ذخیره می‌شود و در گیت نمی‌آید.");
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(null);
    }
  }

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
        start_time: form.start_hour ? `${form.start_hour.padStart(2, "0")}:${form.start_minute}` : undefined,
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
                      <button className="btn-ghost btn-xs" onClick={() => openTopics(exam.id)}>
                        مباحث امتحان
                      </button>
                      {(exam.files ?? []).length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {(exam.files ?? []).map((file: any) => (
                            <a
                              key={file.stored_name}
                              className="badge-muted"
                              href={`/api/exams/${exam.id}/files/${encodeURIComponent(file.stored_name)}`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {file.name}
                            </a>
                          ))}
                        </div>
                      )}
                      <div className="muted mt-1">
                        {exam.start_time ? `ساعت ${toPersianDigits(exam.start_time)} — ` : ""}
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
                      <label className="btn-ghost btn-xs cursor-pointer">
                        {uploading === exam.id ? "در حال ضمیمه…" : "ضمیمه فایل"}
                        <input
                          type="file"
                          className="hidden"
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file) upload(exam.id, file);
                            event.target.value = "";
                          }}
                        />
                      </label>
                      {retakeFor === exam.id ? (
                        <div className="grid gap-2 rounded-xl bg-ink-50 p-2">
                          <JalaliDateInput
                            value={retakeDate}
                            onChange={setRetakeDate}
                            label="تاریخ نوبت جدید (خالی = همان تاریخ)"
                          />
                          <div className="flex gap-2">
                            <button
                              className="btn-primary btn-xs"
                              onClick={async () => {
                                await api.post(`/exams/${exam.id}/retake`, retakeDate ? { date: retakeDate } : {});
                                setNotice("نوبت جدید ساخته شد؛ تاریخچه نوبت قبلی دست‌نخورده ماند.");
                                setRetakeFor(null);
                                setRetakeDate("");
                                load();
                              }}
                            >
                              ثبت نوبت
                            </button>
                            <button className="btn-ghost btn-xs" onClick={() => setRetakeFor(null)}>
                              انصراف
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button className="btn-ghost btn-xs" onClick={() => setRetakeFor(exam.id)}>
                          نوبت جدید
                        </button>
                      )}
                    </div>
                  </div>
                  {topicsFor === exam.id && (
                    <div className="mt-3 grid gap-2 rounded-xl bg-ink-50 p-3 text-xs">
                      <div className="font-semibold text-ink-800">
                        مباحث اعلام‌شده این امتحان (لایه برنامه‌ریزی‌شده از پوشش واقعی جدا است)
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {(topicsData?.planned ?? []).slice(0, 12).map((row: any) => (
                          <span key={row.topic_id} className="badge-muted">
                            {row.title}
                          </span>
                        ))}
                        {(topicsData?.planned ?? []).length === 0 && <span className="muted">هنوز مبحثی علامت نخورده است.</span>}
                      </div>
                      {topicsData?.comparison && (
                        <p className="muted">
                          پوشش برنامه‌ریزی‌شده {toPersianDigits(topicsData.comparison.planned_count)} مبحث، پوشش واقعی{" "}
                          {toPersianDigits(topicsData.comparison.actual_count)} مبحث.
                        </p>
                      )}
                      <div className="grid gap-1">
                        {(tree?.topics ?? []).slice(0, 6).map((node: any) => {
                          const marked = (topicsData?.planned ?? []).some((row: any) => row.topic_id === node.id);
                          return (
                            <label key={node.id} className="flex items-center gap-2">
                              <input
                                type="checkbox"
                                className="h-4 w-4 accent-brand-600"
                                checked={marked}
                                onChange={(event) => markTopic(exam.id, node.id, event.target.checked)}
                              />
                              <span>{node.title}</span>
                            </label>
                          );
                        })}
                      </div>
                      <span className="muted">{bookId ? "مباحث از کتاب فعال انتخاب می‌شوند." : ""}</span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        {prep.length > 0 && (
          <Card title="آمادگی امتحان‌های پیش‌رو">
            <ul className="grid gap-2 text-xs text-ink-600">
              {prep.map((item: any, index: number) => (
                <li key={index} className="rounded-xl bg-ink-50 p-3">
                  <div className="font-medium text-ink-800">
                    {item.exam_title} — {toPersianDigits(item.days_left)} روز مانده
                  </div>
                  <div className="muted mt-1">
                    {toPersianDigits(item.topic_count)} مبحث علامت‌خورده؛ ضعیف‌ترین‌ها:{" "}
                    {(item.weakest_topics ?? [])
                      .slice(0, 3)
                      .map((topic: any) => topic.topic_title)
                      .join("، ")}
                  </div>
                </li>
              ))}
            </ul>
            <p className="muted mt-3">پیشنهاد آمادگی فقط از مباحث همان امتحان ساخته می‌شود و کم‌سروصدا ارائه می‌گردد.</p>
          </Card>
        )}

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
                <label className="label">ساعت شروع (اختیاری)</label>
                <select
                  className="input"
                  value={form.start_hour}
                  onChange={(event) => setForm({ ...form, start_hour: event.target.value })}
                >
                  <option value="">بدون ساعت</option>
                  {Array.from({ length: 24 }, (_, hour) => hour).map((hour) => (
                    <option key={hour} value={String(hour)}>
                      {toPersianDigits(String(hour).padStart(2, "0"))}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">دقیقه</label>
                <select
                  className="input"
                  value={form.start_minute}
                  onChange={(event) => setForm({ ...form, start_minute: event.target.value })}
                  disabled={!form.start_hour}
                >
                  {["00", "15", "30", "45"].map((minute) => (
                    <option key={minute} value={minute}>
                      {toPersianDigits(minute)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
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
