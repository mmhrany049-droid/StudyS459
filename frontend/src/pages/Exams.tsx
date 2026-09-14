import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createExam, listExams } from "@/api/academic";
import type { Exam } from "@/types/academic";

export default function Exams() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [examDate, setExamDate] = useState("");

  const load = async () => {
    try {
      setExams(await listExams());
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const add = async () => {
    if (!title.trim() || !examDate) return;
    try {
      await createExam({ title: title.trim(), exam_date: examDate });
      setTitle("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">امتحانات</h1>
      <ul className="space-y-2">
        {exams.map((e) => (
          <li key={e.id} className="rounded-lg bg-white p-3 text-sm shadow-sm">
            <Link to={`/exams/${e.id}`} className="font-medium hover:underline">
              {e.title}
            </Link>
            <span className="text-xs text-slate-500">
              {" "}— {e.exam_date} — {e.questions.length} سؤال
            </span>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="عنوان امتحان…"
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <input
          type="date"
          value={examDate}
          onChange={(e) => setExamDate(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <button type="button" onClick={() => void add()} className="rounded bg-slate-900 px-3 py-1 text-sm text-white">
          افزودن
        </button>
      </div>
    </div>
  );
}
