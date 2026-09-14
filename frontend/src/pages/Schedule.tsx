import { useEffect, useState } from "react";
import {
  createClassSession,
  createSchedule,
  createTaught,
  listClassSessions,
  listSchedules,
  listTaught,
} from "@/api/academic";
import { getBookTree, listBooks } from "@/api/books";
import type {
  ClassSession,
  Schedule,
  TaughtLesson,
} from "@/types/academic";
import type { Book } from "@/types/books";
import { flattenTree } from "@/utils/tree";

const DOW_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"];

function subjectsOf(books: Book[]): Array<{ id: number; name: string }> {
  const map = new Map<number, string>();
  for (const b of books) map.set(b.subject.id, b.subject.name);
  return [...map.entries()].map(([id, name]) => ({ id, name }));
}

export default function SchedulePage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [sessions, setSessions] = useState<ClassSession[]>([]);
  const [taught, setTaught] = useState<TaughtLesson[]>([]);
  const [books, setBooks] = useState<Book[]>([]);
  const [nodes, setNodes] = useState<Array<{ id: number; label: string }>>([]);
  const [error, setError] = useState<string | null>(null);

  // New schedule form
  const [kind, setKind] = useState("school");
  const [title, setTitle] = useState("");
  const [dow, setDow] = useState("5");
  const [start, setStart] = useState("08:00");
  const [end, setEnd] = useState("09:00");
  const [subjectId, setSubjectId] = useState("");

  const load = async () => {
    try {
      const [s, c, t, b] = await Promise.all([
        listSchedules(),
        listClassSessions(),
        listTaught(),
        listBooks(),
      ]);
      setSchedules(s);
      setSessions(c);
      setTaught(t);
      setBooks(b);
      if (b.length > 0) {
        const tree = await getBookTree(b[0].id);
        setNodes(flattenTree(tree.nodes));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addSchedule = async () => {
    if (!title.trim()) return;
    try {
      await createSchedule({
        schedule_type: kind,
        title: title.trim(),
        day_of_week: Number(dow),
        start_time: start,
        end_time: end,
        subject_id: subjectId ? Number(subjectId) : null,
      });
      setTitle("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  const logSession = async (s: Schedule, attended: boolean) => {
    try {
      const today = new Date().toISOString().slice(0, 10);
      await createClassSession({
        schedule_id: s.id,
        date: today,
        subject_id: s.subject_id ?? subjectsOf(books)[0]?.id,
        attended,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  const [taughtNode, setTaughtNode] = useState<Record<number, string>>({});

  const logTaught = async (sessionId: number, subjId: number) => {
    const nodeId = taughtNode[sessionId];
    if (!nodeId) return;
    try {
      await createTaught({
        class_session_id: sessionId,
        subject_id: subjId,
        node_id: Number(nodeId),
        taught_at: new Date().toISOString(),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">برنامه مدرسه</h1>

      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-bold">کلاس‌های هفتگی</h2>
        <ul className="space-y-1 text-sm">
          {schedules.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-2 border-t border-slate-100 py-1">
              <span className="font-medium">{s.title}</span>
              <span className="text-xs text-slate-500">
                {s.schedule_type === "school" ? "🏫 مدرسه" : "🎯 بیرون"} — {DOW_FA[s.day_of_week]}{" "}
                {s.start_time.slice(0, 5)}–{s.end_time.slice(0, 5)}
              </span>
              <span className="flex gap-1 text-xs">
                <button
                  type="button"
                  onClick={() => void logSession(s, true)}
                  className="rounded bg-green-100 px-2 py-0.5 text-green-800"
                >
                  حاضر شدم
                </button>
                <button
                  type="button"
                  onClick={() => void logSession(s, false)}
                  className="rounded bg-red-100 px-2 py-0.5 text-red-800"
                >
                  غایب
                </button>
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <select value={kind} onChange={(e) => setKind(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
            <option value="school">مدرسه</option>
            <option value="external">کلاس بیرون</option>
          </select>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="عنوان…"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <select value={dow} onChange={(e) => setDow(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
            {DOW_FA.map((d, i) => (
              <option key={i} value={i}>{d}</option>
            ))}
          </select>
          <input type="time" value={start} onChange={(e) => setStart(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm" />
          <input type="time" value={end} onChange={(e) => setEnd(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm" />
          <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
            <option value="">بدون درس</option>
            {subjectsOf(books).map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <button type="button" onClick={() => void addSchedule()} className="rounded bg-slate-900 px-3 py-1 text-sm text-white">
            افزودن
          </button>
        </div>
      </section>

      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-bold">جلسات اخیر</h2>
        {sessions.length === 0 ? (
          <p className="text-sm text-slate-500">هنوز جلسه‌ای ثبت نشده.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {sessions.slice(0, 10).map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-2 border-t border-slate-100 py-1">
                <span>{c.date} — {c.subject_name}</span>
                <span>{c.attended ? "✅ حاضر" : "❌ غایب"}</span>
                <select
                  value={taughtNode[c.id] ?? ""}
                  onChange={(e) => setTaughtNode({ ...taughtNode, [c.id]: e.target.value })}
                  className="rounded border border-slate-300 px-1 py-0.5 text-xs"
                >
                  <option value="">تدریس شد…</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>{n.label}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => void logTaught(c.id, c.subject_id)}
                  className="rounded bg-slate-200 px-2 py-0.5 text-xs"
                >
                  ثبت تدریس
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-bold">تدریس‌شده‌ها (فقط رکورد — روی آمار اثر ندارد)</h2>
        {taught.length === 0 ? (
          <p className="text-sm text-slate-500">چیزی ثبت نشده.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {taught.slice(0, 10).map((t) => (
              <li key={t.id} className="border-t border-slate-100 py-1">
                {t.subject_name} — {t.node_title ?? "بدون مبحث"} (
                {new Date(t.taught_at).toLocaleDateString("fa-IR")})
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
