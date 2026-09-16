import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card, Chip, ChoiceRow, ErrorBox, Loading, Modal, Stat, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa, pct } from "../lib/api";
import type { SessionData, SessionResult } from "../lib/types";

export default function TestRunner() {
  const { sessionId } = useParams();
  const { data, error, loading, reload } = useFetch<SessionData>(`/test-sessions/${sessionId}`, [sessionId]);
  const [answers, setAnswers] = useState<Record<number, number | null>>({});
  const [focusIdx, setFocusIdx] = useState(0);
  const [result, setResult] = useState<SessionResult | null>(null);
  const [askDuration, setAskDuration] = useState(false);
  const [duration, setDuration] = useState(20);
  const [elapsed, setElapsed] = useState(0);
  const refs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const rows = data?.questions || [];

  const setA = useCallback(
    (qid: number, v: number | null | undefined, advance = false) => {
      setAnswers((a) => {
        const n = { ...a };
        if (v === undefined) delete n[qid];
        else n[qid] = v;
        return n;
      });
      if (advance) setFocusIdx((i) => Math.min(rows.length - 1, i + 1));
    },
    [rows.length]
  );

  useEffect(() => {
    if (result) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      const row = rows[focusIdx];
      if (!row) return;
      if (["1", "2", "3", "4"].includes(e.key)) {
        e.preventDefault();
        setA(row.question_id, +e.key, true);
      } else if (e.key === "0" || e.key === " ") {
        e.preventDefault();
        setA(row.question_id, null, true);
      } else if (e.key === "Backspace") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, focusIdx, setA, result]);

  useEffect(() => {
    refs.current[focusIdx]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focusIdx]);

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const finish = async (mins: number | null) => {
    try {
      const r = await api.post<SessionResult>(`/test-sessions/${sessionId}/finish`, {
        answers: rows.map((q) => ({ question_id: q.question_id, answer: answers[q.question_id] ?? null })),
        actual_duration_minutes: mins,
      });
      setResult(r);
      setAskDuration(false);
      if (r.points_awarded) toast(`🪙 +${fa(r.points_awarded)} سکه`);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const answered = Object.values(answers).filter((v) => v !== null && v !== undefined).length;
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  if (result) {
    return (
      <div className="space-y-5">
        <div>
          <Link to="/today" className="muted hover:text-brand-600">
            ← بازگشت به برنامه
          </Link>
          <h1 className="mt-1 text-2xl font-black">
            {result.kind === "review" ? "نتیجه جلسه مرور" : "نتیجه تست"}
          </h1>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Stat label="کل" value={fa(result.total)} />
          <Stat label="درست" value={fa(result.correct)} tone="good" />
          <Stat label="غلط" value={fa(result.wrong)} tone="bad" />
          <Stat label="نزده" value={fa(result.unanswered)} tone="warn" />
          <Stat label="دقت" value={pct(result.accuracy)} tone="brand" />
        </div>

        <Card>
          <div className="mb-4 flex flex-wrap gap-2">
            <Chip tone="brand">🪙 +{fa(result.points_awarded)} سکه</Chip>
            {result.duration_minutes && <Chip tone="sky">⏱ {fa(result.duration_minutes)} دقیقه</Chip>}
            {result.parity !== "any" && <Chip>{result.parity === "odd" ? "فرد" : "زوج"}</Chip>}
            {result.range[0] && (
              <Chip>
                بازه {fa(result.range[0])}–{fa(result.range[1])}
              </Chip>
            )}
          </div>
          <h2 className="section-title mb-3">جزئیات پاسخ‌ها</h2>
          <div className="grid max-h-96 gap-1 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3">
            {result.items.map((it) => (
              <div
                key={it.question_id}
                className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm ${
                  it.result === "correct" ? "bg-emerald-50" : it.result === "wrong" ? "bg-rose-50" : "bg-amber-50"
                }`}
              >
                <span className="tabular w-9 font-bold">{fa(it.sequence_no ?? "")}</span>
                <span className="flex-1 text-xs">
                  {it.result === "correct" ? "✅ درست" : it.result === "wrong" ? "❌ غلط" : "⭕ نزده"}
                </span>
                <span className="tabular text-xs text-ink-soft">
                  {it.answer ? `تو: ${fa(it.answer)}` : "—"} • کلید: {fa(it.answer_key ?? "")}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-4 rounded-xl bg-surface-alt p-3 text-xs leading-6 text-ink-soft">
            غلط‌ها و نزده‌ها به صف مرور اضافه شدند: بحرانی (۲ غلط یا بیشتر) تا ۲ روز، بقیه تا ۳ روز.
          </p>
        </Card>

        <div className="flex gap-2">
          <Link to="/today" className="btn-primary">
            بازگشت به برنامه امروز
          </Link>
          <Link to="/progress" className="btn-ghost">
            مشاهده پیشرفت
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to="/today" className="muted hover:text-brand-600">
            ← انصراف و بازگشت
          </Link>
          <h1 className="mt-1 truncate text-xl font-black" title={data.node_title}>
            {data.kind === "review" ? "🔁 جلسه مرور" : data.node_title}
          </h1>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Chip tone="brand">{fa(rows.length)} سوال</Chip>
            {data.parity !== "any" && <Chip tone="sky">{data.parity === "odd" ? "فرد" : "زوج"}</Chip>}
            {data.range[0] && (
              <Chip>
                بازه {fa(data.range[0])}–{fa(data.range[1])}
              </Chip>
            )}
            {data.timed && <Chip tone="warn">زمان‌دار</Chip>}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-center">
            <p className="tabular text-2xl font-black text-brand-600">
              {fa(mm)}:{fa(ss)}
            </p>
            <p className="text-xs text-ink-mute">زمان سپری‌شده</p>
          </div>
          <button className="btn-primary" onClick={() => (data.timed ? finish(Math.round(elapsed / 60)) : setAskDuration(true))}>
            ✔️ پایان تست
          </button>
        </div>
      </div>

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <p className="rounded-xl bg-brand-50 px-3 py-2 text-xs leading-6 text-brand-700">
            ⌨️ ۱ تا ۴ = گزینه و رفتن به بعدی • ۰/Space = نزده • Backspace = قبلی
          </p>
          <span className="tabular text-sm text-ink-soft">
            {fa(answered)} پاسخ‌داده‌شده از {fa(rows.length)}
          </span>
        </div>

        <div className="grid gap-1 sm:grid-cols-2">
          {rows.map((q, i) => (
            <div
              key={q.question_id}
              ref={(el) => {
                refs.current[i] = el;
              }}
              onClick={() => setFocusIdx(i)}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 transition ${
                i === focusIdx ? "row-focus" : "hover:bg-surface-alt"
              }`}
            >
              <span className="tabular w-10 shrink-0 text-sm font-bold text-ink-soft">{fa(q.sequence_no)}</span>
              <ChoiceRow value={answers[q.question_id]} onChange={(v) => setA(q.question_id, v)} />
              {q.difficulty_level && <Chip tone="sky">سطح {fa(q.difficulty_level)}</Chip>}
              {data.kind === "review" && (
                <span className="truncate text-[10px] text-ink-mute" title={q.node_title}>
                  {q.node_title}
                </span>
              )}
            </div>
          ))}
        </div>
      </Card>

      <Modal open={askDuration} onClose={() => setAskDuration(false)} title="این جلسه چند دقیقه طول کشید؟">
        <div className="space-y-4">
          <p className="muted">
            زمان تقریبی برای تحلیل ثبت می‌شود (تست Untimed محدودیت زمانی ندارد). زمان‌سنج صفحه:{" "}
            <b className="tabular">{fa(Math.max(1, Math.round(elapsed / 60)))} دقیقه</b>
          </p>
          <input
            type="number"
            min={1}
            className="input tabular"
            value={duration}
            onChange={(e) => setDuration(+e.target.value)}
          />
          <div className="flex gap-2">
            <button className="btn-ghost flex-1" onClick={() => setDuration(Math.max(1, Math.round(elapsed / 60)))}>
              استفاده از زمان‌سنج
            </button>
            <button className="btn-primary flex-1" onClick={() => finish(duration)}>
              ثبت و پایان
            </button>
          </div>
          <button className="btn-ghost w-full" onClick={() => finish(null)}>
            بدون ثبت زمان
          </button>
        </div>
      </Modal>
    </div>
  );
}
