import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addExamQuestions,
  getExam,
  getExamAnalytics,
} from "@/api/academic";
import { getBookTree, listBooks } from "@/api/books";
import type { Exam, ExamAnalytics } from "@/types/academic";
import { flattenTree } from "@/utils/tree";

const RESULT_FA: Record<string, string> = {
  correct: "درست",
  wrong: "غلط",
  unanswered: "نزده",
};

export default function ExamDetail() {
  const { id } = useParams<{ id: string }>();
  const [exam, setExam] = useState<Exam | null>(null);
  const [analytics, setAnalytics] = useState<ExamAnalytics | null>(null);
  const [nodes, setNodes] = useState<Array<{ id: number; label: string }>>([]);
  const [error, setError] = useState<string | null>(null);

  const [seq, setSeq] = useState("1");
  const [nodeId, setNodeId] = useState("");
  const [result, setResult] = useState("");

  const load = async (examId: number) => {
    try {
      const [e, a, books] = await Promise.all([
        getExam(examId),
        getExamAnalytics(examId),
        listBooks(),
      ]);
      setExam(e);
      setAnalytics(a);
      if (books.length > 0) {
        const all: Array<{ id: number; label: string }> = [];
        for (const b of books) {
          const tree = await getBookTree(b.id);
          all.push(...flattenTree(tree.nodes).map((n) => ({
            id: n.id,
            label: `${b.title}: ${n.label}`,
          })));
        }
        setNodes(all);
      }
      const maxSeq = e.questions.reduce((m, q) => Math.max(m, q.sequence_no), 0);
      setSeq(String(maxSeq + 1));
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  useEffect(() => {
    if (id) void load(Number(id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const add = async () => {
    if (!id) return;
    try {
      await addExamQuestions(Number(id), [{
        sequence_no: Number(seq),
        topic_node_id: nodeId ? Number(nodeId) : null,
        result: result || null,
      }]);
      setNodeId("");
      setResult("");
      await load(Number(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  };

  if (error) return <p className="text-red-600">{error}</p>;
  if (!exam || !analytics) return <p>در حال بارگذاری…</p>;

  return (
    <div className="space-y-4">
      <Link to="/exams" className="text-sm text-sky-700 underline">→ امتحانات</Link>
      <h1 className="text-xl font-bold">{exam.title}</h1>

      <div className="flex flex-wrap gap-2 text-sm">
        <span className="rounded bg-emerald-100 px-2 py-1">درست: {analytics.correct}</span>
        <span className="rounded bg-red-100 px-2 py-1">غلط: {analytics.wrong}</span>
        <span className="rounded bg-slate-200 px-2 py-1">نزده: {analytics.unanswered}</span>
        <span className="rounded bg-amber-100 px-2 py-1">تصحیح‌نشده: {analytics.ungraded}</span>
      </div>

      {analytics.subjects.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-right text-xs text-slate-500">
              <th className="py-1">درس</th>
              <th>درست</th>
              <th>غلط</th>
              <th>نزده</th>
            </tr>
          </thead>
          <tbody>
            {analytics.subjects.map((s) => (
              <tr key={s.subject_id} className="border-t border-slate-100">
                <td className="py-1">{s.subject_name}</td>
                <td className="text-center text-green-700">{s.correct}</td>
                <td className="text-center text-red-700">{s.wrong}</td>
                <td className="text-center">{s.unanswered}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-bold">سؤال‌ها</h2>
        <ul className="space-y-1 text-sm">
          {exam.questions.map((q) => (
            <li key={q.sequence_no} className="border-t border-slate-100 py-1">
              #{q.sequence_no} — {q.result ? RESULT_FA[q.result] : "تصحیح‌نشده"}
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            type="number"
            value={seq}
            onChange={(e) => setSeq(e.target.value)}
            className="w-16 rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <select value={nodeId} onChange={(e) => setNodeId(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
            <option value="">مبحث…</option>
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>{n.label}</option>
            ))}
          </select>
          <select value={result} onChange={(e) => setResult(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
            <option value="">نتیجه…</option>
            <option value="correct">درست</option>
            <option value="wrong">غلط</option>
            <option value="unanswered">نزده</option>
          </select>
          <button type="button" onClick={() => void add()} className="rounded bg-slate-900 px-3 py-1 text-sm text-white">
            ثبت
          </button>
        </div>
      </section>
    </div>
  );
}
