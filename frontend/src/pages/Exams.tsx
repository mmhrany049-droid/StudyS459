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
  const [center, setCenter] = useState<any>(null);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [answerKeyText, setAnswerKeyText] = useState("");
  const [selectedSubjects, setSelectedSubjects] = useState<number[]>([]);
  const [planFor, setPlanFor] = useState<number | null>(null);
  const [plan, setPlan] = useState<any>(null);
  const [form, setForm] = useState({
    title: "",
    exam_type: "school",
    source: "",
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
    api.get<any>("/exam-center").then(setCenter).catch(() => undefined);
    api
      .get<any>("/books")
      .then(async (payload) => {
        const ids = Array.from(
          new Set((payload.books ?? []).map((book: any) => book.subject_id).filter(Boolean)),
        ) as number[];
        setSubjects(ids.map((id) => ({ id, title: `درس ${toPersianDigits(id)}` })));
      })
      .catch(() => undefined);
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
      const created = await api.post<any>("/exams", {
        title: form.title,
        exam_type: form.exam_type,
        date: form.date,
        start_time: form.start_hour ? `${form.start_hour.padStart(2, "0")}:${form.start_minute}` : undefined,
        subjects: selectedSubjects,
        question_count: form.total_questions ? Number(form.total_questions) : undefined,
        total_questions: form.total_questions ? Number(form.total_questions) : undefined,
        planned_duration_minutes: form.planned_duration_minutes ? Number(form.planned_duration_minutes) : undefined,
        keep_for_retake: form.keep_for_retake,
        source: form.source || undefined,
      });
      if (answerKeyText.trim()) {
        await api.put(`/exams/${created.id}/answer-key`, { answer_key: answerKeyText });
      }
      setNotice("امتحان ثبت شد؛ حالا در اولویت‌بندی و برنامه هفته اثر می‌گذارد.");
      setForm({ ...form, title: "", total_questions: "", planned_duration_minutes: "", source: "" });
      setAnswerKeyText("");
      setSelectedSubjects([]);
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function openPlan(examId: number) {
    if (planFor === examId) {
      setPlanFor(null);
      return;
    }
    setPlanFor(examId);
    setPlan(null);
    const data = await api.get<any>(`/exams/${examId}/prep-plan`);
    setPlan(data);
  }

  if (error && exams.length === 0) return <ErrorBox message={error} onRetry={load} />;

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="lg:col-span-2 grid gap-5">
        {center && (
          <Card title="مرکز آزمون" action={<span className="muted">گذشته {toPersianDigits(center.counts?.past ?? 0)} · آینده {toPersianDigits(center.counts?.upcoming ?? 0)}</span>}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <div className="mb-2 text-xs font-semibold text-ink-800">آزمون‌های گذشته — نتیجه و پیگیری</div>
                {(center.past ?? []).length === 0 && <p className="muted">هنوز آزمون برگزارشده‌ای ثبت نشده است.</p>}
                <ul className="grid gap-2 text-xs">
                  {(center.past ?? []).slice(0, 4).map((exam: any) => (
                    <li key={exam.id} className="rounded-xl bg-ink-50 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-ink-800">{exam.title}</span>
                        <Badge tone={exam.result?.last_percentage === null ? "muted" : "ok"}>
                          {exam.result?.last_percentage === null || exam.result?.last_percentage === undefined
                            ? "بدون نتیجه"
                            : `درصد ${toPersianDigits(Math.round(exam.result.last_percentage))}`}
                        </Badge>
                      </div>
                      <div className="muted mt-1">
                        {exam.type_label} · {exam.date} · {toPersianDigits(exam.result?.attempts ?? 0)} تلاش
                      </div>
                      {(exam.weaknesses ?? []).length > 0 && (
                        <div className="mt-1">
                          ضعیف‌ها: {(exam.weaknesses ?? []).map((item: any) => item.topic_title).join("، ")}
                        </div>
                      )}
                      {(exam.follow_up ?? []).slice(0, 2).map((item: any, index: number) => (
                        <div key={index} className="muted mt-1">
                          پیگیری: {item.topic_title ?? "همین آزمون"} — {item.why}
                        </div>
                      ))}
                      {exam.retake_available && (
                        <div className="mt-1 text-brand-700">
                          برای تمرین مجدد نگه داشته شده؛ تکرار، تاریخچه را پاک نمی‌کند.
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="mb-2 text-xs font-semibold text-ink-800">آزمون‌های آینده — آماده‌سازی</div>
                {(center.upcoming ?? []).length === 0 && <p className="muted">آزمون آینده‌ای ثبت نشده است.</p>}
                <ul className="grid gap-2 text-xs">
                  {(center.upcoming ?? []).slice(0, 4).map((exam: any) => (
                    <li key={exam.id} className="rounded-xl bg-ink-50 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-ink-800">{exam.title}</span>
                        <Badge tone={exam.days_left <= 7 ? "warn" : "muted"}>{toPersianDigits(exam.days_left)} روز</Badge>
                      </div>
                      <div className="muted mt-1">
                        {exam.type_label} · {exam.date_long} · {toPersianDigits(exam.prep?.topics_marked ?? 0)} مبحث علامت‌خورده
                      </div>
                      <div className="mt-1">
                        آمادگی تخمینی:{" "}
                        {exam.prep?.readiness?.value === null || exam.prep?.readiness?.value === undefined
                          ? "بدون داده"
                          : toPersianDigits(Math.round(exam.prep.readiness.value * 100)) + "٪"}
                        <span className="muted"> — {exam.prep?.readiness?.evidence}</span>
                      </div>
                      {exam.prep?.next_action && <div className="muted mt-1">قدم بعدی: {exam.prep.next_action.text}</div>}
                      <button className="btn-ghost btn-xs mt-2" onClick={() => openPlan(exam.id)}>
                        {planFor === exam.id ? "بستن برنامه" : "برنامه آماده‌سازی چندروزه"}
                      </button>
                      {planFor === exam.id && plan && (
                        <div className="mt-2 grid gap-1 border-t border-ink-100 pt-2">
                          {plan.days.map((day: any) => (
                            <div key={day.date} className="flex items-start justify-between gap-2">
                              <span className="muted">{day.weekday} {day.date}</span>
                              <span className="flex-1">
                                {(day.topics ?? []).map((topic: any) => topic.topic_title).join("، ") || "مرور فهرست‌وار"}
                              </span>
                              <span className="muted">{toPersianDigits(day.suggested_minutes)}′</span>
                            </div>
                          ))}
                          <div className="muted">{plan.policy}</div>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <p className="muted mt-3">{center.policy}</p>
          </Card>
        )}

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
                {(center?.types ?? [
                  { value: "personal", label: "آزمون شخصی" },
                  { value: "school", label: "آزمون مدرسه" },
                  { value: "mock", label: "آزمون آزمایشی" },
                  { value: "checkup", label: "چکاپ" },
                  { value: "comprehensive", label: "جامع" },
                ]).map((option: any) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="muted mt-1">
                {(center?.types ?? []).find((option: any) => option.value === form.exam_type)?.hint ?? ""}
              </p>
              {(form.exam_type === "mock" || form.exam_type === "comprehensive") && (
                <div className="mt-2">
                  <label className="label">درس‌ها (چنددرس)</label>
                  <div className="flex flex-wrap gap-2">
                    {(subjects.length ? subjects : [{ id: 1, title: "درس ۱" }, { id: 2, title: "درس ۲" }, { id: 3, title: "درس ۳" }]).map(
                      (subject: any) => {
                        const checked = selectedSubjects.includes(subject.id);
                        return (
                          <button
                            key={subject.id}
                            className={checked ? "btn-primary btn-xs" : "btn-ghost btn-xs"}
                            onClick={() =>
                              setSelectedSubjects(
                                checked
                                  ? selectedSubjects.filter((id) => id !== subject.id)
                                  : [...selectedSubjects, subject.id],
                              )
                            }
                          >
                            {subject.title}
                          </button>
                        );
                      },
                    )}
                  </div>
                </div>
              )}
            </div>
            <JalaliDateInput value={form.date} onChange={(value) => setForm({ ...form, date: value })} label="تاریخ (شمسی)" required />
            <div>
              <label className="label">منبع (اختیاری)</label>
              <input
                className="input"
                value={form.source}
                onChange={(event) => setForm({ ...form, source: event.target.value })}
                placeholder="مدرسه، کانون، خودم…"
              />
            </div>
            <div>
              <label className="label">کلید آزمون (اختیاری)</label>
              <input
                className="input"
                value={answerKeyText}
                onChange={(event) => setAnswerKeyText(event.target.value)}
                placeholder="مثلاً 1:2,2:3,3:1 — خالی یعنی بدون کلید"
              />
              <p className="muted mt-1">کلید آزمون از برگهٔ پاسخ جداست و می‌تواند بعداً هم وارد شود.</p>
            </div>
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
