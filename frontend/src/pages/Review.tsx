import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat } from "../components/ui";
import { toPersianDigits } from "../lib/format";

type ReviewItem = {
  id: number;
  question_id: number;
  sequence_no: number;
  topic_id: number;
  topic_title?: string;
  reason: string;
  priority: string;
  wrong_count: number;
  unanswered_count: number;
  scheduled_for: string;
  evidence?: Record<string, unknown>;
};

export default function Review() {
  const [queue, setQueue] = useState<{ stats: any; items: ReviewItem[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    setError(null);
    api.get<any>("/review/queue").then(setQueue).catch((err) => setError(err.message));
  }
  useEffect(load, []);

  async function build() {
    setBusy(true);
    try {
      const result = await api.post<any>("/review/build", {});
      const built = (result.items ?? []).length;
      setNotice(
        built > 0
          ? `${toPersianDigits(built)} آیتم مرور ساخته شد (${result.message ?? "خوشه مباحث نزدیک"}).`
          : "برای مرور آیتم تازه‌ای پیدا نشد؛ صف فعلی همان است که هست.",
      );
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function resolve(id: number) {
    await api.post(`/review/items/${id}/resolve`, {});
    load();
  }

  async function snooze(id: number, days = 2) {
    await api.post(`/review/items/${id}/snooze`, { days });
    load();
  }

  if (error) return <ErrorBox message={error} onRetry={load} />;
  if (!queue) return <Spinner />;

  return (
    <div className="grid gap-5 lg:grid-cols-4">
      <div className="lg:col-span-3">
        <Card
          title="صف مرور"
          action={
            <button className="btn-soft btn-xs" disabled={busy} onClick={build}>
              ساخت صف از تلاش‌ها
            </button>
          }
        >
          {notice && <div className="mb-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}
          {queue.items.length === 0 ? (
            <Empty
              title="صف مرور خالی است"
              hint="آیتم مرور فقط از غلط‌ها و نزده‌های واقعی ساخته می‌شود؛ اگر جلسه‌ای ثبت نشده باشد چیزی برای مرور نیست."
            />
          ) : (
            <ul className="grid gap-2">
              {queue.items.map((item) => (
                <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-ink-200 p-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="num text-sm">سؤال {toPersianDigits(item.sequence_no)}</span>
                      <Badge tone={item.reason === "wrong" ? "bad" : "warn"}>
                        {item.reason === "wrong" ? "غلط" : "نزده"}
                      </Badge>
                      <Badge tone={item.priority === "critical" ? "bad" : "muted"}>
                        {item.priority === "critical" ? "بحرانی" : "عادی"}
                      </Badge>
                    </div>
                    <div className="muted mt-1">
                      {item.topic_title} — زمان پیشنهادی {item.scheduled_for}
                      {item.wrong_count > 0 && ` — ${toPersianDigits(item.wrong_count)} بار غلط`}
                      {item.unanswered_count > 0 && ` — ${toPersianDigits(item.unanswered_count)} بار نزده`}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button className="btn-primary btn-xs" onClick={() => resolve(item.id)}>
                      حل شد
                    </button>
                    <button className="btn-ghost btn-xs" onClick={() => snooze(item.id, 2)}>
                      ۲ روز بعد
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-5">
        <Card title="وضعیت صف">
          <div className="grid gap-2">
            <Stat label="باز" value={toPersianDigits(queue.stats?.open ?? 0)} />
            <Stat label="سرسید‌شده امروز" value={toPersianDigits(queue.stats?.due_today ?? 0)} />
            <Stat label="بحرانی" value={toPersianDigits(queue.stats?.critical ?? 0)} />
          </div>
        </Card>
        <Card title="قواعد مرور">
          <ul className="grid gap-2 text-xs leading-6 text-ink-600">
            <li>آیتمی که در مرور درست جواب بدهی، از صف خارج می‌شود؛ ولی تاریخچه‌اش می‌ماند.</li>
            <li>آیتم‌هایی که دو بار غلط شده‌اند، بحرانی می‌شوند و زودتر می‌آیند.</li>
            <li>مرور ترجیحاً مبحث‌های نزدیک را با هم می‌آورد و بین‌شان سؤال جدید پخش نمی‌کند.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
