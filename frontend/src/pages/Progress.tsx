import { Bar, Card, Chip, ErrorBox, Loading, Stat } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { fa, pct } from "../lib/api";
import type { ProgressData } from "../lib/types";

export default function Progress() {
  const { data, error, loading, reload } = useFetch<ProgressData>("/progress/overview");

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const maxTrend = Math.max(...data.trend.map((t) => t.attempts), 1);
  const tot = data.books.reduce(
    (a, b) => ({
      total: a.total + b.total,
      attempted: a.attempted + b.attempted,
      correct: a.correct + b.correct,
      wrong: a.wrong + b.wrong,
      unanswered: a.unanswered + b.unanswered,
    }),
    { total: 0, attempted: 0, correct: 0, wrong: 0, unanswered: 0 }
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-black">پیشرفت و تحلیل</h1>
        <p className="muted mt-1">Coverage، Accuracy و Volume سه مفهوم مستقل‌اند و جدا گزارش می‌شوند.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="سوال در بانک" value={fa(tot.total)} />
        <Stat label="Coverage کلی" value={pct(tot.total ? tot.attempted / tot.total : 0)} tone="brand" />
        <Stat label="درست" value={fa(tot.correct)} tone="good" />
        <Stat label="غلط" value={fa(tot.wrong)} tone="bad" />
        <Stat label="نزده" value={fa(tot.unanswered)} tone="warn" />
      </div>

      <Card>
        <h2 className="section-title mb-4">روند ۱۴ روز اخیر</h2>
        <div className="flex h-40 items-end gap-1.5">
          {data.trend.map((t, i) => (
            <div key={i} className="flex flex-1 flex-col items-center gap-1.5" title={`${t.date_jalali}: ${t.attempts}`}>
              <span className="tabular text-[10px] text-ink-mute">{t.attempts ? fa(t.attempts) : ""}</span>
              <div
                className="w-full rounded-t-lg bg-brand-500 transition-all duration-500"
                style={{ height: `${Math.max(3, (t.attempts / maxTrend) * 100)}%` }}
              />
              <span className="text-[9px] text-ink-mute">{t.weekday.slice(0, 3)}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="section-title mb-4">رفتار مشاهده‌شده</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Stat label="نرخ تکمیل کار" value={pct(data.behavior.task_completion_rate)} tone="good" />
          <Stat label="نرخ Skip" value={pct(data.behavior.skip_rate)} tone="warn" />
          <Stat label="میانگین جلسه" value={`${fa(data.behavior.average_session_minutes)} د`} />
          <Stat label="ویرایش دستی" value={fa(data.behavior.manual_override_count)} />
          <Stat
            label="اطمینان مدل"
            value={fa(data.behavior.confidence.toFixed(2))}
            sub={`${fa(data.behavior.evidence_count)} شاهد`}
            tone="brand"
          />
        </div>
        <p className="mt-3 rounded-xl bg-surface-alt p-3 text-xs leading-6 text-ink-soft">
          ۳ مشاهده اعتبار ۳۰ مشاهده را ندارد؛ تا رسیدن به شواهد کافی، توصیه‌ها محافظه‌کارانه می‌مانند. ویرایش
          دستی «خطا» نیست — فقط شاهد ثبت می‌شود.
        </p>
      </Card>

      {data.books.map((b) => (
        <Card key={b.book_id}>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="h-5 w-5 rounded-lg" style={{ backgroundColor: b.color }} />
              <h2 className="section-title">{b.title}</h2>
              <Chip tone="brand">{b.subject}</Chip>
            </div>
            <div className="flex gap-2 text-xs">
              <Chip>Coverage {pct(b.coverage)}</Chip>
              <Chip tone="good">Accuracy {pct(b.accuracy)}</Chip>
              <Chip>{fa(b.total)} سوال</Chip>
            </div>
          </div>

          {b.total === 0 ? (
            <p className="muted">هنوز سوالی در بانک این کتاب تعریف نشده.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-line text-right text-xs text-ink-soft">
                    <th className="py-2 font-medium">فصل</th>
                    <th className="py-2 font-medium">کل</th>
                    <th className="py-2 font-medium">زده‌شده</th>
                    <th className="py-2 font-medium">Coverage</th>
                    <th className="py-2 font-medium">درست</th>
                    <th className="py-2 font-medium">غلط</th>
                    <th className="py-2 font-medium">نزده</th>
                    <th className="py-2 font-medium">Accuracy</th>
                    <th className="py-2 font-medium">مرور باز</th>
                  </tr>
                </thead>
                <tbody>
                  {b.chapters.map((c) => (
                    <tr key={c.node_id} className="border-b border-surface-line/60 hover:bg-surface-alt">
                      <td className="max-w-xs truncate py-2.5" title={c.title}>
                        {c.title}
                      </td>
                      <td className="tabular py-2.5">{fa(c.total)}</td>
                      <td className="tabular py-2.5">{fa(c.attempted)}</td>
                      <td className="py-2.5">
                        <div className="flex items-center gap-2">
                          <div className="w-16">
                            <Bar value={c.coverage} tone={c.coverage < 0.3 ? "bad" : "good"} height="h-1.5" />
                          </div>
                          <span className="tabular text-xs">{pct(c.coverage)}</span>
                        </div>
                      </td>
                      <td className="tabular py-2.5 text-emerald-600">{fa(c.correct)}</td>
                      <td className="tabular py-2.5 text-rose-600">{fa(c.wrong)}</td>
                      <td className="tabular py-2.5 text-amber-600">{fa(c.unanswered)}</td>
                      <td className="tabular py-2.5">{pct(c.accuracy)}</td>
                      <td className="tabular py-2.5">{c.open_review ? fa(c.open_review) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
