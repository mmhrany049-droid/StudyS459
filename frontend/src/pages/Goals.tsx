import { useCallback, useEffect, useState } from "react";
import { getBookTree, listBooks } from "@/api/books";
import {
  createWeekGoal,
  fetchCandidates,
  fetchWeekGoal,
  patchGoal,
} from "@/api/goals";
import type { Book, TreeNode } from "@/types/books";
import type { CandidateTask, GoalItemIn, GoalType, WeekGoal } from "@/types/goals";

const PARITY_FA: Record<string, string> = { odd: "فرد", even: "زوج", any: "آزاد" };

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function flatten(nodes: TreeNode[], prefix = ""): Array<{ id: number; label: string }> {
  const out: Array<{ id: number; label: string }> = [];
  for (const n of nodes) {
    const label = prefix ? `${prefix} / ${n.title}` : n.title;
    out.push({ id: n.id, label });
    out.push(...flatten(n.children, label));
  }
  return out;
}

interface DraftItem {
  goal_type: GoalType;
  target_value: string;
  book_id: string;
  node_id: string;
}

const EMPTY_DRAFT: DraftItem = { goal_type: "count", target_value: "", book_id: "", node_id: "" };

export default function Goals() {
  const [week, setWeek] = useState(todayISO());
  const [goal, setGoal] = useState<WeekGoal | null>(null);
  const [missing, setMissing] = useState(false);
  const [candidates, setCandidates] = useState<CandidateTask[]>([]);
  const [books, setBooks] = useState<Book[]>([]);
  const [nodesByBook, setNodesByBook] = useState<Record<number, Array<{ id: number; label: string }>>>({});
  const [drafts, setDrafts] = useState<DraftItem[]>([{ ...EMPTY_DRAFT }]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (w: string) => {
    setError(null);
    setMissing(false);
    try {
      const g = await fetchWeekGoal(w);
      setGoal(g);
      const c = await fetchCandidates(g.id);
      setCandidates(c.items);
    } catch (err) {
      if (err instanceof Error && err.message.includes("404")) {
        setGoal(null);
        setCandidates([]);
        setMissing(true);
      } else {
        setError(err instanceof Error ? err.message : "خطای نامشخص");
      }
    }
  }, []);

  useEffect(() => {
    void load(week);
    listBooks().then(setBooks).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ensureNodes = async (bookId: number) => {
    if (nodesByBook[bookId]) return;
    const tree = await getBookTree(bookId);
    setNodesByBook((prev) => ({ ...prev, [bookId]: flatten(tree.nodes) }));
  };

  const submit = async () => {
    setError(null);
    try {
      const items: GoalItemIn[] = drafts.map((d) => ({
        goal_type: d.goal_type,
        target_value: Number(d.target_value),
        book_id: d.book_id ? Number(d.book_id) : null,
        node_id: d.node_id ? Number(d.node_id) : null,
      }));
      const g = missing
        ? await createWeekGoal(week, items)
        : await patchGoal(goal!.id, { items });
      setGoal(g);
      setMissing(false);
      const c = await fetchCandidates(g.id);
      setCandidates(c.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  const startEdit = () => {
    if (!goal) return;
    setDrafts(
      goal.items.map((i) => ({
        goal_type: i.goal_type,
        target_value: String(i.target_value),
        book_id: i.book_id ? String(i.book_id) : "",
        node_id: i.node_id ? String(i.node_id) : "",
      })),
    );
    goal.items.forEach((i) => {
      if (i.book_id) void ensureNodes(i.book_id);
    });
    setMissing(true); // reuse the form for editing
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">اهداف هفته</h1>
        <input
          type="date"
          value={week}
          onChange={(e) => {
            setWeek(e.target.value);
            void load(e.target.value);
          }}
          className="rounded border border-slate-300 px-2 py-1"
        />
      </div>
      {error && <p className="text-red-600">{error}</p>}

      {goal && !missing && (
        <>
          <section className="rounded-lg bg-white p-4 shadow-sm">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="font-bold">
                هفته {goal.week_start} تا {goal.week_end}
                {!goal.active && " (غیرفعال)"}
              </h2>
              <button
                type="button"
                onClick={startEdit}
                className="rounded bg-slate-200 px-3 py-1 text-sm"
              >
                ویرایش
              </button>
            </div>
            <p className="mb-3 text-sm text-slate-600">
              حجم یکتای هفته: {goal.week_volume_unique} (بدون شمارش تکراری) — آزمون‌ها:{" "}
              {goal.sessions_in_week}
            </p>
            <ul className="space-y-3">
              {goal.items.map((i) => (
                <li key={i.id} className="rounded border border-slate-200 p-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">
                      {i.goal_type === "count" ? "تعداد" : "موضوع"}: {i.title}
                    </span>
                    <span>{i.progress.done ? "✅" : `${i.progress.remaining} باقی‌مانده`}</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded bg-slate-200">
                    <div
                      className={i.progress.done ? "h-full bg-emerald-500" : "h-full bg-sky-500"}
                      style={{
                        width: `${
                          i.goal_type === "count"
                            ? Math.min(100, (i.progress.volume / Math.max(1, i.target_value)) * 100)
                            : Math.min(100, ((i.progress.coverage ?? 0) / Math.max(0.01, i.target_value)) * 100)
                        }%`,
                      }}
                    />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {i.goal_type === "count"
                      ? `حجم ${i.progress.volume} از ${i.target_value}`
                      : `پوشش ${i.progress.coverage === null ? "—" : Math.round(i.progress.coverage * 100) + "٪"} از ${Math.round(i.target_value * 100)}٪`}
                  </p>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-lg bg-white p-4 shadow-sm">
            <h2 className="mb-3 font-bold">کارهای پیشنهادی</h2>
            {candidates.length === 0 ? (
              <p className="text-sm text-slate-500">پیشنهادی وجود ندارد.</p>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm">
                {candidates.map((c) => (
                  <li key={c.node_id} className="py-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">
                        {c.kind === "test" ? "📝" : "🔁"} {c.title}
                      </span>
                      <span className="text-xs text-slate-500 tabular-nums">
                        {c.suggested_count} سؤال — {PARITY_FA[c.suggested_parity]}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500">{c.path}</p>
                    <p className="text-xs text-slate-700">{c.recommendation_reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      {missing && (
        <section className="space-y-3 rounded-lg bg-white p-4 shadow-sm">
          <h2 className="font-bold">{goal ? "ویرایش اهداف" : "ثبت هدف هفته"}</h2>
          {drafts.map((d, idx) => (
            <div key={idx} className="flex flex-wrap items-center gap-2 rounded border border-slate-200 p-2">
              <select
                value={d.goal_type}
                onChange={(e) => {
                  const next = [...drafts];
                  next[idx] = { ...d, goal_type: e.target.value as GoalType };
                  setDrafts(next);
                }}
                className="rounded border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="count">تعداد تست</option>
                <option value="topic">موضوع</option>
              </select>
              <input
                type="number"
                step="any"
                min="0"
                placeholder={d.goal_type === "count" ? "مثلاً 50" : "پوشش 0 تا 1"}
                value={d.target_value}
                onChange={(e) => {
                  const next = [...drafts];
                  next[idx] = { ...d, target_value: e.target.value };
                  setDrafts(next);
                }}
                className="w-28 rounded border border-slate-300 px-2 py-1 text-sm"
              />
              <select
                value={d.book_id}
                onChange={(e) => {
                  const next = [...drafts];
                  next[idx] = { ...d, book_id: e.target.value, node_id: "" };
                  setDrafts(next);
                  if (e.target.value) void ensureNodes(Number(e.target.value));
                }}
                className="rounded border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">همه کتاب‌ها</option>
                {books.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.title}
                  </option>
                ))}
              </select>
              {d.book_id && (
                <select
                  value={d.node_id}
                  onChange={(e) => {
                    const next = [...drafts];
                    next[idx] = { ...d, node_id: e.target.value };
                    setDrafts(next);
                  }}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="">{d.goal_type === "topic" ? "انتخاب مبحث (الزامی)" : "کل کتاب"}</option>
                  {(nodesByBook[Number(d.book_id)] ?? []).map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label}
                    </option>
                  ))}
                </select>
              )}
              <button
                type="button"
                onClick={() => setDrafts(drafts.filter((_, i) => i !== idx))}
                className="text-sm text-red-600"
              >
                حذف
              </button>
            </div>
          ))}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setDrafts([...drafts, { ...EMPTY_DRAFT }])}
              className="rounded bg-slate-200 px-3 py-1 text-sm"
            >
              + افزودن آیتم
            </button>
            <button
              type="button"
              onClick={() => void submit()}
              className="rounded bg-slate-900 px-4 py-1 text-sm text-white"
            >
              ذخیره
            </button>
            {goal && (
              <button
                type="button"
                onClick={() => {
                  setMissing(false);
                  setDrafts([{ ...EMPTY_DRAFT }]);
                }}
                className="rounded bg-slate-100 px-3 py-1 text-sm"
              >
                انصراف
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
