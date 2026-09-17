import { useEffect, useState } from "react";
import { api, Book } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Meter, Stat } from "../components/ui";
import { JalaliDateInput } from "../components/JalaliDateInput";
import { percent, shiftJalaliDays, todayJalali, toPersianDigits } from "../lib/format";

export default function Goals() {
  const [goals, setGoals] = useState<any[]>([]);
  const [books, setBooks] = useState<Book[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const [form, setForm] = useState({
    title: "",
    goal_type: "three_month",
    target_date: shiftJalaliDays(todayJalali(), 90),
    book_ids: [] as number[],
  });

  function load() {
    setError(null);
    api.get<any>("/goals").then((payload) => setGoals(payload.goals ?? [])).catch((err) => setError(err.message));
    api.get<{ books: Book[] }>("/books").then((payload) => setBooks(payload.books)).catch(() => undefined);
  }
  useEffect(load, []);

  async function create() {
    if (!form.title) {
      setError("عنوان هدف را وارد کن.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/goals", {
        title: form.title,
        goal_type: form.goal_type,
        target_date: form.target_date,
        book_ids: form.book_ids,
      });
      setNotice("هدف ثبت شد؛ حالا در اولویت هفتگی و انتخاب کارها اثر می‌گذارد.");
      setForm({ ...form, title: "", book_ids: [] });
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function refresh(id: number) {
    await api.post(`/goals/${id}/refresh`, {});
    load();
  }

  async function planWeek(id: number) {
    const result = await api.post<any>(`/goals/${id}/plan-week`, {});
    const count = (result.created ?? []).length;
    setNotice(`${toPersianDigits(count)} پیشنهاد کار برای این هدف ساخته شد. ${result.note ?? ""}`.trim());
    load();
  }

  if (error && goals.length === 0) return <ErrorBox message={error} onRetry={load} />;

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="lg:col-span-2 grid gap-5">
        <Card title="هدف‌های فعال">
          {goals.length === 0 ? (
            <Empty
              title="هدفی ثبت نشده"
              hint="هدف سه‌ماهه با تاریخ پایان شمسی ثبت می‌شود و به مراحل ماه/هفته/روز شکسته می‌شود."
            />
          ) : (
            <ul className="grid gap-3">
              {goals.map((goal) => (
                <li key={goal.id} className="rounded-xl border border-ink-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{goal.title}</span>
                        <Badge tone={goal.status === "active" ? "ok" : "muted"}>
                          {goal.status === "active" ? "فعال" : goal.status}
                        </Badge>
                        {goal.progress?.deviation !== undefined && (
                          <Badge tone={(goal.progress?.deviation ?? 0) < -0.1 ? "bad" : "muted"}>
                            انحراف {percent(goal.progress?.deviation ?? 0)}
                          </Badge>
                        )}
                      </div>
                      <div className="muted mt-1">
                        تا {goal.target_date} — {toPersianDigits(goal.days_left ?? 0)} روز مانده
                        {goal.scope_topic_count ? ` — ${toPersianDigits(goal.scope_topic_count)} مبحث در دامنه` : ""}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button className="btn-ghost btn-xs" onClick={() => refresh(goal.id)}>
                        به‌روزرسانی
                      </button>
                      <button className="btn-soft btn-xs" onClick={() => planWeek(goal.id)}>
                        پیشنهاد کار
                      </button>
                      <button className="btn-ghost btn-xs" onClick={() => setOpen(open === goal.id ? null : goal.id)}>
                        جزئیات
                      </button>
                    </div>
                  </div>
                  <div className="mt-3">
                    <Meter value={goal.progress?.ratio ?? 0} label="پیشرفت" />
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <Stat label="پوشش" value={goal.progress?.metrics?.coverage === null ? "نامعلوم" : percent(goal.progress?.metrics?.coverage)} />
                    <Stat label="دقت" value={goal.progress?.metrics?.accuracy === null ? "نامعلوم" : percent(goal.progress?.metrics?.accuracy)} />
                    <Stat label="آمادگی" value={goal.progress?.metrics?.readiness == null ? "نامعلوم" : percent(goal.progress?.metrics?.readiness)} />
                    <Stat label="سؤال‌های دیده‌شده" value={toPersianDigits(goal.progress?.metrics?.question_count ?? 0)} />
                  </div>
                  {open === goal.id && (
                    <div className="mt-3 rounded-xl bg-ink-50 p-3 text-xs leading-6 text-ink-600">
                      <div>دامنه: {JSON.stringify(goal.scope ?? {})}</div>
                      <div className="mt-1">{goal.notes ?? "پیشرفت روی چند بُعد گزارش می‌شود؛ عدد خوش‌بینانه ساخته نمی‌شود."}</div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
          {notice && <div className="mt-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}
        </Card>
      </div>

      <div className="grid gap-5">
        <Card title="هدف جدید (حدود سه ماه)">
          <div className="grid gap-3">
            <div>
              <label className="label">عنوان</label>
              <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="مثلاً تسلط بر حسابان" />
            </div>
            <div>
              <label className="label">نوع</label>
              <select className="input" value={form.goal_type} onChange={(e) => setForm({ ...form, goal_type: e.target.value })}>
                <option value="three_month">سه‌ماهه</option>
                <option value="mastery">تسلط</option>
                <option value="exam">آماده‌سازی امتحان</option>
                <option value="coverage">پوشش مباحث</option>
              </select>
            </div>
            <JalaliDateInput value={form.target_date} onChange={(value) => setForm({ ...form, target_date: value })} label="تاریخ پایان (شمسی)" />
            <div>
              <label className="label">کتاب‌های هدف (چند انتخاب)</label>
              <div className="grid gap-1">
                {books.map((book) => (
                  <label key={book.id} className="flex items-center gap-2 text-xs text-ink-600">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-brand-600"
                      checked={form.book_ids.includes(book.id)}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          book_ids: event.target.checked
                            ? [...form.book_ids, book.id]
                            : form.book_ids.filter((id) => id !== book.id),
                        })
                      }
                    />
                    {book.title}
                  </label>
                ))}
              </div>
            </div>
            <button className="btn-primary" disabled={busy} onClick={create}>
              ثبت هدف
            </button>
          </div>
        </Card>

        <Card title="تفکیک هدف">
          <p className="muted">
            هر هدف به مراحل ماه، هفته و روز شکسته می‌شود و پیشرفت روی پوشش، دقت و آمادگی جدا سنجیده می‌شود. یک عدد کلی
            گمراه‌کننده است.
          </p>
        </Card>
      </div>
    </div>
  );
}
