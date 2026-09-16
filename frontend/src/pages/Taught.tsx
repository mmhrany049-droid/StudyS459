import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, Card, Chip, Empty, ErrorBox, Loading, Modal, Stat, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa, pct } from "../lib/api";
import type { Book, TaughtInsights, TreeNode } from "../lib/types";

const STATUS_TONE: Record<string, string> = {
  no_bank: "bad",
  under_practiced: "warn",
  weak: "bad",
  good: "good",
};

export default function Taught() {
  const { data, error, loading, reload } = useFetch<TaughtInsights>("/taught-topics/insights");
  const [add, setAdd] = useState(false);
  const nav = useNavigate();

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const startTest = async (nodeId: number, count: number) => {
    try {
      const ps = await api.get<{ suggested_parity: string }>(`/nodes/${nodeId}/parity-state`);
      const s = await api.post<{ id: number }>("/test-sessions", {
        node_id: nodeId,
        count,
        parity: ps.suggested_parity,
      });
      nav(`/test/${s.id}`);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const remove = async (id: number) => {
    await api.del(`/taught-topics/${id}`);
    toast("حذف شد");
    reload();
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">تدریس‌شده</h1>
          <p className="muted mt-1">
            چه مباحثی سر کلاس تدریس شده و نتیجه‌ات چیست. تدریس‌شده هرگز به معنی یادگرفته‌شده نیست.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setAdd(true)}>
          ＋ ثبت مبحث تدریس‌شده
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="کل مباحث" value={fa(data.counts.total || 0)} />
        <Stat label="تدریس ۴۸ ساعت اخیر" value={fa(data.counts.recent_48h || 0)} tone="brand" />
        <Stat label="کم‌تمرین" value={fa(data.counts.under_practiced || 0)} tone="warn" />
        <Stat label="با ضعف" value={fa(data.counts.weak || 0)} tone="bad" />
        <Stat label="بدون بانک تست" value={fa(data.counts.no_bank || 0)} tone="bad" />
      </div>

      {data.warnings.length > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <h2 className="mb-2 font-bold text-amber-900">⚠️ نیاز به تعریف بانک تست</h2>
          <ul className="space-y-1.5 text-sm leading-6 text-amber-800">
            {data.warnings.map((w, i) => (
              <li key={i}>• {w}</li>
            ))}
          </ul>
        </Card>
      )}

      {data.suggestions.length > 0 && (
        <Card>
          <h2 className="section-title mb-3">💡 پیشنهاد تست از مباحث تدریس‌شده</h2>
          <div className="space-y-2.5">
            {data.suggestions.map((s) => (
              <div
                key={s.node_id}
                className="flex flex-wrap items-center gap-3 rounded-xl border border-surface-line p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium" title={s.title}>
                    {s.title}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-soft">{s.reason}</p>
                </div>
                <button className="btn-soft btn-xs" onClick={() => startTest(s.node_id, s.suggested_count)}>
                  شروع {fa(s.suggested_count)} تست
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {data.items.length === 0 ? (
        <Empty
          icon="🎓"
          title="هنوز مبحث تدریس‌شده‌ای ثبت نکرده‌ای"
          hint="بعد از هر جلسه مدرسه یا کلاس تقویتی، مبحث تدریس‌شده را ثبت کن تا سیستم بداند کجا باید تمرین بدهد."
          action={
            <button className="btn-primary" onClick={() => setAdd(true)}>
              ＋ ثبت مبحث تدریس‌شده
            </button>
          }
        />
      ) : (
        <Card>
          <h2 className="section-title mb-3">داشبورد مباحث تدریس‌شده</h2>
          <div className="space-y-2.5">
            {data.items.map((it) => (
              <div key={it.id} className="rounded-xl border border-surface-line p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{it.title}</span>
                      <Chip tone={STATUS_TONE[it.status]}>{it.status_label}</Chip>
                      {it.fresh && <Chip tone="brand">تازه‌تدریس‌شده</Chip>}
                      <Chip>
                        {it.source_type === "school"
                          ? "مدرسه"
                          : it.source_type === "external_class"
                          ? "کلاس تقویتی"
                          : "دیگر"}
                      </Chip>
                    </div>
                    <p className="mt-1 truncate text-xs text-ink-mute" title={it.full_title}>
                      {it.book_title} • {it.full_title}
                    </p>
                    {it.notes && <p className="mt-1 text-xs text-ink-soft">📝 {it.notes}</p>}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-ink-mute">
                      {it.taught_at_jalali} ({fa(it.days_since)} روز پیش)
                    </span>
                    <button className="btn-danger btn-xs" onClick={() => remove(it.id)}>
                      🗑
                    </button>
                  </div>
                </div>

                {it.has_bank ? (
                  <div className="mt-3 grid gap-3 sm:grid-cols-4">
                    <div>
                      <div className="mb-1 flex justify-between text-xs text-ink-soft">
                        <span>Coverage</span>
                        <span className="tabular">{pct(it.coverage)}</span>
                      </div>
                      <Bar value={it.coverage} tone={it.coverage < 0.3 ? "bad" : "good"} height="h-1.5" />
                    </div>
                    <div>
                      <div className="mb-1 flex justify-between text-xs text-ink-soft">
                        <span>Accuracy</span>
                        <span className="tabular">{pct(it.accuracy)}</span>
                      </div>
                      <Bar value={it.accuracy} tone={it.accuracy < 0.6 ? "warn" : "good"} height="h-1.5" />
                    </div>
                    <div className="text-xs text-ink-soft">
                      <p>کل بانک: {fa(it.total_questions)} سوال</p>
                      <p>نزده: {fa(it.untouched)}</p>
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      {it.open_review > 0 && <Chip tone="bad">{fa(it.open_review)} در مرور</Chip>}
                      {it.untouched > 0 && (
                        <button
                          className="btn-soft btn-xs"
                          onClick={() => startTest(it.node_id, Math.min(10, it.untouched))}
                        >
                          تست بزن
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 rounded-xl bg-amber-50 p-2.5 text-xs text-amber-800">
                    ⚠️ برای این مبحث هنوز سوال/پاسخ‌نامه تعریف نشده؛ پیشنهاد تست ممکن نیست.
                  </p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      <AddModal open={add} onClose={() => setAdd(false)} onDone={reload} />
    </div>
  );
}

function AddModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { data: books } = useFetch<Book[]>("/books");
  const [bookId, setBookId] = useState<number | null>(null);
  const { data: tree } = useFetch<{ nodes: TreeNode[] }>(bookId ? `/books/${bookId}/nodes?with_stats=false` : null, [
    bookId,
  ]);
  const [nodeId, setNodeId] = useState<number | null>(null);
  const [source, setSource] = useState("school");
  const [notes, setNotes] = useState("");

  const flatten = (nodes: TreeNode[], depth = 0): { id: number; label: string; leaf: boolean }[] =>
    nodes.flatMap((n) => [
      { id: n.id, label: "\u00a0".repeat(depth * 3) + n.title, leaf: n.children.length === 0 },
      ...flatten(n.children, depth + 1),
    ]);

  const submit = async () => {
    if (!nodeId) return toast("مبحث را انتخاب کن", "err");
    try {
      await api.post("/taught-topics", { node_id: nodeId, source_type: source, notes });
      toast("مبحث تدریس‌شده ثبت شد");
      setNotes("");
      setNodeId(null);
      onClose();
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="ثبت مبحث تدریس‌شده">
      <div className="space-y-4">
        <div>
          <label className="label">کتاب</label>
          <select
            className="input"
            value={bookId ?? ""}
            onChange={(e) => {
              setBookId(e.target.value ? +e.target.value : null);
              setNodeId(null);
            }}
          >
            <option value="">— انتخاب —</option>
            {books?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.title}
              </option>
            ))}
          </select>
        </div>
        {tree && (
          <div>
            <label className="label">مبحث</label>
            <select className="input" value={nodeId ?? ""} onChange={(e) => setNodeId(+e.target.value)}>
              <option value="">— انتخاب —</option>
              {flatten(tree.nodes).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label className="label">منبع تدریس</label>
          <select className="input" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="school">مدرسه</option>
            <option value="external_class">کلاس تقویتی</option>
            <option value="other">دیگر</option>
          </select>
        </div>
        <div>
          <label className="label">یادداشت (اختیاری)</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="مثلاً: نصف بخش تدریس شد" />
        </div>
        <div className="flex gap-2">
          <button className="btn-primary flex-1" onClick={submit}>
            ثبت
          </button>
          <button className="btn-ghost" onClick={onClose}>
            انصراف
          </button>
        </div>
      </div>
    </Modal>
  );
}
