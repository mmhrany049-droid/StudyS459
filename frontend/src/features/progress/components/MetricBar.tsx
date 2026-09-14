import { cn } from "@/utils/cn";

interface Props {
  label: string;
  value: number | null;
  barClass: string;
}

/** Coverage and Accuracy are ALWAYS two separate bars (never mixed). */
export default function MetricBar({ label, value, barClass }: Props) {
  const pct = value === null ? null : Math.round(value * 100);
  return (
    <div className="min-w-24 flex-1">
      <div className="flex justify-between text-xs text-slate-500">
        <span>{label}</span>
        <span>{pct === null ? "—" : `${pct}٪`}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded bg-slate-200" title={`${label}: ${pct ?? "—"}`}>
        <div className={cn("h-full", barClass)} style={{ width: `${pct ?? 0}%` }} />
      </div>
    </div>
  );
}
