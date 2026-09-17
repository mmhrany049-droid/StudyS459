import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Meter, Stat, ExplainBox } from "../components/ui";
import { diagnosisLabel, faNumber, percent, toPersianDigits } from "../lib/format";

export default function Progress() {
  const [overview, setOverview] = useState<any>(null);
  const [weaknesses, setWeaknesses] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [trends, setTrends] = useState<any>(null);

  function load() {
    setError(null);
    api.get<any>("/progress/overview").then(setOverview).catch((err) => setError(err.message));
    api.get<any>(`/analytics/weaknesses?limit=10`).then((payload) => setWeaknesses(payload.items ?? [])).catch(() => undefined);
    api.get<any>(`/analytics/trends?days=${days}`).then(setTrends).catch(() => undefined);
  }
  useEffect(load, [days]);

  if (error) return <ErrorBox message={error} onRetry={load} />;
  if (!overview) return <Spinner />;

  const series = trends?.series ?? [];
  const maxAttempts = Math.max(1, ...series.map((row: any) => row.attempts ?? 0));

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="grid gap-5 lg:col-span-2">
        <Card title="تصویر کلی">
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="پوشش" value={percent(overview.coverage)} hint="چند درصد بانک دیده شده" />
            <Stat label="دقت" value={overview.accuracy === null ? "نامعلوم" : percent(overview.accuracy)} hint="از پاسخ‌های ارزیابی‌شده" />
            <Stat label="حجم تلاش" value={toPersianDigits(overview.attempts)} hint="تعداد تلاش‌ها" />
            <Stat label="اطمینان میانگین" value={faNumber(overview.mean_confidence, 2)} />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-4">
            <Stat label="درست" value={toPersianDigits(overview.correct)} />
            <Stat label="غلط" value={toPersianDigits(overview.wrong)} />
            <Stat label="نزده" value={toPersianDigits(overview.unanswered)} />
            <Stat label="ثبت‌نشده" value={toPersianDigits(overview.not_entered)} />
          </div>
          <p className="muted mt-3">{overview.note}</p>
          <p className="muted">
            «نزده» یعنی خودت نزدی؛ «ثبت‌نشده» یعنی ردیف خالی ماند. این دو هرگز با «غلط» جمع نمی‌شوند.
          </p>
        </Card>

        <Card title="ضعف‌ها (چند بُعدی)">
          {weaknesses.length === 0 ? (
            <Empty title="مبحث ضعیفی پیدا نشد" hint="ضعف از جمع غلط‌ها ساخته نمی‌شود؛ باید شواهد کافی وجود داشته باشد." />
          ) : (
            <ul className="grid gap-3">
              {weaknesses.map((item) => (
                <li key={item.topic_id} className="rounded-xl border border-ink-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium">{item.topic_title}</span>
                    <Badge tone={item.diagnosis === "UNCERTAIN_NEEDS_DIAGNOSTIC" ? "warn" : "bad"}>
                      {diagnosisLabel(item.diagnosis)}
                    </Badge>
                  </div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-3">
                    <Meter value={item.coverage} label="پوشش" />
                    <Meter value={item.accuracy} label="دقت" tone="warn" />
                    <Meter value={item.uncertainty} label="عدم‌قطعیت" tone="bad" />
                  </div>
                  <ExplainBox
                    compact
                    explain={{
                      what: item.why,
                      why: item.suggested_action,
                      evidence: {
                        coverage: item.coverage,
                        accuracy: item.accuracy,
                        confidence: item.confidence,
                        retention: item.retention,
                        recency_days: item.recency_days,
                        repeated_error_signal: item.repeated_error_signal,
                      },
                      what_can_i_change: [
                        "با یک تشخیص کوتاه می‌توانی عدم‌قطعیت را کم کنی.",
                        "اگر بخشی از مبحث را تدریس‌شده/تدریس‌نشده اصلاح کنی، محاسبه بازسازی می‌شود.",
                      ],
                    }}
                  />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-5">
        <Card title="روند" action={
          <select className="input max-w-[110px]" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={14}>۲ هفته</option>
            <option value={30}>۱ ماه</option>
            <option value={90}>۳ ماه</option>
          </select>
        }>
          {series.length === 0 ? (
            <p className="muted">فعالیتی ثبت نشده است. {trends?.note}</p>
          ) : (
            <>
              <div className="flex h-28 items-end gap-1">
                {series.map((row: any) => (
                  <div
                    key={row.date}
                    title={`${row.date} — ${row.attempts} تلاش`}
                    className="flex-1 rounded-t bg-brand-300"
                    style={{ height: `${Math.max(4, ((row.attempts ?? 0) / maxAttempts) * 100)}%` }}
                  />
                ))}
              </div>
              <div className="muted mt-2 flex justify-between">
                <span>{trends?.from}</span>
                <span>{trends?.to}</span>
              </div>
              <div className="mt-3 grid gap-2">
                <Stat label="روزهای فعال" value={toPersianDigits(trends?.summary?.days_with_activity ?? 0)} />
                <Stat label="میانگین دقت" value={trends?.summary?.mean_accuracy == null ? "نامعلوم" : percent(trends.summary.mean_accuracy)} />
              </div>
              <p className="muted mt-2">{trends?.note}</p>
            </>
          )}
        </Card>

        <Card title="بازسازی مقادیر مشتق">
          <p className="muted">
            هر عدد مشتق (پوشش، دقت، اولویت، نگه‌داشت) از داده خام بازساخته می‌شود. تغییر پاسخ‌نامه یا تیک تدریس، خودکار
            بازمحاسبه را علامت می‌زند.
          </p>
          <button
            className="btn-soft btn-xs mt-3"
            onClick={async () => {
              await api.post("/analytics/rebuild", {});
              load();
            }}
          >
            بازسازی کامل
          </button>
        </Card>
      </div>
    </div>
  );
}
