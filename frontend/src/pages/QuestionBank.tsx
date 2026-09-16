import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, Card, Chip, ChoiceRow, Empty, ErrorBox, Loading, Modal, Stat, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa, pct } from "../lib/api";
import type { BankData } from "../lib/types";

/**
 * بانک تست هر مبحث — سند 02_QUESTION_BANK_UI
 *  • افزودن بازه سریع از N تا M
 *  • پاسخ‌نامه چهارگزینه‌ای به شکل لیست بزرگ  (S1 صفحه‌کلید سریع)
 *  • ورودی فشرده «1:2, 2:3»
 *  • فیلتر بدون جواب / بدون attempt (S4)
 *  • خلاصه مبحث بالای لیست (S3)  •  Auto-save (S2)
 */
export default function QuestionBank() {
  const { bookId, nodeId } = useParams();
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [onlyUnattempted, setOnlyUnattempted] = useState(false);
  const path = `/nodes/${nodeId}/questions?only_missing_key=${onlyMissing}&only_unattempted=${onlyUnattempted}`;
  const { data, error, loading, reload } = useFetch<BankData>(path, [onlyMissing, onlyUnattempted]);

  const [draft, setDraft] = useState<Record<number, number | null>>({});
  const [focusIdx, setFocusIdx] = useState(0);
  const [showRange, setShowRange] = useState(false);
  const [showCompact, setShowCompact] = useState(false);
  const [saving, setSaving] = useState(false);
  const rowRefs = useRef<(HTMLDivElement | null)[]>([]);
  const scope = `bank:${nodeId}`;

  // بازیابی پیش‌نویس (S2)
  useEffect(() => {
    api
      .get<{ payload: Record<string, number | null> }>(`/drafts/${scope}`)
      .then((r) => {
        const p = r.payload || {};
        if (Object.keys(p).length) {
          setDraft(Object.fromEntries(Object.entries(p).map(([k, v]) => [+k, v])));
          toast("پیش‌نویس ذخیره‌شده بازیابی شد", "info");
        }
      })
      .catch(() => undefined);
  }, [scope]);

  const dirty = Object.keys(draft).length;

  // auto-save هر ۱۰ پاسخ یا هر ۳۰ ثانیه (S2)
  const persistDraft = useCallback(() => {
    if (!Object.keys(draft).length) return;
    api.put("/drafts", { scope, payload: draft }).catch(() => undefined);
  }, [draft, scope]);

  useEffect(() => {
    if (dirty && dirty % 10 === 0) persistDraft();
  }, [dirty, persistDraft]);

  useEffect(() => {
    const t = setInterval(persistDraft, 30000);
    return () => clearInterval(t);
  }, [persistDraft]);

  const rows = data?.questions || [];

  const setAnswer = useCallback(
    (seq: number, v: number | null, advance = false) => {
      setDraft((d) => {
        const next = { ...d };
        if (v === undefined) delete next[seq];
        else next[seq] = v;
        return next;
      });
      if (advance) setFocusIdx((i) => Math.min(rows.length - 1, i + 1));
    },
    [rows.length]
  );

  // S1 — پاسخ‌نامه سریع صفحه‌کلید
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      const row = rows[focusIdx];
      if (!row) return;
      if (["1", "2", "3", "4"].includes(e.key)) {
        e.preventDefault();
        setAnswer(row.sequence_no, +e.key, true);
      } else if (e.key === "0" || e.key === " ") {
        e.preventDefault();
        setAnswer(row.sequence_no, null, true);
      } else if (e.key === "Backspace") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusIdx((i) => Math.min(rows.length - 1, i + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, focusIdx, setAnswer]);

  useEffect(() => {
    rowRefs.current[focusIdx]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focusIdx]);

  const save = async () => {
    const items = Object.entries(draft).map(([seq, key]) => ({
      sequence_no: +seq,
      answer_key: key,
    }));
    if (!items.length) return toast("تغییری برای ذخیره نیست", "info");
    setSaving(true);
    try {
      const r = await api.put<{ updated: number }>(`/nodes/${nodeId}/questions/bulk`, { items });
      toast(`پاسخ‌نامه ${fa(r.updated)} سوال ذخیره شد`);
      setDraft({});
      await api.del(`/drafts/${scope}`).catch(() => undefined);
      reload();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setSaving(false);
    }
  };

  const removeQuestion = async (id: number) => {
    try {
      const r = await api.del<{ soft_deleted: boolean; message: string }>(`/questions/${id}`);
      toast(r.message, r.soft_deleted ? "info" : "ok");
      reload();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const filled = useMemo(
    () => rows.filter((r) => draft[r.sequence_no] !== undefined || r.answer_key !== null).length,
    [rows, draft]
  );

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;
  const s = data.summary;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to="/books" className="muted hover:text-brand-600">
            ← بازگشت به کتاب‌ها
          </Link>
          <h1 className="mt-1 text-xl font-black leading-7">{data.node_title}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={() => setShowCompact(true)}>
            ⌨️ ورودی فشرده
          </button>
          <button className="btn-primary" onClick={() => setShowRange(true)}>
            ＋ افزودن بازه سوال
          </button>
        </div>
      </div>

      {/* S3 — خلاصه مبحث */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="کل سوال بانک" value={fa(s.total)} />
        <Stat label="دارای پاسخ‌نامه" value={fa(s.with_answer_key)} tone="good" />
        <Stat label="بدون جواب" value={fa(s.missing_answer_key)} tone={s.missing_answer_key ? "warn" : "default"} />
        <Stat label="قبلاً زده‌شده" value={fa(s.attempted)} tone="brand" sub={`Coverage ${pct(s.coverage)}`} />
        <Stat label="غلط/نزده باز" value={fa(s.open_review)} tone={s.open_review ? "bad" : "default"} />
      </div>

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            <button
              className={onlyMissing ? "btn-soft btn-xs" : "btn-ghost btn-xs"}
              onClick={() => setOnlyMissing(!onlyMissing)}
            >
              فقط بدون جواب
            </button>
            <button
              className={onlyUnattempted ? "btn-soft btn-xs" : "btn-ghost btn-xs"}
              onClick={() => setOnlyUnattempted(!onlyUnattempted)}
            >
              فقط بدون attempt
            </button>
          </div>
          <div className="flex items-center gap-3">
            <span className="tabular text-xs text-ink-mute">
              {fa(filled)} از {fa(rows.length)} ردیف پاسخ دارد
            </span>
            <button className="btn-primary" onClick={save} disabled={saving || !dirty}>
              {saving ? "در حال ذخیره…" : `💾 ذخیره پاسخ‌نامه${dirty ? ` (${fa(dirty)})` : ""}`}
            </button>
          </div>
        </div>

        <p className="mb-4 rounded-xl bg-brand-50 p-3 text-xs leading-6 text-brand-700">
          ⌨️ <b>ورود سریع:</b> کلیدهای <b>۱ ۲ ۳ ۴</b> پاسخ ردیف فعال را ثبت می‌کنند و به سوال بعد می‌روند •{" "}
          <b>۰</b> یا <b>Space</b> = نزده • <b>Backspace</b> = سوال قبل • پیش‌نویس هر ۱۰ پاسخ و هر ۳۰ ثانیه خودکار
          ذخیره می‌شود.
        </p>

        {rows.length === 0 ? (
          <Empty
            icon="🗂️"
            title="هنوز سوالی در این مبحث تعریف نشده"
            hint="با «افزودن بازه سوال» مثلاً از ۱ تا ۴۰ سوال بساز، بعد پاسخ‌نامه چهارگزینه‌ای را وارد کن. جواب می‌تواند بعداً تکمیل شود."
            action={
              <button className="btn-primary" onClick={() => setShowRange(true)}>
                ＋ افزودن بازه سوال
              </button>
            }
          />
        ) : (
          <div className="max-h-[62vh] space-y-1 overflow-y-auto pl-1">
            {rows.map((q, i) => {
              const val = draft[q.sequence_no] !== undefined ? draft[q.sequence_no] : q.answer_key;
              const changed = draft[q.sequence_no] !== undefined;
              return (
                <div
                  key={q.id}
                  ref={(el) => {
                    rowRefs.current[i] = el;
                  }}
                  onClick={() => setFocusIdx(i)}
                  className={`flex items-center gap-3 rounded-xl border border-transparent px-3 py-2 transition ${
                    i === focusIdx ? "row-focus" : "hover:bg-surface-alt"
                  }`}
                >
                  <span className="tabular w-12 shrink-0 text-sm font-bold text-ink-soft">
                    {fa(q.sequence_no)}
                  </span>
                  <ChoiceRow
                    value={val === null && !changed && q.answer_key === null ? undefined : val}
                    onChange={(v) => {
                      setAnswer(q.sequence_no, v as number | null);
                      setFocusIdx(i);
                    }}
                  />
                  {changed && <Chip tone="warn">تغییر ذخیره‌نشده</Chip>}
                  {q.difficulty_level && <Chip tone="sky">سطح {fa(q.difficulty_level)}</Chip>}
                  {q.question_tag && <Chip>{q.question_tag}</Chip>}
                  {q.archived && <Chip tone="bad">آرشیو</Chip>}
                  <span className="flex-1" />
                  {q.attempt_count > 0 && (
                    <span className="hidden text-xs text-ink-mute sm:inline">
                      {fa(q.attempt_count)} بار زده‌شده
                      {q.wrong_count ? ` • ${fa(q.wrong_count)} غلط` : ""}
                      {q.unanswered_count ? ` • ${fa(q.unanswered_count)} نزده` : ""}
                    </span>
                  )}
                  <button
                    className="btn-danger btn-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeQuestion(q.id);
                    }}
                    title="حذف / آرشیو نرم"
                  >
                    🗑
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {s.total > 0 && (
          <div className="mt-4">
            <div className="mb-1 flex justify-between text-xs text-ink-soft">
              <span>تکمیل پاسخ‌نامه</span>
              <span className="tabular">{pct(s.with_answer_key / s.total)}</span>
            </div>
            <Bar value={s.with_answer_key / s.total} tone="good" height="h-1.5" />
          </div>
        )}
      </Card>

      <RangeModal
        open={showRange}
        onClose={() => setShowRange(false)}
        nodeId={Number(nodeId)}
        bookId={Number(bookId)}
        onDone={reload}
      />
      <CompactModal open={showCompact} onClose={() => setShowCompact(false)} nodeId={Number(nodeId)} onDone={reload} />
    </div>
  );
}

function RangeModal({
  open,
  onClose,
  nodeId,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  nodeId: number;
  bookId: number;
  onDone: () => void;
}) {
  const [from, setFrom] = useState(1);
  const [to, setTo] = useState(20);
  const [level, setLevel] = useState<string>("");
  const [tag, setTag] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ created: number; restored: number; skipped: number }>(
        `/nodes/${nodeId}/questions/range`,
        { from, to, difficulty_level: level ? +level : null, question_tag: tag || null }
      );
      toast(
        `${fa(r.created)} سوال ساخته شد` +
          (r.restored ? ` • ${fa(r.restored)} از آرشیو بازگشت` : "") +
          (r.skipped ? ` • ${fa(r.skipped)} از قبل موجود بود` : "")
      );
      onClose();
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="افزودن بازه سریع سوال">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">از شماره</label>
            <input type="number" min={1} className="input tabular" value={from} onChange={(e) => setFrom(+e.target.value)} />
          </div>
          <div>
            <label className="label">تا شماره</label>
            <input type="number" min={1} className="input tabular" value={to} onChange={(e) => setTo(+e.target.value)} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">سطح سختی (اختیاری — حسابان)</label>
            <select className="input" value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="">بدون سطح</option>
              <option value="1">سطح ۱</option>
              <option value="2">سطح ۲</option>
              <option value="3">سطح ۳</option>
            </select>
          </div>
          <div>
            <label className="label">نوع سوال (اختیاری)</label>
            <select className="input" value={tag} onChange={(e) => setTag(e.target.value)}>
              <option value="">بدون برچسب</option>
              <option value="مفهومی">مفهومی</option>
              <option value="محاسباتی">محاسباتی</option>
              <option value="حفظی">حفظی</option>
              <option value="ترکیبی">ترکیبی</option>
            </select>
          </div>
        </div>
        <p className="rounded-xl bg-surface-alt p-3 text-xs leading-5 text-ink-soft">
          سوال‌ها بدون جواب ساخته می‌شوند؛ پاسخ‌نامه را می‌توانی بعداً تدریجی تکمیل کنی. شماره‌های تکراری دوباره
          ساخته نمی‌شوند.
        </p>
        <div className="flex gap-2">
          <button className="btn-primary flex-1" onClick={submit} disabled={busy || to < from}>
            ساخت {fa(Math.max(0, to - from + 1))} سوال
          </button>
          <button className="btn-ghost" onClick={onClose}>
            انصراف
          </button>
        </div>
      </div>
    </Modal>
  );
}

function CompactModal({
  open,
  onClose,
  nodeId,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  nodeId: number;
  onDone: () => void;
}) {
  const [text, setText] = useState("");
  const submit = async () => {
    try {
      const r = await api.put<{ updated: number; created: number }>(`/nodes/${nodeId}/questions/bulk`, {
        compact: text,
      });
      toast(`${fa(r.updated)} پاسخ ثبت شد` + (r.created ? ` • ${fa(r.created)} سوال جدید ساخته شد` : ""));
      setText("");
      onClose();
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="ورودی فشرده پاسخ‌نامه">
      <div className="space-y-4">
        <div>
          <label className="label">متن پاسخ‌نامه</label>
          <textarea
            className="input h-32 font-mono"
            dir="ltr"
            placeholder="1:2, 2:3, 3:1, 4:4  یا  2 3 1 4 2 1"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <p className="rounded-xl bg-surface-alt p-3 text-xs leading-6 text-ink-soft">
          دو فرمت پشتیبانی می‌شود:
          <br />• <b dir="ltr">1:2, 2:3, 3:1</b> — شماره سوال : گزینه
          <br />• <b dir="ltr">2 3 1 4</b> — فقط گزینه‌ها به ترتیب، از سوال شماره ۱
          <br />
          مقدار <b>0</b> یا <b>-</b> یعنی بدون کلید.
        </p>
        <div className="flex gap-2">
          <button className="btn-primary flex-1" onClick={submit} disabled={!text.trim()}>
            ثبت پاسخ‌نامه
          </button>
          <button className="btn-ghost" onClick={onClose}>
            انصراف
          </button>
        </div>
      </div>
    </Modal>
  );
}
