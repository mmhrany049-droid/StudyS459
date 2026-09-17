import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat } from "../components/ui";
import { faNumber, percent, toPersianDigits } from "../lib/format";

const PATTERN_LABEL: Record<string, string> = {
  hard_task_avoidance: "پرهیز از کار سخت",
  over_planning: "برنامه‌ریزی بیش از ظرفیت",
  late_start: "شروع دیرهنگام",
  fatigue_dip: "افت انرژی",
  skipping_review: "رها کردن مرور",
  cramming: "فشرده‌خوانی",
};

const EVENT_LABEL: Record<string, string> = {
  experiment_created: "آزمایش ساخته شد",
  answer_key_changed: "پاسخ‌نامه تغییر کرد",
  replay_rank_adjusted: "رتبه بازتوزیع شد",
  tasks_replanned: "برنامه بازچینی شد",
  integrity_issue_detected: "ناسازگاری داده",
  goal_created: "هدف ساخته شد",
  recommendation_accepted: "پیشنهاد پذیرفته شد",
  recommendation_rejected: "پیشنهاد رد شد",
  task_skipped: "کار رد شد",
  plan_generated: "برنامه ساخته شد",
  priority_feedback: "بازخورد اولویت",
};

export default function Lab() {
  const [experiments, setExperiments] = useState<any>(null);
  const [integrity, setIntegrity] = useState<any>(null);
  const [audit, setAudit] = useState<any[]>([]);
  const [behaviour, setBehaviour] = useState<any>(null);
  const [state, setState] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<any>(null);

  function load() {
    setError(null);
    api.get<any>("/experiments").then(setExperiments).catch((err) => setError(err.message));
    api.get<any>("/integrity/report").then(setIntegrity).catch(() => undefined);
    api.get<any>("/audit?limit=20").then((payload) => setAudit(payload.events ?? [])).catch(() => undefined);
    api.get<any>("/behavior/summary").then(setBehaviour).catch(() => undefined);
    api.get<any>("/state/current").then(setState).catch(() => undefined);
  }
  useEffect(load, []);

  async function startExperiment(template: any) {
    try {
      await api.post("/experiments", { template_key: template.key, title: template.title });
      setNotice(`آزمایش «${template.title}» شروع شد. نتیجه فقط با داده کافی گزارش می‌شود.`);
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function analyse(id: number) {
    const result = await api.get<any>(`/experiments/${id}/analysis`);
    setAnalysis(result);
  }

  if (error && !experiments) return <ErrorBox message={error} onRetry={load} />;
  if (!experiments) return <Spinner />;

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="grid gap-5 lg:col-span-2">
        <Card title="آزمایش‌های شخصی">
          {notice && <div className="mb-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}
          {experiments.experiments.length === 0 ? (
            <Empty title="آزمایشی در جریان نیست" hint="می‌توانی یک قالب را شروع کنی و اثرش را روی داده خودت بسنجی." />
          ) : (
            <ul className="grid gap-2">
              {experiments.experiments.map((item: any) => (
                <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-ink-200 p-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{item.title}</span>
                      <Badge tone={item.status === "running" ? "ok" : "muted"}>{item.status}</Badge>
                    </div>
                    <p className="muted mt-1">{item.hypothesis}</p>
                    <p className="muted">سنجه: {item.metric}</p>
                  </div>
                  <button className="btn-ghost btn-xs" onClick={() => analyse(item.id)}>
                    تحلیل
                  </button>
                </li>
              ))}
            </ul>
          )}
          {analysis && (
            <div className="mt-3 rounded-xl bg-ink-50 p-3 text-xs leading-6 text-ink-600">
              <div className="font-semibold text-ink-800">نتیجه تحلیل</div>
              <div>سنجه: {analysis.metric}</div>
              <div>وضعیت: {analysis.conclusion ?? "نامعلوم"}</div>
              <div>
                مشاهده هر بازو: مداخله {toPersianDigits(analysis.n_intervention ?? 0)} در برابر کنترل{" "}
                {toPersianDigits(analysis.n_control ?? 0)}
                {analysis.min_required ? ` (حداقل لازم: ${toPersianDigits(analysis.min_required)})` : ""}
              </div>
              {analysis.confidence !== undefined && analysis.confidence !== null && (
                <div>اطمینان: {percent(analysis.confidence, 0)}</div>
              )}
              <div>{analysis.interpretation}</div>
            </div>
          )}
        </Card>

        <Card title="قالب‌های آزمایش">
          <ul className="grid gap-3">
            {experiments.templates.map((template: any) => (
              <li key={template.key} className="rounded-xl border border-ink-200 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{template.title}</span>
                  <button className="btn-soft btn-xs" onClick={() => startExperiment(template)}>
                    شروع
                  </button>
                </div>
                <p className="muted mt-1">{template.hypothesis}</p>
                <p className="muted">
                  سنجه: {template.metric} ({template.metric_direction === "higher" ? "بالاتر بهتر" : "پایین‌تر بهتر"})
                </p>
              </li>
            ))}
          </ul>
          <p className="muted mt-3">{experiments.policy}</p>
        </Card>

        <Card title="بررسی یکپارچگی داده">
          {integrity && (
            <>
              <div className="grid gap-2 sm:grid-cols-3">
                <Stat label="وضعیت" value={integrity.ok ? "سالم" : "نیاز به بررسی"} />
                <Stat label="تعداد مشکل" value={toPersianDigits((integrity.issues ?? []).length)} />
                <Stat label="داده خام دست‌نخورده" value={integrity.raw_data_untouched ? "بله" : "خیر"} />
              </div>
              {(integrity.issues ?? []).length > 0 && (
                <ul className="mt-3 grid gap-2 text-xs text-ink-600">
                  {integrity.issues.map((issue: any, index: number) => (
                    <li key={index} className="rounded-xl bg-warn-100/60 p-3 text-warn-600">
                      {issue.kind} — {issue.message ?? JSON.stringify(issue)}
                    </li>
                  ))}
                </ul>
              )}
              <p className="muted mt-3">{integrity.note}</p>
            </>
          )}
        </Card>
      </div>

      <div className="grid gap-5">
        <Card title="مشاهده‌های رفتاری">
          {behaviour?.features ? (
            <div className="grid gap-2">
              <Stat label="نرخ تکمیل کار" value={percent(behaviour.features.task_completion_rate ?? 0)} />
              <Stat label="نرخ رد کردن" value={percent(behaviour.features.skip_rate ?? 0)} />
              <Stat label="نرخ ویرایش" value={percent(behaviour.features.edit_rate ?? 0)} />
              <Stat label="میانگین جلسه" value={behaviour.features.average_session_minutes ? `${faNumber(behaviour.features.average_session_minutes)} دقیقه` : "نامعلوم"} />
              <Stat label="ساعت شروع مؤثر" value={behaviour.features.effective_start_hour ? toPersianDigits(behaviour.features.effective_start_hour) : "نامعلوم"} />
            </div>
          ) : (
            <p className="muted">داده رفتاری کافی نیست.</p>
          )}
          {behaviour?.patterns?.length > 0 && (
            <ul className="mt-3 grid gap-2 text-xs">
              {behaviour.patterns.map((pattern: any) => (
                <li key={pattern.code} className="rounded-xl bg-ink-50 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{pattern.title ?? PATTERN_LABEL[pattern.code] ?? pattern.code}</span>
                    <span className="num text-ink-600">قوت {faNumber(pattern.strength, 2)}</span>
                  </div>
                  <p className="muted mt-1">{pattern.description}</p>
                  <p className="muted">{pattern.suggestion}</p>
                  <button
                    className="btn-ghost btn-xs mt-2"
                    onClick={async () => {
                      await api.post("/behavior/patterns/dismiss", { pattern_code: pattern.code, hours: 72 });
                      load();
                    }}
                  >
                    ۷۲ ساعت نشانم نده
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="muted mt-3">{behaviour?.features?.note}</p>
        </Card>

        <Card title="وضعیت لحظه‌ای">
          {state?.available ? (
            <div className="grid gap-2">
              {state.dimensions.map((dimension: any) => (
                <div key={dimension.key} className="flex items-center justify-between text-xs">
                  <span>{dimension.label}</span>
                  <span className="num">{faNumber(dimension.value, 2)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">{state?.message}</p>
          )}
          <div className="mt-3 grid gap-1">
            <button
              className="btn-soft btn-xs"
              onClick={async () => {
                await api.post("/state/check-in", {
                  answers: { energy: 0.6, focus: 0.6, motivation: 0.6, stress: 0.3, fatigue: 0.4 },
                });
                load();
              }}
            >
              چک‌این سریع امروز
            </button>
            <span className="muted">وضعیت لحظه‌ای با «شخصیت» قاطی نمی‌شود؛ دو مدل جدا هستند.</span>
          </div>
        </Card>

        <Card title="ردگیری تصمیم‌ها (Audit)">
          {audit.length === 0 ? (
            <p className="muted">رویدادی ثبت نشده است.</p>
          ) : (
            <ul className="grid gap-2 text-xs text-ink-600">
              {audit.slice(0, 10).map((event: any) => (
                <li key={event.id} className="rounded-lg bg-ink-50 p-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-ink-800">{EVENT_LABEL[event.event_type] ?? event.event_type}</span>
                    <span className="num">{event.at}</span>
                  </div>
                  {event.reason && <div className="mt-0.5">{event.reason}</div>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
