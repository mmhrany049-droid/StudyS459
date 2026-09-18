import { useEffect, useMemo, useState } from "react";
import { api, PlanningSession } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, ExplainBox, Stat } from "../components/ui";
import { JalaliDateInput } from "../components/JalaliDateInput";
import { faNumber, minutes, toPersianDigits } from "../lib/format";

export default function Planner() {
  const [session, setSession] = useState<PlanningSession | null>(null);
  const [week, setWeek] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<number, string>>({});
  const [typeRegistry, setTypeRegistry] = useState<any[]>([]);
  const [draft, setDraft] = useState({ title: "", task_type: "practice_test", planned_date: "", planned_minutes: "", planned_question_count: "" });

  function load() {
    setError(null);
    api
      .get<PlanningSession>("/planning/current")
      .then(setSession)
      .catch((err) => setError(err.message));
    api
      .get<any>("/planning/week")
      .then((payload) => {
        setWeek(payload);
        const today = (payload?.days ?? []).find((day: any) => day.is_today) ?? payload?.days?.[0];
        if (today?.date) setDraft((current) => (current.planned_date ? current : { ...current, planned_date: today.date }));
      })
      .catch(() => undefined);
    api
      .get<any>("/tasks/types")
      .then((payload) => {
        setTypeRegistry(payload.types ?? []);
        const preferred = (payload.types ?? []).find((item: any) => item.code === "practice_test");
        if (preferred) setDraft((current) => ({ ...current, task_type: preferred.code }));
      })
      .catch(() => undefined);
  }
  useEffect(load, []);

  const stages = (session as any)?.stages as { key: string; label: string }[] | undefined;
  const questions = (session as any)?.questions as any[] | undefined;
  const suggestions = ((session as any)?.priority_suggestions ?? []) as any[];
  const savedDecisions = ((session as any)?.user_decisions ?? []) as any[];
  const savedByTopic: Record<number, string> = {};
  if (Array.isArray(savedDecisions)) {
    for (const row of savedDecisions) {
      if (row && typeof row === "object" && row.topic_id !== undefined) savedByTopic[row.topic_id] = row.decision;
    }
  }
  const explanation = (session as any)?.explanation;
  const plan = (session as any)?.plan ?? [];
  const answeredCount = (questions ?? []).filter((item) => item.answered).length;

  const nextQuestion = useMemo(() => (questions ?? []).find((item) => !item.answered && !item.skipped), [questions]);

  async function savePriorityDecisions() {
    if (!session) return;
    const items = Object.entries(decisions).map(([topicId, decision]) => ({
      topic_id: Number(topicId),
      decision,
    }));
    if (items.length === 0) {
      setNotice("تصمیمی ثبت نشد؛ می‌توانی همین‌طور ادامه بدهی و بر ترتیب خودکار تکیه کنی.");
      return;
    }
    setBusy(true);
    try {
      await api.post(`/planning/sessions/${session.id}/priorities`, { items });
      setNotice("تصمیم‌های تو ذخیره شد و بر ترتیب برنامه اثر می‌گذارد؛ هیچ‌چیز خودکار لغو نمی‌شود.");
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function answerQuestion(question: any, value: unknown) {
    if (!session) return;
    setBusy(true);
    try {
      await api.post(`/planning/sessions/${session.id}/answers`, {
        code: question.code,
        answer: value,
      });
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function addManualTask() {
    if (!draft.title.trim()) {
      setError("عنوان کار مطالعه را بنویس.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        title: draft.title.trim(),
        task_type: draft.task_type,
        source: "manual",
      };
      if (draft.planned_date) payload.planned_date = draft.planned_date;
      if (draft.planned_minutes) payload.planned_minutes = Number(draft.planned_minutes);
      if (draft.planned_question_count) payload.planned_question_count = Number(draft.planned_question_count);
      const created = await api.post<any>("/tasks", payload);
      setNotice(`کار «${created.title}» با نوع «${created.type_label}» اضافه شد (${created.duration_label ?? "بدون برآورد"}).`);
      setDraft({ ...draft, title: "", planned_minutes: "", planned_question_count: "" });
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function generate(rebuild = false) {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const path = rebuild ? "rebuild" : "generate";
      const result = await api.post<any>(`/planning/sessions/${session.id}/${path}`, {});
      setNotice(
        rebuild
          ? "برنامه بازسازی شد. کارهای دستی تو دست‌نخورده ماندند."
          : `برنامه ساخته شد: ${toPersianDigits(result.tasks_created ?? 0)} کار برای هفته.`,
      );
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !session) return <ErrorBox message={error} onRetry={load} />;
  if (!session) return <Spinner />;

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="grid gap-5 lg:col-span-2">
        <Card
          title={`برنامه‌ریزی هفتگی — ${(session as any).week_label ?? ""}`}
          action={<Badge tone={session.status === "finalized" ? "ok" : "warn"}>{session.status === "finalized" ? "نهایی‌شده" : "در جریان"}</Badge>}
        >
          {stages && (
            <ol className="mb-4 flex flex-wrap gap-1 text-[11px] text-ink-600">
              {stages.map((stage, index) => (
                <li key={stage.key} className="rounded-lg bg-ink-100 px-2 py-1">
                  {toPersianDigits(index + 1)}. {stage.label}
                </li>
              ))}
            </ol>
          )}

          {notice && <div className="mb-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}
          {error && <div className="mb-3 rounded-xl bg-bad-100/60 p-3 text-xs text-bad-600">{error}</div>}

          <section className="mb-5">
            <h3 className="mb-2 text-sm font-semibold">
              ۱. پیشنهاد اولویت‌ها {suggestions.length > 0 && <span className="muted">({toPersianDigits(suggestions.length)} مبحث)</span>}
            </h3>
            {suggestions.length === 0 ? (
              <Empty title="پیشنهادی نیست" hint="وقتی داده کافی نباشد، برنامه بدون ساخته‌شدن اولویت الکی ساخته می‌شود." />
            ) : (
              <>
                <ul className="grid gap-2">
                  {suggestions.map((item) => {
                    const decision = decisions[item.topic_id] ?? savedByTopic[item.topic_id] ?? "";
                    return (
                      <li key={item.topic_id} className="rounded-xl border border-ink-200 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-sm font-medium">{item.topic_title}</span>
                          <span className="num text-xs text-ink-600">امتیاز {faNumber(item.score, 2)}</span>
                        </div>
                        <p className="muted mt-1">{item.short_reason}</p>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {[
                            ["accept", "تأیید"],
                            ["increase", "افزایش"],
                            ["decrease", "کاهش"],
                            ["reject", "رد"],
                          ].map(([value, label]) => (
                            <button
                              key={value}
                              className={decision === value ? "btn-primary btn-xs" : "btn-ghost btn-xs"}
                              onClick={() => setDecisions({ ...decisions, [item.topic_id]: value })}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </li>
                    );
                  })}
                </ul>
                <button className="btn-soft btn-xs mt-3" disabled={busy} onClick={savePriorityDecisions}>
                  ثبت تصمیم‌ها
                </button>
              </>
            )}
          </section>

          <section className="mb-5">
            <h3 className="mb-2 text-sm font-semibold">
              ۲. پرسش‌های تطبیقی{" "}
              <span className="muted">
                ({toPersianDigits(answeredCount)} از {toPersianDigits((questions ?? []).length)})
              </span>
            </h3>
            {nextQuestion ? (
              <div className="rounded-xl border border-brand-300 bg-brand-50/40 p-3">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-sm font-medium">{nextQuestion.text}</span>
                  <Badge tone="muted">ارزش اطلاعاتی {faNumber(nextQuestion.information_value, 2)}</Badge>
                </div>
                {nextQuestion.because && <p className="muted mb-2">چرا می‌پرسم: {nextQuestion.because}</p>}
                <div className="flex flex-wrap gap-2">
                  {(nextQuestion.options ?? []).map((option: any) => (
                    <button
                      key={option.value ?? option.label}
                      className="btn-ghost btn-xs"
                      disabled={busy}
                      onClick={() => answerQuestion(nextQuestion, option.value ?? option.label)}
                    >
                      {option.label ?? option.value}
                    </button>
                  ))}
                  <button className="btn-soft btn-xs" disabled={busy} onClick={() => answerQuestion(nextQuestion, null)}>
                    نمی‌دانم / رد کن
                  </button>
                </div>
                <p className="muted mt-2">سؤال‌ها فقط جایی پرسیده می‌شوند که پاسخ، برنامه را واقعاً تغییر بدهد.</p>
              </div>
            ) : (
              <p className="muted">سؤال بی‌جوابی نمانده است.</p>
            )}
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">۳. تولید برنامه</h3>
            <div className="flex flex-wrap gap-2">
              <button className="btn-primary" disabled={busy} onClick={() => generate(false)}>
                ساخت برنامه هفته
              </button>
              <button className="btn-ghost" disabled={busy} onClick={() => generate(true)}>
                بازسازی برنامه
              </button>
              <span className="muted self-center">بازسازی هرگز کار دستی تو را پاک نمی‌کند؛ اول تأیید می‌گیرد.</span>
            </div>
          </section>
        </Card>

        <Card
          title="تقویم هفته"
          action={<span className="muted">{week?.calendar ? `${week.calendar.from_long} تا ${week.calendar.to_long}` : ""}</span>}
        >
          {!week?.calendar ? (
            <p className="muted">تقویم هفته در حال بارگذاری است…</p>
          ) : (
            <>
              <div className="grid grid-cols-7 gap-1">
                {week.calendar.days.map((row: any) => (
                  <div
                    key={row.date}
                    className={`rounded-xl border p-2 text-center text-[11px] ${
                      row.is_holiday ? "border-bad-200 bg-bad-50" : "border-ink-200 bg-white"
                    }`}
                  >
                    <div className="font-medium">{row.weekday}</div>
                    <div className="num">{toPersianDigits(row.jalali.day)}</div>
                    <div className="muted">{row.jalali.month}</div>
                    <div className="mt-1 flex flex-col items-center gap-0.5">
                      {row.event_count > 0 && <span className="badge-muted">{toPersianDigits(row.event_count)} رویداد</span>}
                      {row.planned_minutes > 0 && <span className="muted">{toPersianDigits(row.planned_minutes)}′</span>}
                      {row.holiday_titles?.length > 0 && <span className="text-[10px] text-bad-600">تعطیل</span>}
                    </div>
                  </div>
                ))}
              </div>
              <p className="muted mt-2">{week.calendar.note}</p>
            </>
          )}
        </Card>

        <Card title="برنامه هفته">
          {!week || (week.days ?? []).every((day: any) => (day.tasks ?? []).length === 0) ? (
            <Empty title="هنوز برنامه‌ای ساخته نشده" hint="با «ساخت برنامه هفته» کارها روی روزها پخش می‌شوند." />
          ) : (
            <div className="grid gap-3">
              {week.days.map((day: any) => (
                <div key={day.date} className="rounded-xl border border-ink-200 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="text-sm font-medium">{day.date_long}</span>
                      {day.over_capacity && <span className="badge-warn mr-2">بیش از ظرفیت</span>}
                      {day.calendar?.is_holiday && (
                        <span className="badge-muted mr-2">{day.calendar.holiday_titles?.[0] ?? "تعطیل"}</span>
                      )}
                      {day.calendar?.events?.some((event: any) => event.kind === "exam") && (
                        <span className="badge-warn mr-2">آزمون</span>
                      )}
                    </div>
                    <span className="muted">
                      برنامه‌ریزی‌شده {minutes(day.capacity?.planned_minutes)} / ظرفیت واقع‌بینانه{" "}
                      {minutes(day.capacity?.realistic_minutes)}
                    </span>
                  </div>
                  {(day.tasks ?? []).length === 0 ? (
                    <p className="muted">کاری برای این روز نیست.</p>
                  ) : (
                    <ul className="grid gap-1">
                      {day.tasks.map((task: any) => (
                        <li key={task.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-ink-50 px-3 py-2">
                          <div>
                            <span className="text-sm">{task.title}</span>
                            {task.manual_override && <span className="badge-warn mr-2">دستی</span>}
                          </div>
                          <span className="muted">
                            {task.duration_label ?? `${minutes(task.duration_low)} تا ${minutes(task.duration_high)}`}
                            {task.override_reason ? ` — ${task.override_reason}` : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-5">
        <Card title="افزودن کار مطالعه">
          <div className="grid gap-2">
            <input
              className="input"
              placeholder="عنوان کار"
              value={draft.title}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
            />
            <select className="input" value={draft.task_type} onChange={(event) => setDraft({ ...draft, task_type: event.target.value })}>
              {typeRegistry.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.label}
                </option>
              ))}
            </select>
            <p className="muted">
              {typeRegistry.find((item) => item.code === draft.task_type)?.hint}
              {typeRegistry.find((item) => item.code === draft.task_type)?.needs_questions
                ? " — این نوع با تعداد سؤال سنجیده می‌شود."
                : " — این نوع سؤال نمی‌خواهد؛ زمانش مهم است."}
            </p>
            <JalaliDateInput
              value={draft.planned_date}
              onChange={(value) => setDraft({ ...draft, planned_date: value })}
              label="روز (شمسی)"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                className="input"
                inputMode="numeric"
                placeholder="مدت (دقیقه) — اختیاری"
                value={draft.planned_minutes}
                onChange={(event) => setDraft({ ...draft, planned_minutes: event.target.value.replace(/[^0-9]/g, "") })}
              />
              <input
                className="input"
                inputMode="numeric"
                placeholder="تعداد سؤال — اختیاری"
                value={draft.planned_question_count}
                onChange={(event) => setDraft({ ...draft, planned_question_count: event.target.value.replace(/[^0-9]/g, "") })}
              />
            </div>
            <button className="btn-primary btn-xs" onClick={addManualTask} disabled={busy}>
              افزودن
            </button>
            <p className="muted">
              اگر مدت را خالی بگذاری، برآورد پله‌ای (کم/زیاد) از تاریخ واقعی خودت ساخته می‌شود — نه از عدد ثابت.
            </p>
          </div>
        </Card>

        <Card title="از پاسخ‌های خودت">
          <div className="grid gap-2 text-xs">
            <p className="muted">
              {(explanation?.from_your_answers?.weight_adjustments?.weights &&
                Object.keys(explanation.from_your_answers.weight_adjustments.weights).length > 0 &&
                "پاسخ‌های هفتگی وزن هدف/مرور را کمی جابه‌جا کرده‌اند:") ||
                "پاسخ هفتگی‌ای که وزن برنامه را عوض کند ثبت نشده؛ برنامه با وزن‌های پایه ساخته شده است."}
            </p>
            {explanation?.from_your_answers?.weight_adjustments?.weights && (
              <ul className="grid gap-1">
                {Object.entries(explanation.from_your_answers.weight_adjustments.weights).map(([weight, entry]: any) => (
                  <li key={weight}>
                    {weight} → ضریب {faNumber(entry.multiplier, 2)} ({faNumber(entry.delta_pct * 100, 1)}٪)
                  </li>
                ))}
              </ul>
            )}
            {explanation?.from_your_answers?.ordering_note && <p>{explanation.from_your_answers.ordering_note}</p>}
            {explanation?.from_your_answers?.capacity_note && <p>{explanation.from_your_answers.capacity_note}</p>}
            <p className="muted">
              ترجیح شخصیتی فقط با شواهد کافی و فقط روی ترتیب پیشنهادهای هم‌امتیاز اثر می‌گذارد؛ هیچ‌چیز قفل نمی‌شود.
            </p>
          </div>
        </Card>

        <Card title="چرا این برنامه؟">
          {explanation && Object.keys(explanation).length > 0 ? (
            <div className="grid gap-3 text-xs leading-6">
              <p>{explanation.summary}</p>
              {explanation.capacity_note && <p className="muted">{explanation.capacity_note}</p>}
              {explanation.review_open !== undefined && (
                <p className="muted">آیتم‌های مرور باز: {toPersianDigits(explanation.review_open)}</p>
              )}
              {explanation.exams && explanation.exams.length > 0 && (
                <div>
                  <div className="font-semibold text-ink-800">امتحان‌های مؤثر</div>
                  <ul className="list-inside list-disc">
                    {explanation.exams.map((exam: any, index: number) => (
                      <li key={index}>
                        {exam.title} — {exam.date}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {explanation.overload?.has_overload && (
                <div className="rounded-xl bg-warn-100/60 p-3 text-warn-600">
                  <div className="font-semibold">بار بیشتر از ظرفیت</div>
                  <ul className="mt-1 list-inside list-disc">
                    {explanation.overload.days.slice(0, 3).map((day: any, index: number) => (
                      <li key={index}>
                        {day.date}: {minutes(day.excess)} بیشتر — {day.suggestion}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {explanation.what_can_i_change && (
                <div>
                  <div className="font-semibold text-ink-800">چه چیزی را می‌توانم تغییر بدهم؟</div>
                  <ul className="list-inside list-disc">
                    {explanation.what_can_i_change.map((item: string, index: number) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {explanation.no_magic && <p className="muted">{explanation.no_magic}</p>}
            </div>
          ) : (
            <p className="muted">بعد از تولید برنامه، دلیل هر تصمیم اینجا نمایش داده می‌شود.</p>
          )}
        </Card>

        {week?.capacity && (
          <Card title="ظرفیت هفته">
            <div className="grid gap-2">
              <Stat label="ظرفیت واقع‌بینانه" value={minutes(week.capacity.realistic_minutes)} />
              <Stat label="وقت آزاد تقویمی" value={minutes(week.capacity.theoretical_minutes)} />
              <Stat label="برنامه‌ریزی‌شده" value={minutes(week.capacity.planned_minutes)} />
              <Stat label="روزهای پر" value={toPersianDigits((week.capacity.overloaded_days ?? []).length)} />
            </div>
          </Card>
        )}

        {week?.midweek && (
          <Card title="بررسی میان‌هفته">
            <p className="muted">
              پیشرفت {faNumber((week.midweek.progress ?? 0) * 100, 0)}٪ — آستانه هشدار{" "}
              {faNumber((week.midweek.threshold ?? 0) * 100, 0)}٪
            </p>
            {week.midweek.warning ? (
              <p className="mt-2 rounded-xl bg-warn-100/70 p-3 text-xs text-warn-600">{week.midweek.warning}</p>
            ) : (
              <p className="muted mt-2">هشدار میان‌هفته‌ای وجود ندارد.</p>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
