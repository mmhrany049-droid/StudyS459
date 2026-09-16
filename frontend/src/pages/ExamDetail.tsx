import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Bar, Card, Chip, ChoiceRow, Empty, ErrorBox, Loading, Modal, Stat, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa, pctRaw } from "../lib/api";
import type { Book, ExamDetail, TreeNode } from "../lib/types";

export default function ExamDetailPage() {
  const { examId } = useParams();
  const nav = useNavigate();
  const { data, error, loading, reload } = useFetch<ExamDetail>(`/exams/${examId}`, [examId]);
  const [tab, setTab] = useState<"files" | "key" | "sections" | "attempts">("files");
  const [newAttempt, setNewAttempt] = useState(false);

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const removeExam = async () => {
    await api.del(`/exams/${examId}`);
    toast("امتحان حذف شد");
    nav("/exams");
  };

  const tabs: [typeof tab, string][] = [
    ["files", "📎 فایل‌ها"],
    ["key", "🔑 پاسخ‌نامه رسمی"],
    ["sections", "🧩 بخش‌ها و نگاشت مبحث"],
    ["attempts", "🔁 نوبت‌ها و نتایج"],
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/exams" className="muted hover:text-brand-600">
            ← بازگشت به امتحانات
          </Link>
          <h1 className="mt-1 text-2xl font-black">{data.title}</h1>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Chip tone={data.exam_kind === "mock" ? "brand" : "sky"}>
              {data.exam_kind === "mock" ? "آزمون آزمایشی" : data.exam_kind === "school" ? "مدرسه‌ای" : "دیگر"}
            </Chip>
            <Chip>{data.exam_date_jalali}</Chip>
            <Chip>{fa(data.total_questions)} سوال</Chip>
            {data.provider && <Chip>{data.provider}</Chip>}
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-primary" onClick={() => setNewAttempt(true)} disabled={!data.answer_key.length}>
            ＋ ثبت نوبت جدید
          </button>
          <button className="btn-danger" onClick={removeExam}>
            🗑 حذف
          </button>
        </div>
      </div>

      {!data.answer_key.length && (
        <Card className="border-amber-200 bg-amber-50">
          <p className="text-sm text-amber-800">
            ⚠️ برای ثبت نوبت، اول باید پاسخ‌نامه رسمی امتحان را در تب «پاسخ‌نامه رسمی» وارد کنی.
          </p>
        </Card>
      )}

      {data.attempts.length > 0 && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="تعداد نوبت" value={fa(data.attempts.length)} />
          <Stat label="آخرین درصد" value={pctRaw(data.attempts[data.attempts.length - 1].percentage, 1)} tone="brand" />
          <Stat
            label="تغییر درصد"
            value={data.progress.delta_percentage === null ? "—" : `${data.progress.delta_percentage > 0 ? "+" : ""}${fa(data.progress.delta_percentage)}`}
            tone={(data.progress.delta_percentage || 0) >= 0 ? "good" : "bad"}
          />
          <Stat
            label="تغییر زمان"
            value={data.progress.delta_minutes === null ? "—" : `${fa(data.progress.delta_minutes)} دقیقه`}
            tone={(data.progress.delta_minutes || 0) <= 0 ? "good" : "warn"}
          />
        </div>
      )}

      <div className="flex gap-1.5 overflow-x-auto rounded-2xl border border-surface-line bg-white p-2">
        {tabs.map(([k, l]) => (
          <button
            key={k}
            className={`shrink-0 rounded-xl px-3.5 py-2 text-sm transition ${
              tab === k ? "bg-brand-50 font-semibold text-brand-700" : "text-ink-soft hover:bg-surface-alt"
            }`}
            onClick={() => setTab(k)}
          >
            {l}
          </button>
        ))}
      </div>

      {tab === "files" && <FilesTab data={data} onDone={reload} />}
      {tab === "key" && <KeyTab data={data} onDone={reload} />}
      {tab === "sections" && <SectionsTab data={data} onDone={reload} />}
      {tab === "attempts" && <AttemptsTab data={data} />}

      <AttemptModal open={newAttempt} onClose={() => setNewAttempt(false)} data={data} onDone={reload} />
    </div>
  );
}

/* ------------------------------------------------------------------ files */
function FilesTab({ data, onDone }: { data: ExamDetail; onDone: () => void }) {
  const [kind, setKind] = useState("exam_paper");
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLInputElement>(null);

  const upload = async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("file_kind", kind);
    setBusy(true);
    try {
      await api.upload(`/exams/${data.id}/files`, form);
      toast("فایل آپلود شد");
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
      if (ref.current) ref.current.value = "";
    }
  };

  const remove = async (id: number) => {
    await api.del(`/exam-files/${id}`);
    toast("فایل حذف شد");
    onDone();
  };

  return (
    <Card>
      <h2 className="section-title mb-3">فایل‌های امتحان</h2>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="label">نوع فایل</label>
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="exam_paper">صورت امتحان</option>
            <option value="answer_key_sheet">برگه پاسخ‌نامه رسمی</option>
          </select>
        </div>
        <div className="flex-1">
          <label className="label">انتخاب فایل (PDF تا ۱۵MB، عکس تا ۵MB)</label>
          <input
            ref={ref}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.gif"
            className="input"
            disabled={busy}
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
        </div>
      </div>

      {data.files.length === 0 ? (
        <Empty icon="📎" title="فایلی آپلود نشده" hint="صورت امتحان و پاسخ‌نامه رسمی را جداگانه آپلود کن." />
      ) : (
        <div className="grid gap-2.5 sm:grid-cols-2">
          {data.files.map((f) => (
            <div key={f.id} className="flex items-center gap-3 rounded-xl border border-surface-line p-3">
              <span className="text-2xl">{f.file_type === "pdf" ? "📄" : "🖼️"}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium" title={f.original_name}>
                  {f.original_name}
                </p>
                <p className="text-xs text-ink-mute">
                  {f.file_kind === "answer_key_sheet" ? "پاسخ‌نامه رسمی" : "صورت امتحان"} •{" "}
                  {fa((f.size_bytes / 1024).toFixed(0))} کیلوبایت
                </p>
              </div>
              <a className="btn-ghost btn-xs" href={f.url} target="_blank" rel="noreferrer">
                باز کردن
              </a>
              <button className="btn-danger btn-xs" onClick={() => remove(f.id)}>
                🗑
              </button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ key */
function KeyTab({ data, onDone }: { data: ExamDetail; onDone: () => void }) {
  const total = Math.max(data.total_questions, data.answer_key.length, 10);
  const initial = useMemo(() => {
    const o: Record<number, number | null> = {};
    data.answer_key.forEach((k) => (o[k.sequence_no] = k.answer_key));
    return o;
  }, [data.answer_key]);
  const [keys, setKeys] = useState<Record<number, number | null>>(initial);
  const [focusIdx, setFocusIdx] = useState(0);
  const [compact, setCompact] = useState("");
  const refs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => setKeys(initial), [initial]);

  const seqs = useMemo(() => Array.from({ length: total }, (_, i) => i + 1), [total]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const seq = seqs[focusIdx];
      if (!seq) return;
      if (["1", "2", "3", "4"].includes(e.key)) {
        e.preventDefault();
        setKeys((k) => ({ ...k, [seq]: +e.key }));
        setFocusIdx((i) => Math.min(seqs.length - 1, i + 1));
      } else if (e.key === "Backspace") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [seqs, focusIdx]);

  useEffect(() => {
    refs.current[focusIdx]?.scrollIntoView({ block: "nearest" });
  }, [focusIdx]);

  const save = async () => {
    const items = Object.entries(keys)
      .filter(([, v]) => v !== null && v !== undefined)
      .map(([s, v]) => ({ sequence_no: +s, answer_key: v }));
    try {
      const r = await api.put<{ saved: number }>(`/exams/${data.id}/answer-key`, { items });
      toast(`پاسخ‌نامه ${fa(r.saved)} سوال ذخیره شد`);
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const applyCompact = async () => {
    try {
      const r = await api.put<{ saved: number }>(`/exams/${data.id}/answer-key`, { compact });
      toast(`${fa(r.saved)} پاسخ ثبت شد`);
      setCompact("");
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="section-title">پاسخ‌نامه رسمی امتحان</h2>
        <button className="btn-primary" onClick={save}>
          💾 ذخیره پاسخ‌نامه
        </button>
      </div>
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <div className="min-w-[260px] flex-1">
          <label className="label">ورودی فشرده (اختیاری)</label>
          <input
            className="input font-mono"
            dir="ltr"
            placeholder="1:2, 2:3, 3:1  یا  2 3 1 4 …"
            value={compact}
            onChange={(e) => setCompact(e.target.value)}
          />
        </div>
        <button className="btn-ghost" onClick={applyCompact} disabled={!compact.trim()}>
          اعمال
        </button>
      </div>
      <p className="mb-3 rounded-xl bg-brand-50 p-3 text-xs leading-6 text-brand-700">
        ⌨️ با کلیدهای ۱ تا ۴ سریع پر کن؛ به‌صورت خودکار به سوال بعد می‌رود.
      </p>
      <div className="grid max-h-[55vh] gap-1 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3">
        {seqs.map((seq, i) => (
          <div
            key={seq}
            ref={(el) => {
              refs.current[i] = el;
            }}
            onClick={() => setFocusIdx(i)}
            className={`flex items-center gap-2 rounded-xl px-2.5 py-1.5 ${
              i === focusIdx ? "row-focus" : "hover:bg-surface-alt"
            }`}
          >
            <span className="tabular w-9 shrink-0 text-sm font-bold text-ink-soft">{fa(seq)}</span>
            <div className="flex gap-1">
              {[1, 2, 3, 4].map((n) => (
                <button
                  key={n}
                  className="choice-btn"
                  data-active={keys[seq] === n}
                  onClick={() => setKeys({ ...keys, [seq]: keys[seq] === n ? null : n })}
                >
                  {fa(n)}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ sections */
function SectionsTab({ data, onDone }: { data: ExamDetail; onDone: () => void }) {
  const { data: books } = useFetch<Book[]>("/books");
  const subjects = Array.from(new Map((books || []).map((b) => [b.subject_id, b.subject])).entries());
  const [rows, setRows] = useState(
    data.sections.length
      ? data.sections.map((s) => ({
          subject_id: String(s.subject_id),
          sequence_from: s.sequence_from,
          sequence_to: s.sequence_to,
          duration_minutes: s.duration_minutes ?? "",
        }))
      : [{ subject_id: "", sequence_from: 1, sequence_to: 30, duration_minutes: "" as number | string }]
  );

  const [mapBook, setMapBook] = useState<number | null>(null);
  const { data: tree } = useFetch<{ nodes: TreeNode[] }>(mapBook ? `/books/${mapBook}/nodes?with_stats=false` : null, [
    mapBook,
  ]);
  const [mapRow, setMapRow] = useState({ from: 1, to: 10, node_id: "" });

  const flatten = (nodes: TreeNode[], depth = 0): { id: number; label: string }[] =>
    nodes.flatMap((n) => [
      { id: n.id, label: "\u00a0".repeat(depth * 3) + n.title },
      ...flatten(n.children, depth + 1),
    ]);

  const saveSections = async () => {
    const sections = rows
      .filter((r) => r.subject_id)
      .map((r) => ({
        subject_id: +r.subject_id,
        sequence_from: +r.sequence_from,
        sequence_to: +r.sequence_to,
        duration_minutes: r.duration_minutes === "" ? null : +r.duration_minutes,
      }));
    if (!sections.length) return toast("حداقل یک بلاک درس لازم است", "err");
    try {
      await api.put(`/exams/${data.id}/sections`, { sections });
      toast("بخش‌های آزمون ذخیره شد");
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const addMapping = async () => {
    if (!mapRow.node_id) return toast("مبحث را انتخاب کن", "err");
    try {
      const r = await api.put<{ mapped: number }>(`/exams/${data.id}/topic-map`, {
        items: [{ sequence_from: +mapRow.from, sequence_to: +mapRow.to, node_id: +mapRow.node_id }],
      });
      toast(`${fa(r.mapped)} سوال به مبحث نگاشت شد`);
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="space-y-5">
      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="section-title">بلاک‌های درسی (آزمون چنددرسه)</h2>
            <p className="muted mt-1">مثلاً ۱ تا ۳۰ شیمی، ۳۱ تا ۵۵ حسابان، ۵۶ تا ۸۰ فیزیک.</p>
          </div>
          <div className="flex gap-2">
            <button
              className="btn-ghost"
              onClick={() =>
                setRows([
                  ...rows,
                  {
                    subject_id: "",
                    sequence_from: (rows[rows.length - 1]?.sequence_to || 0) + 1,
                    sequence_to: (rows[rows.length - 1]?.sequence_to || 0) + 25,
                    duration_minutes: "",
                  },
                ])
              }
            >
              ＋ بلاک
            </button>
            <button className="btn-primary" onClick={saveSections}>
              💾 ذخیره بخش‌ها
            </button>
          </div>
        </div>

        <div className="space-y-2.5">
          {rows.map((r, i) => (
            <div key={i} className="grid items-end gap-2 rounded-xl border border-surface-line p-3 sm:grid-cols-5">
              <div className="sm:col-span-2">
                <label className="label">درس</label>
                <select
                  className="input"
                  value={r.subject_id}
                  onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, subject_id: e.target.value } : x)))}
                >
                  <option value="">— انتخاب —</option>
                  {subjects.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">از سوال</label>
                <input
                  type="number"
                  className="input tabular"
                  value={r.sequence_from}
                  onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, sequence_from: +e.target.value } : x)))}
                />
              </div>
              <div>
                <label className="label">تا سوال</label>
                <input
                  type="number"
                  className="input tabular"
                  value={r.sequence_to}
                  onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, sequence_to: +e.target.value } : x)))}
                />
              </div>
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <label className="label">زمان (دقیقه)</label>
                  <input
                    type="number"
                    className="input tabular"
                    value={r.duration_minutes}
                    onChange={(e) =>
                      setRows(rows.map((x, j) => (j === i ? { ...x, duration_minutes: e.target.value } : x)))
                    }
                  />
                </div>
                <button className="btn-danger btn-xs mb-1" onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                  🗑
                </button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="section-title mb-1">نگاشت بازه شماره سوال → مبحث</h2>
        <p className="muted mb-4">با این نگاشت، نتیجه per topic هم محاسبه می‌شود.</p>
        <div className="grid items-end gap-2 sm:grid-cols-5">
          <div>
            <label className="label">از سوال</label>
            <input
              type="number"
              className="input tabular"
              value={mapRow.from}
              onChange={(e) => setMapRow({ ...mapRow, from: +e.target.value })}
            />
          </div>
          <div>
            <label className="label">تا سوال</label>
            <input
              type="number"
              className="input tabular"
              value={mapRow.to}
              onChange={(e) => setMapRow({ ...mapRow, to: +e.target.value })}
            />
          </div>
          <div>
            <label className="label">کتاب</label>
            <select className="input" value={mapBook ?? ""} onChange={(e) => setMapBook(e.target.value ? +e.target.value : null)}>
              <option value="">— انتخاب —</option>
              {books?.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">مبحث</label>
            <select className="input" value={mapRow.node_id} onChange={(e) => setMapRow({ ...mapRow, node_id: e.target.value })}>
              <option value="">— انتخاب —</option>
              {tree && flatten(tree.nodes).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <button className="btn-primary" onClick={addMapping}>
            ＋ افزودن نگاشت
          </button>
        </div>

        {data.topic_map.length > 0 && (
          <div className="mt-4 max-h-64 space-y-1 overflow-y-auto">
            {Object.entries(
              data.topic_map.reduce<Record<string, number[]>>((acc, t) => {
                (acc[t.node_title] ||= []).push(t.sequence_no);
                return acc;
              }, {})
            ).map(([title, seqs]) => (
              <div key={title} className="flex items-center gap-2 rounded-xl bg-surface-alt px-3 py-2 text-sm">
                <Chip tone="brand">
                  {fa(Math.min(...seqs))}–{fa(Math.max(...seqs))}
                </Chip>
                <span className="truncate" title={title}>
                  {title}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ attempts */
function AttemptsTab({ data }: { data: ExamDetail }) {
  if (!data.attempts.length)
    return <Empty icon="🔁" title="هنوز نوبتی ثبت نشده" hint="هر بار که این آزمون را می‌زنی، نوبت جدید با مدت زمان ثبت کن تا پیشرفت را ببینی." />;

  const maxP = Math.max(...data.attempts.map((a) => a.percentage), 1);

  return (
    <div className="space-y-5">
      <Card>
        <h2 className="section-title mb-4">مقایسه نوبت‌ها</h2>
        <div className="space-y-3">
          {data.attempts.map((a) => (
            <div key={a.id} className="rounded-xl border border-surface-line p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{a.label}</span>
                  <Chip>{a.attempted_at_jalali}</Chip>
                  <Chip tone="sky">⏱ {fa(a.duration_minutes)} دقیقه</Chip>
                </div>
                <span className="tabular text-lg font-bold text-brand-600">{pctRaw(a.percentage, 1)}</span>
              </div>
              <div className="mt-2">
                <Bar value={a.percentage / maxP} tone="brand" height="h-2" />
              </div>
              <div className="mt-2 flex gap-2 text-xs">
                <Chip tone="good">{fa(a.correct)} درست</Chip>
                <Chip tone="bad">{fa(a.wrong)} غلط</Chip>
                <Chip tone="warn">{fa(a.unanswered)} نزده</Chip>
              </div>
              {a.notes && <p className="mt-2 text-xs text-ink-soft">📝 {a.notes}</p>}
            </div>
          ))}
        </div>
      </Card>

      {data.breakdown.per_subject.length > 0 && (
        <Card>
          <h2 className="section-title mb-1">نتیجه به تفکیک درس</h2>
          <p className="muted mb-4">بر اساس {data.breakdown.attempt_label}</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {data.breakdown.per_subject.map((s) => (
              <div key={s.subject_id} className="rounded-xl border border-surface-line p-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{s.subject}</span>
                  <span className="tabular font-bold text-brand-600">{pctRaw(s.percentage, 1)}</span>
                </div>
                <p className="mt-1 text-xs text-ink-mute">
                  سوال {fa(s.range[0])}–{fa(s.range[1])}
                  {s.duration_minutes ? ` • ${fa(s.duration_minutes)} دقیقه` : ""}
                </p>
                <div className="mt-2">
                  <Bar value={s.percentage / 100} tone={s.percentage < 50 ? "bad" : "good"} height="h-1.5" />
                </div>
                <div className="mt-2 flex gap-1.5 text-xs">
                  <Chip tone="good">{fa(s.correct)}</Chip>
                  <Chip tone="bad">{fa(s.wrong)}</Chip>
                  <Chip tone="warn">{fa(s.unanswered)}</Chip>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {data.breakdown.per_topic.length > 0 && (
        <Card>
          <h2 className="section-title mb-4">نتیجه به تفکیک مبحث (ضعیف‌ترین اول)</h2>
          <div className="space-y-2">
            {data.breakdown.per_topic.map((t) => (
              <div key={t.node_id} className="flex items-center gap-3 rounded-xl border border-surface-line p-3">
                <span className="min-w-0 flex-1 truncate text-sm" title={t.title}>
                  {t.title}
                </span>
                <div className="w-28">
                  <Bar value={t.percentage / 100} tone={t.percentage < 50 ? "bad" : "good"} height="h-1.5" />
                </div>
                <span className="tabular w-14 text-left text-sm font-bold">{pctRaw(t.percentage, 0)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ attempt modal */
function AttemptModal({
  open,
  onClose,
  data,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  data: ExamDetail;
  onDone: () => void;
}) {
  const seqs = useMemo(() => data.answer_key.map((k) => k.sequence_no).sort((a, b) => a - b), [data.answer_key]);
  const [answers, setAnswers] = useState<Record<number, number | null>>({});
  const [meta, setMeta] = useState({ label: "", duration_minutes: 60, notes: "" });
  const [focusIdx, setFocusIdx] = useState(0);
  const refs = useRef<(HTMLDivElement | null)[]>([]);

  const setA = useCallback(
    (seq: number, v: number | null | undefined, advance = false) => {
      setAnswers((a) => {
        const n = { ...a };
        if (v === undefined) delete n[seq];
        else n[seq] = v;
        return n;
      });
      if (advance) setFocusIdx((i) => Math.min(seqs.length - 1, i + 1));
    },
    [seqs.length]
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      const seq = seqs[focusIdx];
      if (!seq) return;
      if (["1", "2", "3", "4"].includes(e.key)) {
        e.preventDefault();
        setA(seq, +e.key, true);
      } else if (e.key === "0" || e.key === " ") {
        e.preventDefault();
        setA(seq, null, true);
      } else if (e.key === "Backspace") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, seqs, focusIdx, setA]);

  useEffect(() => {
    refs.current[focusIdx]?.scrollIntoView({ block: "nearest" });
  }, [focusIdx]);

  const submit = async () => {
    try {
      const r = await api.post<{ correct: number; wrong: number; unanswered: number; percentage: number }>(
        `/exams/${data.id}/attempts`,
        {
          ...meta,
          duration_minutes: +meta.duration_minutes,
          answers: seqs.map((s) => ({ sequence_no: s, user_answer: answers[s] ?? null })),
        }
      );
      toast(`نتیجه: ${pctRaw(r.percentage, 1)} • ${fa(r.correct)} درست، ${fa(r.wrong)} غلط، ${fa(r.unanswered)} نزده`);
      setAnswers({});
      onClose();
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="ثبت نوبت جدید" wide>
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label className="label">برچسب نوبت</label>
            <input
              className="input"
              placeholder={`نوبت ${fa(data.attempts.length + 1)}`}
              value={meta.label}
              onChange={(e) => setMeta({ ...meta, label: e.target.value })}
            />
          </div>
          <div>
            <label className="label">مدت زمان (دقیقه) *</label>
            <input
              type="number"
              className="input tabular"
              value={meta.duration_minutes}
              onChange={(e) => setMeta({ ...meta, duration_minutes: +e.target.value })}
            />
          </div>
          <div>
            <label className="label">یادداشت</label>
            <input className="input" value={meta.notes} onChange={(e) => setMeta({ ...meta, notes: e.target.value })} />
          </div>
        </div>

        <p className="rounded-xl bg-brand-50 p-3 text-xs leading-6 text-brand-700">
          ⌨️ ۱ تا ۴ = گزینه و رفتن به بعدی • ۰/Space = نزده • Backspace = قبلی
        </p>

        <div className="grid max-h-[45vh] gap-1 overflow-y-auto sm:grid-cols-2">
          {seqs.map((seq, i) => (
            <div
              key={seq}
              ref={(el) => {
                refs.current[i] = el;
              }}
              onClick={() => setFocusIdx(i)}
              className={`flex items-center gap-2 rounded-xl px-2.5 py-1.5 ${
                i === focusIdx ? "row-focus" : "hover:bg-surface-alt"
              }`}
            >
              <span className="tabular w-9 shrink-0 text-sm font-bold text-ink-soft">{fa(seq)}</span>
              <ChoiceRow value={answers[seq]} onChange={(v) => setA(seq, v)} compact />
            </div>
          ))}
        </div>

        <div className="flex gap-2">
          <button className="btn-primary flex-1" onClick={submit}>
            ثبت نوبت ({fa(Object.keys(answers).length)} پاسخ)
          </button>
          <button className="btn-ghost" onClick={onClose}>
            انصراف
          </button>
        </div>
      </div>
    </Modal>
  );
}
