import { useEffect, useRef, useState, type ReactNode } from "react";
import { fa } from "../lib/api";

/* ---------------- states ---------------- */
export function Loading({ label = "در حال بارگذاری…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-14 text-ink-soft">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card animate-rise border-rose-200 bg-rose-50">
      <div className="flex items-start gap-3">
        <span className="text-xl">⚠️</span>
        <div className="flex-1">
          <p className="font-medium text-rose-800">مشکلی پیش آمد</p>
          <p className="mt-1 text-sm text-rose-700">{message}</p>
        </div>
        {onRetry && (
          <button className="btn-ghost btn-xs" onClick={onRetry}>
            تلاش دوباره
          </button>
        )}
      </div>
    </div>
  );
}

export function Empty({ icon = "📭", title, hint, action }: { icon?: string; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex animate-rise flex-col items-center justify-center rounded-2xl border border-dashed border-surface-line bg-white/60 px-6 py-12 text-center">
      <div className="mb-3 text-4xl opacity-70">{icon}</div>
      <p className="font-semibold text-ink">{title}</p>
      {hint && <p className="mt-1.5 max-w-md text-sm leading-6 text-ink-soft">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/* ---------------- primitives ---------------- */
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card animate-rise ${className}`}>{children}</div>;
}

export function Stat({ label, value, sub, tone = "default", icon }: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "default" | "good" | "warn" | "bad" | "brand";
  icon?: string;
}) {
  const tones: Record<string, string> = {
    default: "text-ink",
    good: "text-emerald-600",
    warn: "text-amber-600",
    bad: "text-rose-600",
    brand: "text-brand-600",
  };
  return (
    <div className="card-tight animate-rise">
      <div className="flex items-center gap-1.5 text-xs text-ink-soft">
        {icon && <span>{icon}</span>}
        <span>{label}</span>
      </div>
      <div className={`tabular mt-1.5 text-2xl font-bold ${tones[tone]}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-ink-mute">{sub}</div>}
    </div>
  );
}

export function Bar({ value, tone = "brand", height = "h-2" }: { value: number; tone?: string; height?: string }) {
  const tones: Record<string, string> = {
    brand: "bg-brand-500",
    good: "bg-emerald-500",
    warn: "bg-amber-500",
    bad: "bg-rose-500",
  };
  return (
    <div className={`w-full overflow-hidden rounded-full bg-slate-100 ${height}`}>
      <div
        className={`h-full rounded-full transition-all duration-500 ${tones[tone] || tones.brand}`}
        style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
      />
    </div>
  );
}

export function Chip({ children, tone = "slate" }: { children: ReactNode; tone?: string }) {
  const tones: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700",
    brand: "bg-brand-50 text-brand-700",
    good: "bg-emerald-50 text-emerald-700",
    warn: "bg-amber-50 text-amber-700",
    bad: "bg-rose-50 text-rose-700",
    sky: "bg-sky-50 text-sky-700",
  };
  return <span className={`chip ${tones[tone] || tones.slate}`}>{children}</span>;
}

export function Modal({ open, onClose, title, children, wide = false }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm">
      <div
        className={`my-8 w-full animate-pop rounded-2xl bg-white p-6 shadow-xl ${wide ? "max-w-4xl" : "max-w-lg"}`}
      >
        <div className="mb-5 flex items-center justify-between gap-4">
          <h3 className="text-lg font-bold">{title}</h3>
          <button className="btn-ghost btn-xs" onClick={onClose} aria-label="بستن">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/* ---------------- toast ---------------- */
type Toast = { id: number; text: string; tone: "ok" | "err" | "info" };
let pushToast: ((t: Omit<Toast, "id">) => void) | null = null;

export function toast(text: string, tone: Toast["tone"] = "ok") {
  pushToast?.({ text, tone });
}

export function Toaster() {
  const [items, setItems] = useState<Toast[]>([]);
  const seq = useRef(0);
  useEffect(() => {
    pushToast = (t) => {
      const id = ++seq.current;
      setItems((prev) => [...prev, { ...t, id }]);
      setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== id)), 4200);
    };
    return () => {
      pushToast = null;
    };
  }, []);
  const tones = {
    ok: "bg-emerald-600",
    err: "bg-rose-600",
    info: "bg-slate-800",
  };
  return (
    <div className="pointer-events-none fixed bottom-5 left-5 z-[60] flex flex-col gap-2">
      {items.map((t) => (
        <div
          key={t.id}
          className={`animate-pop rounded-xl px-4 py-2.5 text-sm font-medium text-white shadow-lg ${tones[t.tone]}`}
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}

/* ---------------- four-choice row (S1) ---------------- */
export function ChoiceRow({
  value,
  onChange,
  compact = false,
}: {
  value: number | null | undefined;
  onChange: (v: number | null) => void;
  compact?: boolean;
}) {
  const answered = value !== undefined;
  return (
    <div className={`flex items-center ${compact ? "gap-1" : "gap-1.5"}`}>
      {[1, 2, 3, 4].map((n) => (
        <button
          key={n}
          type="button"
          className="choice-btn"
          data-active={value === n}
          onClick={() => onChange(value === n ? undefined as unknown as null : n)}
          title={`گزینه ${fa(n)}`}
        >
          {fa(n)}
        </button>
      ))}
      <button
        type="button"
        className="choice-btn w-auto px-2.5 text-xs"
        data-skip="true"
        data-active={answered && value === null}
        onClick={() => onChange(value === null ? (undefined as unknown as null) : null)}
        title="نزده"
      >
        نزده
      </button>
    </div>
  );
}
