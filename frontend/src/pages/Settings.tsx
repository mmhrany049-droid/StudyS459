import { useEffect, useState } from "react";
import { fetchMe, patchMe } from "@/api/users";
import type { User } from "@/types/users";

const TIMEZONES = [
  "Asia/Tehran",
  "UTC",
  "Europe/Berlin",
  "Asia/Dubai",
  "America/New_York",
];

export default function Settings() {
  const [me, setMe] = useState<User | null>(null);
  const [name, setName] = useState("");
  const [tz, setTz] = useState("Asia/Tehran");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMe()
      .then((u) => {
        setMe(u);
        setName(u.display_name);
        setTz(u.timezone);
      })
      .catch(() => setError("خطا در دریافت تنظیمات."));
  }, []);

  const save = async () => {
    setError(null);
    setSaved(false);
    try {
      const u = await patchMe({ display_name: name.trim() || undefined, timezone: tz });
      setMe(u);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  if (error) return <p className="text-red-600">{error}</p>;
  if (!me) return <p>در حال بارگذاری…</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">تنظیمات</h1>

      <section className="space-y-3 rounded-lg bg-white p-4 shadow-sm">
        <h2 className="font-bold">پروفایل</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label className="w-24 text-slate-500">نام نمایشی</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label className="w-24 text-slate-500">منطقه زمانی</label>
          <select
            value={TIMEZONES.includes(tz) ? tz : ""}
            onChange={(e) => setTz(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          >
            {!TIMEZONES.includes(tz) && <option value="">{tz} (فعلی)</option>}
            {TIMEZONES.map((z) => (
              <option key={z} value={z}>{z}</option>
            ))}
          </select>
        </div>
        <p className="text-xs text-slate-500">
          منطقه زمانی مبنای روزها، روندها و streak است. پایه تحصیلی و رشته از ایمپورت کتاب می‌آید.
        </p>
        <button
          type="button"
          onClick={() => void save()}
          className="rounded bg-slate-900 px-4 py-1 text-sm text-white"
        >
          ذخیره
        </button>
        {saved && <p className="text-sm text-green-700">✅ ذخیره شد.</p>}
      </section>

      <section className="rounded-lg bg-white p-4 text-sm shadow-sm">
        <h2 className="mb-2 font-bold">درباره</h2>
        <p className="text-slate-600">
          SS459 نسخه ۱ — تک‌کاربره، بدون نیاز به اینترنت دائمی برای منطق اصلی، کاملاً بدون تلگرام.
        </p>
      </section>
    </div>
  );
}
