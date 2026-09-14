import { useEffect, useState } from "react";
import { createHomework, listHomework, patchHomework } from "@/api/academic";
import { getBookTree, listBooks } from "@/api/books";
import type { Homework as HW } from "@/types/academic";
import type { Book } from "@/types/books";
import { flattenTree } from "@/utils/tree";

function subjectsOf(books: Book[]): Array<{ id: number; name: string }> {
  const map = new Map<number, string>();
  for (const b of books) map.set(b.subject.id, b.subject.name);
  return [...map.entries()].map(([id, name]) => ({ id, name }));
}

export default function HomeworkPage() {
  const [items, setItems] = useState<HW[]>([]);
  const [showDone, setShowDone] = useState(false);
  const [books, setBooks] = useState<Book[]>([]);
  const [bookId, setBookId] = useState("");
  const [nodes, setNodes] = useState<Array<{ id: number; label: string }>>([]);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [nodeId, setNodeId] = useState("");
  const [due, setDue] = useState("");
  const [minutes, setMinutes] = useState("30");
  const [withTask, setWithTask] = useState(true);

  const load = async (done: boolean) => {
    try {
      const [hw, b] = await Promise.all([
        listHomework(done ? undefined : "pending"),
        listBooks(),
      ]);
      setItems(hw);
      setBooks(b);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  useEffect(() => {
    void load(showDone);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pickBook = async (id: string) => {
    setBookId(id);
    setNodeId("");
    if (!id) {
      setNodes([]);
      return;
    }
    const tree = await getBookTree(Number(id));
    setNodes(flattenTree(tree.nodes));
  };

  const add = async () => {
    if (!title.trim() || !subjectId || !due) return;
    try {
      await createHomework({
        title: title.trim(),
        subject_id: Number(subjectId),
        node_id: nodeId ? Number(nodeId) : null,
        due_at: new Date(due).toISOString(),
        estimated_minutes: Number(minutes) || 0,
        create_task: withTask,
      });
      setTitle("");
      await load(showDone);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  const mark = async (id: number, status: string) => {
    try {
      await patchHomework(id, { status });
      await load(showDone);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">تکالیف</h1>
        <label className="flex items-center gap-1 text-sm">
          <input
            type="checkbox"
            checked={showDone}
            onChange={(e) => {
              setShowDone(e.target.checked);
              void load(e.target.checked);
            }}
          />
          نمایش انجام‌شده‌ها
        </label>
      </div>

      <ul className="space-y-2">
        {items.map((h) => (
          <li key={h.id} className="flex flex-wrap items-center gap-2 rounded-lg bg-white p-3 text-sm shadow-sm">
            <span className="font-medium">{h.title}</span>
            <span className="text-xs text-slate-500">
              {h.subject_name}
              {h.node_title ? ` — ${h.node_title}` : ""} — مهلت:{" "}
              {new Date(h.due_at).toLocaleDateString("fa-IR")} ({h.estimated_minutes}′)
            </span>
            {h.status === "pending" ? (
              <span className="flex gap-1">
                <button
                  type="button"
                  onClick={() => void mark(h.id, "done")}
                  className="rounded bg-green-100 px-2 py-0.5 text-green-800"
                >
                  انجام شد
                </button>
                <button
                  type="button"
                  onClick={() => void mark(h.id, "cancelled")}
                  className="rounded bg-slate-200 px-2 py-0.5"
                >
                  لغو
                </button>
              </span>
            ) : (
              <span>{h.status === "done" ? "✅" : "🚫"}</span>
            )}
          </li>
        ))}
      </ul>

      <section className="space-y-2 rounded-lg bg-white p-4 shadow-sm">
        <h2 className="font-bold">تکلیف جدید</h2>
        <div className="flex flex-wrap gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="عنوان…"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
            <option value="">درس…</option>
            {subjectsOf(books).map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <select value={bookId} onChange={(e) => void pickBook(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
            <option value="">کتاب (اختیاری)…</option>
            {books.map((b) => (
              <option key={b.id} value={b.id}>{b.title}</option>
            ))}
          </select>
          {nodes.length > 0 && (
            <select value={nodeId} onChange={(e) => setNodeId(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
              <option value="">مبحث…</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>{n.label}</option>
              ))}
            </select>
          )}
          <input
            type="datetime-local"
            value={due}
            onChange={(e) => setDue(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <input
            type="number"
            value={minutes}
            onChange={(e) => setMinutes(e.target.value)}
            className="w-16 rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <label className="flex items-center gap-1 text-sm">
            <input type="checkbox" checked={withTask} onChange={(e) => setWithTask(e.target.checked)} />
            ساخت تسک
          </label>
          <button type="button" onClick={() => void add()} className="rounded bg-slate-900 px-3 py-1 text-sm text-white">
            افزودن
          </button>
        </div>
      </section>
    </div>
  );
}
