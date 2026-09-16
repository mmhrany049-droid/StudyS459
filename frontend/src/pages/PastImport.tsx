import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Card, Chip, ChoiceRow, Empty, ErrorBox, Loading, Stat, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa, pct } from "../lib/api";
import type { AnswerSheet, Book } from "../lib/types";

/**
 * ورود تست‌های زده‌شده قبلی — سند 03_PAST_ATTEMPT_ENTRY
 * فقط انتخاب کتاب → لیست بزرگ چهارگزینه‌ای + «نزده». بدون سکه، is_imported=true.
 */
export default function PastImport() {
  const { data: books, loading: lb } = useFetch<Book[]>("/books");
  const [bookId, setBookId] = useState<number | null>(null);
  const [onlyUnattempted, setOnlyUnattempted] = useState(false);
  const path = bookId ? `/books/${bookId}/answer-sheet?only_unattempted=${onlyUnattempted}` : null;
  const { data: sheet, error, loading, reload } = useFetch<AnswerSheet>(path, [bookId, onlyUnattempted]);

  const [draft, setDraft] = useState<Record<number, number | null>>({});
  const [focusIdx, setFocusIdx] = useState(0);
  const [busy, setBusy] = useState(false);
  const rowRefs = useRef<(HTMLDivElement | null)[]>([]);
  const scope = `import_book:${bookId}`;

  const flat = useMemo(
    () =>
      (sheet?.groups || []).flatMap((g) =>
        g.questions.map((q) => ({ ...q, group: g.short_title, full: g.title }))
      ),
    [sheet]
  );

  // S2 — بازیابی پیش‌نویس
  useEffect(() => {
    if (!bookId) return;
    setDraft({});
    setFocusIdx(0);
    api
      .get<{ payload: Record<string, number | null> }>(`/drafts/${scope}`)
      .then((r) => {
        const p = r.payload || {};
        if (Object.keys(p).length) {
          setDraft(Object.fromEntries(Object.entries(p).map(([k, v]) => [+k, v])));
          toast(`پیش‌نویس ${fa(Object.keys(p).length)} پاسخ بازیابی شد`, "info");
        }
      })
      .catch(() => undefined);
  }, [bookId, scope]);

  const count = Object.keys(draft).length;
  const persist = useCallback(() => {
    if (!bookId || !Object.keys(draft).length) return;
    api.put("/drafts", { scope, payload: draft }).catch(() => undefined);
  }, [draft, scope, bookId]);

  useEffect(() => {
    if (count && count % 10 === 0) persist();
  }, [count, persist]);
  useEffect(() => {
    const t = setInterval(persist, 30000);
    return () => clearInterval(t);
  }, [persist]);

  const setAnswer = useCallback(
    (qid: number, v: number | null | undefined, advance = false) => {
      setDraft((d) => {
        const next = { ...d };
        if (v === undefined) delete next[qid];
        else next[qid] = v;
        return next;
      });
      if (advance) setFocusIdx((i) => Math.min(flat.length - 1, i + 1));
    },
    [flat.length]
  );

  // S1 — ورود سریع با صفحه‌کلید
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const row = flat[focusIdx];
      if (!row) return;
      if (["1", "2", "3", "4"].includes(e.key)) {
        e.preventDefault();
        setAnswer(row.id, +e.key, true);
      } else if (e.key === "0" || e.key === " ") {
        e.preventDefault();
        setAnswer(row.id, null, true);
      } else if (e.key === "Backspace") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusIdx((i) => Math.min(flat.length - 1, i + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flat, focusIdx, setAnswer]);

  useEffect(() => {
    rowRefs.current[focusIdx]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focusIdx]);

  const submit = async () => {
    const answers = Object.entries(draft).map(([qid, choice]) => ({ question_id: +qid, choice }));
    if (!answers.length) return toast("هیچ پاسخی وارد نشده", "info");
    setBusy(true);
    try {
      const r = await api.post<{
        imported: number;
        correct: number;
        wrong: number;
        unanswered: number;
        accuracy: number;
        message: string;
      }>("/attempts/import-by-book", { book_id: bookId, answers });
      toast(
        `${fa(r.imported)} تست ثبت شد • ${fa(r.correct)} درست، ${fa(r.wrong)} غلط، ${fa(r.unanswered)} نزده`
      );
      setDraft({});
      await api.del(`/drafts/${scope}`).catch(() => undefined);
      reload();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  const stats = useMemo(() => {
    let c = 0,
      w = 0,
      u = 0;
    for (const q of flat) {
      const v = draft[q.id];
      if (v === undefined) continue;
      if (v === null) u++;
      else if (v === q.answer_key) c++;
      else w++;
    }
    return { c, w, u };
  }, [draft, flat]);

  if (lb) return <Loading />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-black">ورود تست‌های زده‌شده قبلی</h1>
        <p className="muted mt-1">
          فقط کتاب را انتخاب کن؛ لیست بزرگ سوال‌ها گروه‌بندی‌شده بر اساس مبحث می‌آید. «نزده» جدا از غلط ثبت
          می‌شود و سکه‌ای تعلق نمی‌گیرد.
        </p>
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <label className="label">کتاب</label>
            <select
              className="input"
              value={bookId ?? ""}
              onChange={(e) => setBookId(e.target.value ? +e.target.value : null)}
            >
              <option value="">— انتخاب کتاب —</option>
              {books?.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.title} — {b.publisher}
                </option>
              ))}
            </select>
          </div>
          <button
            className={onlyUnattempted ? "btn-soft" : "btn-ghost"}
            onClick={() => setOnlyUnattempted(!onlyUnattempted)}
            disabled={!bookId}
          >
            فقط سوال‌های هرگز زده‌نشده
          </button>
        </div>
      </Card>

      {!bookId ? (
        <Empty icon="📖" title="یک کتاب انتخاب کن" hint="بعد از انتخاب، پاسخ‌نامه بزرگ همان کتاب نمایش داده می‌شود." />
      ) : loading ? (
        <Loading label="در حال ساخت پاسخ‌نامه…" />
      ) : error ? (
        <ErrorBox message={error} onRetry={reload} />
      ) : !sheet || flat.length === 0 ? (
        <Empty
          icon="🗂️"
          title="سوالی با پاسخ‌نامه در این کتاب نیست"
          hint="اول در بخش «کتاب‌ها و بانک تست» برای مباحث، سوال و پاسخ‌نامه تعریف کن. بدون کلید، تصحیح ممکن نیست."
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="کل سوال" value={fa(flat.length)} />
            <Stat label="پاسخ‌داده‌شده" value={fa(count)} tone="brand" />
            <Stat label="درست" value={fa(stats.c)} tone="good" />
            <Stat label="غلط" value={fa(stats.w)} tone="bad" />
            <Stat label="نزده" value={fa(stats.u)} tone="warn" />
          </div>

          <Card>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <p className="rounded-xl bg-brand-50 px-3 py-2 text-xs leading-6 text-brand-700">
                ⌨️ کلیدهای <b>۱ ۲ ۳ ۴</b> = گزینه و رفتن به بعدی • <b>۰/Space</b> = نزده • <b>Backspace</b> = قبلی
              </p>
              <button className="btn-primary" onClick={submit} disabled={busy || !count}>
                {busy ? "در حال ثبت…" : `ثبت ${fa(count)} پاسخ`}
              </button>
            </div>

            <div className="max-h-[62vh] overflow-y-auto pl-1">
              {sheet.groups.map((g) => (
                <div key={g.test_set_id} className="mb-4">
                  <div className="sticky top-0 z-10 mb-1.5 flex items-center gap-2 bg-white/95 py-1.5 backdrop-blur">
                    <Chip tone="brand">{g.short_title}</Chip>
                    <span className="truncate text-xs text-ink-mute" title={g.title}>
                      {g.title}
                    </span>
                    <span className="tabular mr-auto shrink-0 text-xs text-ink-mute">
                      {fa(g.questions.length)} سوال
                    </span>
                  </div>
                  {g.questions.map((q) => {
                    const idx = flat.findIndex((f) => f.id === q.id);
                    const v = draft[q.id];
                    return (
                      <div
                        key={q.id}
                        ref={(el) => {
                          rowRefs.current[idx] = el;
                        }}
                        onClick={() => setFocusIdx(idx)}
                        className={`flex items-center gap-3 rounded-xl px-3 py-2 transition ${
                          idx === focusIdx ? "row-focus" : "hover:bg-surface-alt"
                        }`}
                      >
                        <span className="tabular w-10 shrink-0 text-sm font-bold text-ink-soft">
                          {fa(q.sequence_no)}
                        </span>
                        <ChoiceRow value={v} onChange={(nv) => setAnswer(q.id, nv)} />
                        {v !== undefined && v !== null && (
                          <Chip tone={v === q.answer_key ? "good" : "bad"}>
                            {v === q.answer_key ? "درست" : "غلط"}
                          </Chip>
                        )}
                        {v === null && <Chip tone="warn">نزده</Chip>}
                        <span className="flex-1" />
                        {q.attempt_count > 0 && (
                          <span className="text-xs text-ink-mute">{fa(q.attempt_count)} بار قبلاً ثبت شده</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>

            {count > 0 && (
              <p className="mt-3 text-xs text-ink-mute">
                پیشرفت: {pct(count / flat.length)} — پیش‌نویس خودکار ذخیره می‌شود.
              </p>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
