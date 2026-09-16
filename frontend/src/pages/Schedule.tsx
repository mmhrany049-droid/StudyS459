import { Card, Chip, Empty, ErrorBox, Loading, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa, WEEKDAYS } from "../lib/api";
import type { ScheduleItem } from "../lib/types";

export default function Schedule() {
  const { data, error, loading, reload } = useFetch<ScheduleItem[]>("/schedules");

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const patch = async (id: number, params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    await api.patch(`/schedules/${id}?${qs}`);
    toast("ذخیره شد");
    reload();
  };

  const seed = async () => {
    const r = await api.post<{ classes_created: number }>("/schedules/seed-defaults");
    toast(r.classes_created ? `${fa(r.classes_created)} کلاس پیش‌فرض ساخته شد` : "کلاس‌های پیش‌فرض از قبل موجودند");
    reload();
  };

  const override = async (offset: number) => {
    const d = new Date();
    d.setDate(d.getDate() + offset);
    await api.post(`/school-day-overrides?day=${d.toISOString().slice(0, 10)}&is_school_day=false&reason=${encodeURIComponent("مدرسه نمی‌روم")}`);
    toast("ظرفیت آن روز ۳۵٪ افزایش یافت (حداقل ۱۸۰ دقیقه)");
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">کلاس‌ها و تقویم</h1>
          <p className="muted mt-1">
            روز کلاس هر درس، تست‌های همان درس را +۱۵ امتیاز اولویت می‌دهد و ظرفیت آن روز را کاهش می‌دهد.
          </p>
        </div>
        <button className="btn-ghost" onClick={seed}>
          بازنشانی کلاس‌های پیش‌فرض
        </button>
      </div>

      {!data || data.length === 0 ? (
        <Empty
          icon="🗓️"
          title="کلاسی تعریف نشده"
          hint="سه کلاس تقویتی پیش‌فرض (حسابان، شیمی، فیزیک) را بساز و روز/ساعتشان را مشخص کن."
          action={
            <button className="btn-primary" onClick={seed}>
              افزودن کلاس‌های پیش‌فرض
            </button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {data.map((s) => (
            <Card key={s.id}>
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-bold">{s.title}</h3>
                {s.subject && <Chip tone="brand">{s.subject}</Chip>}
              </div>
              {s.source === "default_seed_v2" && (
                <p className="mt-1 text-xs text-ink-mute">کلاس پیش‌فرض نسخه ۲</p>
              )}
              <div className="mt-4 space-y-3">
                <div>
                  <label className="label">روز هفته</label>
                  <select
                    className="input"
                    value={s.day_of_week ?? -1}
                    onChange={(e) => patch(s.id, { day_of_week: e.target.value })}
                  >
                    <option value={-1}>— مشخص نشده —</option>
                    {WEEKDAYS.map((d, i) => (
                      <option key={i} value={i}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="label">شروع</label>
                    <input
                      type="time"
                      className="input"
                      value={s.start_time || ""}
                      onChange={(e) => patch(s.id, { start_time: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="label">پایان</label>
                    <input
                      type="time"
                      className="input"
                      value={s.end_time || ""}
                      onChange={(e) => patch(s.id, { end_time: e.target.value })}
                    />
                  </div>
                </div>
              </div>
              {s.day_name && (
                <p className="mt-3 rounded-xl bg-brand-50 p-2.5 text-xs text-brand-700">
                  📅 {s.day_name}
                  {s.start_time ? ` — ${fa(s.start_time)}` : ""}
                  {s.end_time ? ` تا ${fa(s.end_time)}` : ""}
                </p>
              )}
            </Card>
          ))}
        </div>
      )}

      <Card>
        <h2 className="section-title mb-1">امروز/فردا مدرسه نمی‌روم</h2>
        <p className="muted mb-4">
          ظرفیت آن روز ۳۵٪ افزایش می‌یابد (حداقل ۱۸۰ دقیقه). هیچ کاری خودکار حذف نمی‌شود.
        </p>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={() => override(0)}>
            امروز مدرسه نمی‌روم
          </button>
          <button className="btn-ghost" onClick={() => override(1)}>
            فردا مدرسه نمی‌روم
          </button>
        </div>
      </Card>

      <Card>
        <h2 className="section-title mb-3">هفته ایرانی</h2>
        <div className="grid grid-cols-7 gap-2">
          {WEEKDAYS.map((d, i) => (
            <div
              key={i}
              className={`rounded-xl p-3 text-center text-sm ${
                i <= 4 ? "bg-sky-50 text-sky-700" : "bg-emerald-50 text-emerald-700"
              }`}
            >
              <p className="font-medium">{d}</p>
              <p className="mt-1 text-[10px]">{i <= 4 ? "مدرسه" : "آزاد / جبرانی"}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-ink-mute">
          برنامه‌ریزی اصلی جمعه برای هفته بعد است • پنج‌شنبه و جمعه وزن مرور بالاتر است.
        </p>
      </Card>
    </div>
  );
}
