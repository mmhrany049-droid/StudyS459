import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, Card, Chip, Empty, ErrorBox, Loading, Modal, Stat, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa, pct } from "../lib/api";
import type { Book, ReadinessPlan, TreeNode, UpcomingExam } from "../lib/types";

export default function Readiness() {
  const { data: list, error, loading, reload } = useFetch<UpcomingExam[]>("/upcoming-exams");
  const [add, setAdd] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const active = selected ?? list?.[0]?.id ?? null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">آمادگی امتحان</h1>
          <p className="muted mt-1">
            تاریخ امتحان + مباحث تحت پوشش را بده؛ سیستم از بانک همان مباحث تست پیشنهاد می‌دهد.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setAdd(true)}>
          ＋ آمادگی امتحان جدید
        </button>
      </div>

      {!list || list.length === 0 ? (
        <Empty
          icon="🎯"
          title="هنوز امتحان پیش‌رویی تعریف نشده"
          hint="عنوان، تاریخ و مباحث امتحان را وارد کن تا برنامه آمادگی بر اساس Coverage، غلط/نزده‌ها و تست‌های دیده‌نشده ساخته شود."
          action={
            <button className="btn-primary" onClick={() => setAdd(true)}>
              ＋ آمادگی امتحان جدید
            </button>
          }
        />
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            {list.map((u) => (
              <button
                key={u.id}
                onClick={() => setSelected(u.id)}
                className={`card animate-rise text-right transition ${
                  active === u.id ? "border-brand-400 ring-2 ring-brand-100" : "hover:border-brand-200"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-bold">{u.title}</h3>
                  <Chip tone={u.days_left <= 3 ? "bad" : u.days_left <= 14 ? "warn" : "slate"}>
                    {u.days_left < 0 ? "گذشته" : u.days_left === 0 ? "امروز" : `${fa(u.days_left)} روز`}
                  </Chip>
                </div>
                <p className="muted mt-1.5">{u.exam_date_jalali}</p>
                <p className="mt-2 text-xs text-ink-mute">{fa(u.topic_count)} مبحث تحت پوشش</p>
                <span
                  className="btn-danger btn-xs mt-3 inline-block"
                  onClick={async (e) => {
                    e.stopPropagation();
                    await api.del(`/upcoming-exams/${u.id}`);
                    toast("حذف شد");
                    setSelected(null);
                    reload();
                  }}
                >
                  🗑 حذف
                </span>
              </button>
            ))}
          </div>

          {active && <Plan id={active} />}
        </>
      )}

      <AddModal open={add} onClose={() => setAdd(false)} onDone={reload} />
    </div>
  );
}

function Plan({ id }: { id: number }) {
  const [wrongOnly, setWrongOnly] = useState(false);
  const { data, error, loading, reload } = useFetch<ReadinessPlan>(
    `/upcoming-exams/${id}/suggested-tasks?wrong_only=${wrongOnly}`,
    [id, wrongOnly]
  );
  const nav = useNavigate();

  if (loading) return <Loading label="در حال ساخت برنامه آمادگی…" />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const startTest = async (nodeId: number, count: number, parity: string) => {
    try {
      const s = await api.post<{ id: number }>("/test-sessions", { node_id: nodeId, count, parity });
      nav(`/test/${s.id}`);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const materialize = async () => {
    try {
      const r = await api.post<{ created: number }>(`/upcoming-exams/${id}/materialize`);
      toast(r.created ? `${fa(r.created)} کار «آمادگی امتحان» به برنامه اضافه شد` : "کار جدیدی لازم نبود");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="space-y-5">
      {data.countdown_mode && (
        <Card className="border-amber-200 bg-amber-50">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-bold text-amber-900">
                ⏳ {fa(data.upcoming_exam.days_left)} روز تا «{data.upcoming_exam.title}»
              </h2>
              <p className="mt-1 text-sm text-amber-800">
                {pct(data.low_coverage_ratio)} از مباحث هنوز Coverage زیر ۳۰٪ دارند (
                {fa(data.topics_low_coverage)} از {fa(data.topics_total)} مبحث).
              </p>
            </div>
            <Chip tone="warn">{data.upcoming_exam.exam_date_jalali}</Chip>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="مباحث تحت پوشش" value={fa(data.topics_total)} />
        <Stat label="Coverage زیر ۳۰٪" value={fa(data.topics_low_coverage)} tone="bad" />
        <Stat label="تست پیشنهادی" value={fa(data.total_suggested_tests)} tone="brand" />
        <Stat label="ظرفیت تخمینی هفته" value={fa(data.week_capacity_tests)} sub="تست" />
      </div>

      {data.capacity_warning && (
        <Card className="border-rose-200 bg-rose-50">
          <p className="text-sm text-rose-800">⚠️ {data.capacity_warning}</p>
        </Card>
      )}

      {data.missing_bank.length > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <p className="mb-2 text-sm font-medium text-amber-900">
            این مباحث بانک تست ندارند و پیشنهادی برایشان ممکن نیست:
          </p>
          <ul className="space-y-1 text-xs leading-6 text-amber-800">
            {data.missing_bank.map((t, i) => (
              <li key={i}>• {t}</li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="section-title">پیشنهاد تست از بانک همان مباحث</h2>
          <div className="flex gap-2">
            <button className={wrongOnly ? "btn-soft btn-xs" : "btn-ghost btn-xs"} onClick={() => setWrongOnly(!wrongOnly)}>
              فقط غلط/نزده‌ها
            </button>
            <button className="btn-primary btn-xs" onClick={materialize}>
              ＋ افزودن به برنامه
            </button>
          </div>
        </div>

        {data.suggestions.length === 0 ? (
          <Empty icon="✅" title="پیشنهادی نیست" hint="یا مباحث بانک ندارند یا همه چیز پوشش داده شده." />
        ) : (
          <div className="space-y-2.5">
            {data.suggestions.map((s, i) => (
              <div key={s.node_id} className="rounded-xl border border-surface-line p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="tabular flex h-6 w-6 items-center justify-center rounded-lg bg-brand-50 text-xs font-bold text-brand-700">
                        {fa(i + 1)}
                      </span>
                      <span className="truncate font-medium" title={s.title}>
                        {s.short_title}
                      </span>
                      <Chip tone={s.parity === "odd" ? "sky" : "brand"}>
                        {s.parity === "odd" ? "فرد" : "زوج"}
                      </Chip>
                    </div>
                    <p className="mt-1 truncate text-xs text-ink-mute" title={s.title}>
                      {s.title}
                    </p>
                    <p className="mt-1 text-xs text-ink-soft">{s.reason}</p>
                  </div>
                  <button
                    className="btn-soft btn-xs shrink-0"
                    onClick={() => startTest(s.node_id, s.suggested_count, s.parity)}
                  >
                    شروع {fa(s.suggested_count)} تست
                  </button>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  <div>
                    <div className="mb-1 flex justify-between text-xs text-ink-soft">
                      <span>Coverage</span>
                      <span className="tabular">{pct(s.coverage)}</span>
                    </div>
                    <Bar value={s.coverage} tone={s.coverage < 0.3 ? "bad" : "good"} height="h-1.5" />
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    {s.open_review > 0 && <Chip tone="bad">{fa(s.open_review)} غلط/نزده باز</Chip>}
                    {s.unseen > 0 && <Chip tone="warn">{fa(s.unseen)} دیده‌نشده</Chip>}
                  </div>
                  <div className="text-left text-xs text-ink-mute">اولویت {fa(s.priority)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function AddModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { data: books } = useFetch<Book[]>("/books");
  const [bookId, setBookId] = useState<number | null>(null);
  const { data: tree } = useFetch<{ nodes: TreeNode[] }>(bookId ? `/books/${bookId}/nodes?with_stats=false` : null, [
    bookId,
  ]);
  const [title, setTitle] = useState("");
  const [examDate, setExamDate] = useState("");
  const [picked, setPicked] = useState<{ id: number; label: string }[]>([]);

  const flatten = (nodes: TreeNode[], depth = 0): { id: number; label: string; leaf: boolean }[] =>
    nodes.flatMap((n) => [
      { id: n.id, label: "\u00a0".repeat(depth * 3) + n.title, leaf: n.children.length === 0 },
      ...flatten(n.children, depth + 1),
    ]);

  const submit = async () => {
    if (!title.trim() || !examDate) return toast("عنوان و تاریخ لازم است", "err");
    if (!picked.length) return toast("حداقل یک مبحث انتخاب کن", "err");
    try {
      await api.post("/upcoming-exams", {
        title,
        exam_date: examDate,
        node_ids: picked.map((p) => p.id),
      });
      toast("آمادگی امتحان ساخته شد");
      setTitle("");
      setExamDate("");
      setPicked([]);
      onClose();
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="آمادگی امتحان جدید" wide>
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label">عنوان امتحان</label>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="مثلاً: امتحان فصل ۱ و ۲ شیمی" />
          </div>
          <div>
            <label className="label">تاریخ امتحان (میلادی — نمایش شمسی می‌شود)</label>
            <input type="date" className="input" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label">کتاب</label>
            <select className="input" value={bookId ?? ""} onChange={(e) => setBookId(e.target.value ? +e.target.value : null)}>
              <option value="">— انتخاب —</option>
              {books?.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">افزودن مبحث</label>
            <select
              className="input"
              value=""
              onChange={(e) => {
                const id = +e.target.value;
                if (!id || picked.some((p) => p.id === id)) return;
                const found = tree && flatten(tree.nodes).find((o) => o.id === id);
                if (found) setPicked([...picked, { id, label: found.label.trim() }]);
              }}
            >
              <option value="">— انتخاب مبحث —</option>
              {tree && flatten(tree.nodes).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {picked.length > 0 && (
          <div className="flex flex-wrap gap-2 rounded-xl border border-surface-line p-3">
            {picked.map((p) => (
              <button key={p.id} className="chip bg-brand-50 text-brand-700" onClick={() => setPicked(picked.filter((x) => x.id !== p.id))}>
                {p.label} ✕
              </button>
            ))}
          </div>
        )}

        <p className="rounded-xl bg-surface-alt p-3 text-xs leading-6 text-ink-soft">
          پیشنهادها فقط از سوال‌هایی ساخته می‌شوند که در بانک همان مباحث تعریف شده‌اند. اولویت: Coverage پایین →
          غلط/نزده‌های مرور → تست‌های دیده‌نشده.
        </p>

        <div className="flex gap-2">
          <button className="btn-primary flex-1" onClick={submit}>
            ساخت ({fa(picked.length)} مبحث)
          </button>
          <button className="btn-ghost" onClick={onClose}>
            انصراف
          </button>
        </div>
      </div>
    </Modal>
  );
}
