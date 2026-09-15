import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchRewardsSummary } from "@/api/rewards";
import { useHealth } from "@/hooks/useHealth";
import type { RewardsSummary } from "@/types/rewards";

/** Dashboard: server health + rewards strip (full widgets land in Phase 8). */
export default function Dashboard() {
  const health = useHealth();
  const [rewards, setRewards] = useState<RewardsSummary | null>(null);

  useEffect(() => {
    fetchRewardsSummary().then(setRewards).catch(() => undefined);
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">داشبورد</h1>
      {rewards && (
        <Link
          to="/rewards"
          className="flex items-center justify-between rounded bg-white p-4 shadow hover:bg-slate-50"
        >
          <span className="text-lg font-bold tabular-nums">⭐ {rewards.total_points}</span>
          <span className="text-sm tabular-nums">🔥 {rewards.current_streak} روز</span>
          <span className="text-sm text-slate-600">
            🏅 {rewards.badges.slice(0, 2).map((b) => b.title).join("، ") || "بدون نشان"}
            {rewards.badge_count > 2 ? ` (+${rewards.badge_count - 2})` : ""}
          </span>
        </Link>
      )}
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
