interface Props {
  title: string;
  phase: string;
}

/** Phase-0 route shell — real UI arrives in later phases (spec 11). */
export default function Placeholder({ title, phase }: Props) {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="rounded bg-white p-4 text-sm text-slate-500 shadow">
        این صفحه در {phase} پیاده‌سازی می‌شود (اسکلت Phase 0).
      </p>
    </div>
  );
}
