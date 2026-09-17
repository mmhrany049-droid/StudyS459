import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Dashboard as DashboardShape, Suggestion } from "../lib/api";
import { Card, Empty, ErrorBox, ExplainBox, Meter, Spinner, Badge } from "../components/ui";
import { confidenceBand, faNumber, minutes, percent, toPersianDigits,  statusLabel } from "../lib/format";

export default function Dashboard() {
  const [data, setData] = useState<DashboardShape | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openExplain, setOpenExplain] = useState<number | null>(null);

  function load() {
    setError(null);
    api
      .get<DashboardShape>("/dashboard")
      .then(setData)
      .catch((err) => setError(err.message));
  }

  useEffect(load, []);

  if (error) return <ErrorBox message={error} onRetry={load} />;
  if (!data) return <Spinner />;

  const priorities = data.what_matters_now?.priorities ?? [];
  const review = data.what_matters_now?.review;
  const next = data.what_next;
  const tasks = (next?.tasks as any[]) ?? [];
  const time = data.time;
  const suggestions: Suggestion[] = data.why?.suggestions ?? [];
  const quiet: Suggestion[] = data.why?.quiet ?? [];
  const learning = data.learning ?? {};
  const exams = (data.exams?.upcoming as any[]) ?? [];
  const goals = (data.goals as any[]) ?? [];
  const habits = data.habits as any;
  const midweek = data.midweek as any;
  const checkin = data.checkin as any;

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="grid gap-5 lg:col-span-2">
        <Card
          title={<span>الان مهمترین چیز</span>}
          action={<Link to="/plan" className="btn-soft btn-xs">برنامه هفته</Link>}
        >
          {priorities.length === 0 ? (
            <Empty title="هنوز شواهدی برای اولویت‌بندی نیست" hint="با تیک «تدریس‌شده» و ثبت تلاش‌ها، اولویت‌ها ساخته می‌شوند." />
          ) : (
            <ol className="grid gap-3">
              {priorities.slice(0, 4).map((item: any, index: number) => (
                <li key={item.topic_id} className="rounded-xl border border-ink-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="grid h-6 w-6 place-items-center rounded-lg bg-brand-50 text-xs text-brand-700 num">
                        {toPersianDigits(index + 1)}
                      </span>
                      <span className="text-sm font-medium">{item.topic_title ?? `مبحث ${item.topic_id}`}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="num text-xs text-ink-600">امتیاز {faNumber(item.score, 2)}</span>
                      <Badge tone={item.confidence >= 0.6 ? "ok" : item.confidence >= 0.35 ? "warn" : "muted"}>
                        اطمینان {confidenceBand(item.confidence)}
                      </Badge>
                    </div>
                  </div>
                  <p className="muted mt-1">
                    {item.top_reasons?.[0]?.human_text || item.top_reasons?.[0]?.label || ""}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </Card>

        <Card title="بعد چه کاری">
          {tasks.length === 0 ? (
            <Empty
              title="برای امروز کاری برنامه‌ریزی نشده"
              hint="می‌توانی از برنامه هفته کار بسازی یا از پیشنهادها مستقیم کار بسازی."
            />
          ) : (
            <ul className="grid gap-2">
              {tasks.slice(0, 6).map((task) => (
                <li key={task.id} className="flex items-center justify-between rounded-xl border border-ink-200 p-3">
                  <div>
                    <div className="text-sm font-medium">{task.title}</div>
                    <div className="muted">
                      {task.duration_label || `${minutes(task.duration_low)} تا ${minutes(task.duration_high)}`}
                      {task.override_reason && ` — ${task.override_reason}`}
                    </div>
                  </div>
                  <Badge tone={task.status === "completed" ? "ok" : "muted"}>{statusLabel(task.status)}</Badge>
                </li>
              ))}
            </ul>
          )}
          {next?.over_capacity && (
            <div className="mt-3 rounded-xl border border-warn-600/30 bg-warn-100/60 p-3 text-xs text-warn-600">
              بار امروز از ظرفیت واقع‌بینانه بیشتر است. هیچ کاری خودکار حذف نمی‌شود؛ فقط جابه‌جایی پیشنهاد می‌شود.
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <Link to="/sheet" className="btn-primary btn-xs">شروع جلسه تست</Link>
            <Link to="/review" className="btn-ghost btn-xs">مرور {toPersianDigits(review?.open ?? 0)} آیتم</Link>
          </div>
        </Card>

        <Card title="چرا؟ (این هفته چه چیزی مهم است)">
          {suggestions.length === 0 && quiet.length === 0 ? (
            <Empty title="پیشنهادی نیست" hint="پیشنهادها فقط وقتی ساخته می‌شوند که داده کافی باشد؛ عدد الکی نمایش داده نمی‌شود." />
          ) : (
            <ul className="grid gap-3">
              {[...suggestions, ...quiet].slice(0, 5).map((item) => (
                <li key={item.topic_id} className="rounded-xl bg-ink-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{item.topic_title}</span>
                    <Badge tone="muted">{item.suggested_intervention_label ?? item.suggested_intervention}</Badge>
                  </div>
                  <p className="muted mt-1">{item.short_reason}</p>
                  <button
                    className="btn-soft btn-xs mt-2"
                    onClick={() => setOpenExplain(openExplain === item.topic_id ? null : item.topic_id)}
                  >
                    {openExplain === item.topic_id ? "بستن توضیح" : "چرا این؟ شواهد چیست؟"}
                  </button>
                  {openExplain === item.topic_id && <div className="mt-2"><ExplainBox explain={item.why} compact /></div>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-5">
        <Card title="زمان واقع‌بینانه امروز">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-ink-50 p-3">
              <div className="text-xs text-ink-600">ظرفیت واقع‌بینانه</div>
              <div className="num mt-1 text-lg font-semibold">{minutes(time?.realistic_minutes_today)}</div>
            </div>
            <div className="rounded-xl bg-ink-50 p-3">
              <div className="text-xs text-ink-600">وقت آزاد تقویمی</div>
              <div className="num mt-1 text-lg font-semibold text-ink-600">{minutes(time?.theoretical_minutes_today)}</div>
            </div>
            <div className="rounded-xl bg-ink-50 p-3">
              <div className="text-xs text-ink-600">برنامه‌ریزی‌شده</div>
              <div className="num mt-1 text-lg font-semibold">{minutes(time?.planned_minutes_today)}</div>
            </div>
            <div className="rounded-xl bg-ink-50 p-3">
              <div className="text-xs text-ink-600">مرور باز</div>
              <div className="num mt-1 text-lg font-semibold">{toPersianDigits(review?.open ?? 0)}</div>
            </div>
          </div>
          <p className="muted mt-3">{time?.explanation}</p>
          <p className="muted mt-1">ظرفیت واقعی ≠ وقت آزاد.</p>
        </Card>

        <Card title="امتحان‌های نزدیک" action={<Link to="/exams" className="btn-ghost btn-xs">همه</Link>}>
          {exams.length === 0 ? (
            <p className="muted">امتحانی ثبت نشده است. امتحان مدرسه یا آزمون آزمایشی را اضافه کن تا اولویت‌ها واقعی شوند.</p>
          ) : (
            <ul className="grid gap-2">
              {exams.slice(0, 4).map((exam) => (
                <li key={exam.id} className="flex items-center justify-between rounded-xl border border-ink-200 p-2.5">
                  <div>
                    <div className="text-sm font-medium">{exam.title}</div>
                    <div className="muted">{exam.date}</div>
                  </div>
                  <Badge tone={exam.exam_type === "mock" ? "warn" : "muted"}>
                    {exam.exam_type === "mock" ? "آزمایشی" : "مدرسه"}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="هدف‌ها" action={<Link to="/goals" className="btn-ghost btn-xs">همه</Link>}>
          {goals.length === 0 ? (
            <p className="muted">هدف سه‌ماهه‌ای ثبت نشده است.</p>
          ) : (
            <ul className="grid gap-3">
              {goals.slice(0, 3).map((goal) => (
                <li key={goal.id}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium">{goal.title}</span>
                    <span className="num text-xs text-ink-600">{percent(goal.progress?.ratio)}</span>
                  </div>
                  <Meter value={goal.progress?.ratio} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="یادگیری">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-ink-50 p-3">
              <div className="text-xs text-ink-600">پوشش</div>
              <div className="num mt-1 font-semibold">{percent(learning.coverage as number)}</div>
            </div>
            <div className="rounded-xl bg-ink-50 p-3">
              <div className="text-xs text-ink-600">دقت</div>
              <div className="num mt-1 font-semibold">
                {learning.accuracy === null ? "نامعلوم" : percent(learning.accuracy as number)}
              </div>
            </div>
            <div className="rounded-xl bg-ink-50 p-3">
              <div className="text-xs text-ink-600">حجم تلاش</div>
              <div className="num mt-1 font-semibold">{toPersianDigits((learning.volume as number) ?? 0)}</div>
            </div>
            <div className="rounded-xl bg-ink-50 p-3">
              <div className="text-xs text-ink-600">نزده / ثبت‌نشده</div>
              <div className="num mt-1 font-semibold">
                {toPersianDigits((learning.unanswered as number) ?? 0)} / {toPersianDigits((learning.not_entered as number) ?? 0)}
              </div>
            </div>
          </div>
          <p className="muted mt-3">پوشش، دقت و حجم سه مفهوم جدا هستند؛ هیچ‌کدام جای دیگری را نمی‌گیرد.</p>
          <Link to="/progress" className="btn-soft btn-xs mt-3">تحلیل کامل</Link>
        </Card>

        {(habits?.available === false || midweek?.warning || checkin) && (
          <Card title="عادت‌ها و وضعیت">
            {habits?.message && <p className="muted">{habits.message}</p>}
            {midweek?.warning && (
              <p className="mt-2 rounded-xl bg-warn-100/70 p-3 text-xs text-warn-600">{midweek.warning}</p>
            )}
            {checkin?.message && <p className="muted mt-2">{checkin.message}</p>}
          </Card>
        )}
      </div>
    </div>
  );
}
