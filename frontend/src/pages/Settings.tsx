import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat } from "../components/ui";
import { toPersianDigits } from "../lib/format";

const MODEL_VERSION_LABEL: Record<string, string> = {
  V1: "نسخه ۱",
  V2: "نسخه ۲",
  V2_1: "نسخه ۲.۱",
  V2_2: "نسخه ۲.۲",
  V2_C: "قرارداد نسخه ۲",
  V2_R: "قرارداد مرور نسخه ۲",
  V3: "نسخه ۳",
  USER_SPECIFIC: "شخصی‌سازی‌شده",
};

const EVIDENCE_LABEL: Record<string, string> = {
  EMPIRICAL: "شواهد تجربی",
  RESEARCH_SUPPORTED: "پشتوانه پژوهشی",
  HEURISTIC: "تجربی/سرانگشتی",
  USER_SPECIFIC: "وابسته به کاربر",
  EXPERIMENTAL: "آزمایشی",
};

export default function Settings() {
  const [me, setMe] = useState<any>(null);
  const [params, setParams] = useState<any>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [telegram, setTelegram] = useState<any>(null);

  function load() {
    setError(null);
    api.get<any>("/me").then(setMe).catch((err) => setError(err.message));
    api.get<any>("/config/params").then(setParams).catch(() => undefined);
    api.get<any>("/integrations/telegram").then(setTelegram).catch(() => undefined);
  }
  useEffect(load, []);

  async function saveMe(patch: Record<string, unknown>) {
    await api.patch("/me", patch);
    setNotice("ذخیره شد.");
    load();
  }

  if (error) return <ErrorBox message={error} onRetry={load} />;
  if (!me || !params) return <Spinner />;

  const entries = Object.entries(params.params ?? {}).filter(([key, value]: any) =>
    filter ? key.includes(filter) || String(value?.provenance ?? "").includes(filter) : true,
  );

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="grid gap-5 lg:col-span-2">
        <Card title="پارامترهای مدل" action={<Badge tone="muted">نسخه {toPersianDigits(params.model_version)}</Badge>}>
          <p className="muted mb-3">
            هیچ عددی در کد هارد‌کد نشده است؛ هر پارامتر منبع، سطح شواهد و توضیح دارد. تغییر پارامتر بدون بازسازی داده
            مشتق، فقط یک ادعا است.
          </p>
          <input
            className="input mb-3"
            placeholder="جستجو در پارامترها…"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
          {entries.length === 0 ? (
            <Empty title="پارامتری پیدا نشد" />
          ) : (
            <ul className="grid max-h-[60vh] gap-1 overflow-y-auto">
              {entries.map(([key, value]: any) => (
                <li key={key} className="rounded-xl border border-ink-200 p-2 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <code dir="ltr" className="text-[11px] text-ink-800">
                      {key}
                    </code>
                    <span className="num font-medium text-ink-900">{String(value?.value)}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-ink-600">
                    <span>{MODEL_VERSION_LABEL[value?.provenance] ?? value?.provenance}</span>
                    <span>•</span>
                    <span>{EVIDENCE_LABEL[value?.confidence] ?? value?.confidence}</span>
                    {value?.note && (
                      <>
                        <span>•</span>
                        <span className="text-ink-400">{value.note}</span>
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-5">
        <Card title="کاربر">
          <div className="grid gap-2">
            <Stat label="نام" value={me.display_name} />
            <Stat label="پایه" value={me.grade} />
            <Stat label="رشته" value={me.track} />
            <Stat label="امروز" value={me.today_long} />
            <Stat label="سکه" value={toPersianDigits(me.coins)} />
            <Stat label="زنجیره" value={toPersianDigits(me.streak)} />
          </div>
          <label className="mt-3 flex items-center gap-2 text-xs text-ink-600">
            <input
              type="checkbox"
              className="h-4 w-4 accent-brand-600"
              checked={!!me.quiet_mode}
              onChange={(event) => saveMe({ quiet_mode: event.target.checked })}
            />
            حالت کم‌حرف (حداکثر یک کارت پیشنهاد در روز)
          </label>
          <label className="mt-2 flex items-center gap-2 text-xs text-ink-600">
            <input
              type="checkbox"
              className="h-4 w-4 accent-brand-600"
              checked={!!me.auto_time_adjust}
              onChange={(event) => saveMe({ auto_time_adjust: event.target.checked })}
            />
            تنظیم خودکار زمان بر پایه زمان واقعی
          </label>
          {notice && <div className="mt-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}
        </Card>

        <Card title="تلگرام (اختیاری)">
          {telegram ? (
            <>
              <div className="flex items-center justify-between text-xs">
                <span>وضعیت</span>
                <Badge tone={telegram.enabled ? "ok" : "muted"}>{telegram.enabled ? "فعال" : "غیرفعال"}</Badge>
              </div>
              <p className="muted mt-2">{telegram.message}</p>
              <div className="mt-3 grid gap-2">
                <input
                  className="input"
                  placeholder="chat id"
                  onChange={(event) => setTelegram({ ...telegram, chat_id: event.target.value })}
                />
                <button
                  className="btn-soft btn-xs"
                  onClick={async () => {
                    await api.post(`/integrations/telegram/connect?chat_id=${encodeURIComponent(telegram.chat_id ?? "")}`);
                    load();
                  }}
                >
                  اتصال
                </button>
                <p className="muted">خاموش بودن تلگرام هیچ قابلیتی را محدود نمی‌کند؛ کل محصول بدون آن کار می‌کند.</p>
              </div>
            </>
          ) : (
            <p className="muted">وضعیت تلگرام در دسترس نیست.</p>
          )}
        </Card>

        <Card title="سیاست‌های ثابت">
          <ul className="grid gap-2 text-xs leading-6 text-ink-600">
            <li>تا وقتی «ثبت‌نشده» را وارد نکنی، «نزده» حساب نمی‌شود.</li>
            <li>یک خطا ضعف نیست؛ تکرار خطا با شواهد کافی بررسی می‌شود.</li>
            <li>یک موفقیت تسلط نیست؛ اطمینان با تعداد شواهد بالا می‌رود.</li>
            <li>وقت آزاد تقویم، ظرفیت واقعی نیست.</li>
            <li>هیچ کار انجام‌نشده «شکست» شمرده نمی‌شود؛ فقط جابه‌جا می‌شود.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
