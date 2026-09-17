import { ReactNode } from "react";
import { faNumber, percent, confidenceBand, toPersianDigits } from "../lib/format";
import type { Explain } from "../lib/api";

export function Card({
  title,
  action,
  children,
  className = "",
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <header className="card-title">
          <span>{title}</span>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Spinner({ label = "در حال بارگذاری…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-6 text-sm text-ink-600">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      {label}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-bad-600/30 bg-bad-100/60 p-4 text-sm text-bad-600">
      <div className="flex items-center justify-between gap-3">
        <span>{message}</span>
        {onRetry && (
          <button className="btn-ghost btn-xs" onClick={onRetry}>
            تلاش دوباره
          </button>
        )}
      </div>
    </div>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-ink-200 bg-white/60 p-6 text-center">
      <p className="text-sm font-medium text-ink-800">{title}</p>
      {hint && <p className="muted mt-1">{hint}</p>}
    </div>
  );
}

export function Badge({ tone = "muted", children }: { tone?: "ok" | "warn" | "bad" | "muted"; children: ReactNode }) {
  const cls = { ok: "badge-ok", warn: "badge-warn", bad: "badge-bad", muted: "badge-muted" }[tone];
  return <span className={cls}>{children}</span>;
}

export function Meter({
  value,
  label,
  tone = "brand",
  unknown = false,
}: {
  value: number | null | undefined;
  label?: string;
  tone?: "brand" | "ok" | "warn" | "bad";
  unknown?: boolean;
}) {
  const colors: Record<string, string> = {
    brand: "bg-brand-500",
    ok: "bg-ok-600",
    warn: "bg-warn-600",
    bad: "bg-bad-600",
  };
  const width = value === null || value === undefined ? 0 : Math.max(0, Math.min(1, value)) * 100;
  return (
    <div>
      {label && (
        <div className="mb-1 flex items-center justify-between text-xs text-ink-600">
          <span>{label}</span>
          <span className="num">{value === null || value === undefined ? "نامعلوم" : percent(value)}</span>
        </div>
      )}
      <div className="h-2 w-full overflow-hidden rounded-full bg-ink-100">
        {unknown || value === null || value === undefined ? (
          <div className="h-full w-full bg-[repeating-linear-gradient(45deg,#d5dae3,#d5dae3_4px,transparent_4px,transparent_8px)]" />
        ) : (
          <div className={`h-full rounded-full ${colors[tone]}`} style={{ width: `${width}%` }} />
        )}
      </div>
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl bg-ink-50 p-3">
      <div className="text-xs text-ink-600">{label}</div>
      <div className="num mt-1 text-lg font-semibold text-ink-900">{value}</div>
      {hint && <div className="muted mt-0.5">{hint}</div>}
    </div>
  );
}

/** The four mandatory questions, shown wherever the system decides something. */
export function ExplainBox({ explain, compact = false }: { explain?: Explain | null; compact?: boolean }) {
  if (!explain) return null;
  return (
    <div className={`rounded-xl border border-ink-200 bg-ink-50/70 ${compact ? "p-3" : "p-4"} text-xs leading-6`}>
      <div className="grid gap-2">
        <Row label="چی؟" text={explain.what} />
        <Row label="چرا؟" text={explain.why} />
        {explain.evidence && Object.keys(explain.evidence).length > 0 && (
          <Row
            label="شواهد؟"
            text={
              <ul className="list-inside list-disc space-y-0.5">
                {Object.entries(explain.evidence).map(([key, value]) => (
                  <li key={key}>
                    <span className="text-ink-600">{evidenceLabel(key)}: </span>
                    <span className="num">{formatEvidence(value)}</span>
                  </li>
                ))}
              </ul>
            }
          />
        )}
        {explain.what_can_i_change && explain.what_can_i_change.length > 0 && (
          <Row
            label="چه چیزی را می‌توانم تغییر بدهم؟"
            text={
              <ul className="list-inside list-disc space-y-0.5">
                {explain.what_can_i_change.map((item: string, index: number) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            }
          />
        )}
        {explain.confidence !== undefined && (
          <div className="text-ink-600">
            اطمینان: <span className="num">{confidenceBand(explain.confidence)}</span>
            {explain.model_version && <span className="mr-2 text-ink-400">نسخه مدل {toPersianDigits(explain.model_version)}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, text }: { label: string; text: ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="shrink-0 font-semibold text-ink-800">{label}</span>
      <div className="text-ink-800">{text}</div>
    </div>
  );
}

function evidenceLabel(key: string): string {
  const map: Record<string, string> = {
    accuracy: "دقت",
    coverage: "پوشش",
    confidence: "اطمینان",
    retention: "نگه‌داشت",
    uncertainty: "عدم‌قطعیت",
    attempts: "تلاش‌ها",
    exam_days: "روز تا امتحان",
    score: "امتیاز اولویت",
    weight: "وزن",
    contribution: "سهم",
    reason: "دلیل",
    value: "مقدار",
    recall: "یادآوری",
    prerequisite_health: "وضعیت پیش‌نیاز",
    exam_readiness: "آمادگی امتحان",
    repeated_error_signal: "سیگنال خطای تکرارشده",
    recency_days: "فاصله زمانی (روز)",
    question_count: "تعداد سؤال",
    pool_size: "اندازه بانک",
    days_remaining: "روزهای باقی‌مانده",
    wrong: "غلط",
    unanswered: "نزده",
    total: "کل",
    invariant_ok: "صحت جمع‌بندی",
  };
  return map[key] ?? key;
}

function formatEvidence(value: unknown): string {
  if (value === null || value === undefined) return "نامعلوم";
  if (typeof value === "number") {
    if (Number.isInteger(value)) return faNumber(value);
    return faNumber(value, 3);
  }
  if (typeof value === "boolean") return value ? "بله" : "نه";
  if (Array.isArray(value)) return value.map((item) => formatEvidence(item)).join("، ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${evidenceLabel(key)}: ${formatEvidence(item)}`)
      .join(" | ");
  }
  return String(value);
}

export function Confidence({ value }: { value: number | null | undefined }) {
  return (
    <span className="text-xs text-ink-600">
      اطمینان: <span className="num">{confidenceBand(value)}</span>
    </span>
  );
}
