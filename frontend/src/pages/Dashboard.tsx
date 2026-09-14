import { useHealth } from "@/hooks/useHealth";

/** Phase-0 dashboard: proves frontend <-> backend wiring via /health. */
export default function Dashboard() {
  const health = useHealth();

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">داشبورد</h1>
      <div className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 font-semibold">وضعیت اتصال به سرور</h2>
        {health.status === "loading" && <p>در حال بررسی…</p>}
        {health.status === "error" && (
          <p className="text-red-600">عدم اتصال به سرور: {health.message}</p>
        )}
        {health.status === "ok" && (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-slate-500">وضعیت</dt>
            <dd className="font-semibold text-green-700">{health.data.status}</dd>
            <dt className="text-slate-500">نسخه</dt>
            <dd>{health.data.version}</dd>
            <dt className="text-slate-500">محیط</dt>
            <dd>{health.data.env}</dd>
            <dt className="text-slate-500">منطقه زمانی</dt>
            <dd>{health.data.timezone}</dd>
          </dl>
        )}
      </div>
      <p className="text-sm text-slate-500">
        ویجت‌های واقعی داشبورد (وضعیت امروز/هفته، اهداف، ضعف‌ها، پیشنهادها، امتیاز) از Phase 3 به بعد اضافه می‌شوند.
      </p>
    </div>
  );
}
