import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Book, TopicNode, TreeResponse } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat } from "../components/ui";
import { toPersianDigits, toLatinDigits } from "../lib/format";

type QuestionRow = {
  id: number;
  sequence_no: number;
  difficulty_level?: number | null;
  answer_key?: string | null;
  answer_key_version?: number;
  has_answer_key?: boolean;
  active?: boolean;
  stats?: Record<string, unknown>;
};

const OPTIONS = ["1", "2", "3", "4"];

export default function QuestionBank() {
  const [books, setBooks] = useState<Book[]>([]);
  const [bookId, setBookId] = useState<number | null>(null);
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<QuestionRow[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [draft, setDraft] = useState<Record<number, string>>({});
  const [cursor, setCursor] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [rangeFrom, setRangeFrom] = useState("");
  const [rangeTo, setRangeTo] = useState("");
  const [rangeLevel, setRangeLevel] = useState("");
  const [compact, setCompact] = useState("");
  const [showCompact, setShowCompact] = useState(false);
  const listRef = useRef<HTMLUListElement | null>(null);

  useEffect(() => {
    api
      .get<{ books: Book[] }>("/books")
      .then((payload) => {
        setBooks(payload.books);
        if (payload.books[0]) setBookId(payload.books[0].id);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!bookId) return;
    api.get<TreeResponse>(`/books/${bookId}/tree`).then(setTree).catch((err) => setError(err.message));
    setTopicId(null);
  }, [bookId]);

  const flatTopics = useMemo(() => {
    const out: TopicNode[] = [];
    function walk(nodes: TopicNode[]) {
      nodes.forEach((node) => {
        out.push(node);
        walk(node.children ?? []);
      });
    }
    if (tree) walk(tree.topics);
    return out;
  }, [tree]);

  const leaves = useMemo(() => flatTopics.filter((node) => node.is_leaf), [flatTopics]);

  const loadQuestions = useCallback(async (id: number) => {
    const payload = await api.get<{ items: QuestionRow[]; summary: Record<string, number>; total: number }>(
      `/books/${bookId}/nodes/${id}/questions`,
    );
    setQuestions(payload.items);
    setSummary(payload.summary);
    setDraft({});
    setCursor(0);
  }, [bookId]);

  useEffect(() => {
    if (topicId && bookId) loadQuestions(topicId);
  }, [topicId, bookId, loadQuestions]);

  async function saveDraft() {
    if (!bookId || !topicId) return;
    const items = Object.entries(draft)
      .filter(([, value]) => value !== "")
      .map(([id, value]) => {
        const row = questions.find((item) => item.id === Number(id));
        return { sequence_no: row?.sequence_no ?? 0, answer_key: value };
      })
      .filter((item) => item.sequence_no);
    if (items.length === 0) return;
    setSaving(true);
    try {
      const result = await api.put<any>(`/books/${bookId}/nodes/${topicId}/answer-key`, {
        items,
        reason: "ورود گروهی پاسخ‌نامه",
      });
      setNotice(
        `${toPersianDigits(result.updated ?? items.length)} پاسخ‌نامه ذخیره شد؛ نسخه قبلی پاک نشد و تاریخچه دارد.`,
      );
      await loadQuestions(topicId);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function addRange() {
    if (!bookId || !topicId) return;
    try {
      const result = await api.post<any>(`/books/${bookId}/nodes/${topicId}/questions/range`, {
        from_sequence: Number(toLatinDigits(rangeFrom)),
        to_sequence: Number(toLatinDigits(rangeTo)),
        level: rangeLevel ? Number(toLatinDigits(rangeLevel)) : undefined,
      });
      setNotice(`${toPersianDigits(result.created)} سؤال ساخته شد (${toPersianDigits(result.skipped)} تکراری رد شد).`);
      await loadQuestions(topicId);
      setRangeFrom("");
      setRangeTo("");
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function applyCompact() {
    if (!bookId || !topicId) return;
    try {
      const result = await api.post<any>(`/books/${bookId}/nodes/${topicId}/answer-key/compact`, {
        text: compact,
        start_sequence: 1,
        apply: true,
      });
      setNotice(
        `${toPersianDigits(result.parsed)} کلید خوانده شد، ${toPersianDigits(result.updated)} ذخیره شد، ${toPersianDigits(
          result.invalid ?? 0,
        )} نامعتبر بود.`,
      );
      setCompact("");
      await loadQuestions(topicId);
    } catch (err: any) {
      setError(err.message);
    }
  }

  function assign(index: number, value: string) {
    const row = questions[index];
    if (!row) return;
    setDraft((prev) => ({ ...prev, [row.id]: value }));
    setCursor(Math.min(index + 1, questions.length - 1));
  }

  function onKeyDown(event: React.KeyboardEvent) {
    const focusedIndex = Number((event.target as HTMLElement).dataset.index ?? cursor);
    if (["1", "2", "3", "4"].includes(event.key)) {
      event.preventDefault();
      assign(focusedIndex, event.key);
    } else if (event.key === "0" || event.key === " ") {
      event.preventDefault();
      assign(focusedIndex, "0"); // 0 = بدون پاسخ (نزده)
    } else if (event.key === "Enter") {
      event.preventDefault();
      setCursor(Math.min(focusedIndex + 1, questions.length - 1));
      const next = listRef.current?.querySelector<HTMLInputElement>(`[data-index="${focusedIndex + 1}"]`);
      next?.focus();
    }
  }

  if (error) return <ErrorBox message={error} />;

  return (
    <div className="grid gap-5 lg:grid-cols-4">
      <div className="lg:col-span-1">
        <Card title="۱. کتاب و مبحث">
          <div className="grid gap-3">
            <div>
              <label className="label">کتاب</label>
              <select className="input" value={bookId ?? ""} onChange={(event) => setBookId(Number(event.target.value))}>
                {books.map((book) => (
                  <option key={book.id} value={book.id}>
                    {book.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">مبحث (برگ‌ها = قابل سؤال)</label>
              <select
                className="input"
                value={topicId ?? ""}
                onChange={(event) => setTopicId(Number(event.target.value))}
              >
                <option value="">انتخاب کن…</option>
                {leaves.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.title} ({toPersianDigits(node.depth)})
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="muted mt-3">
            این صفحه «بانک تست این مبحث» است: سؤال‌ها، پاسخ‌نامه‌ها و نسخه‌بندی هر تغییر.
          </p>
        </Card>
      </div>

      <div className="grid gap-5 lg:col-span-3">
        {!topicId ? (
          <Empty title="یک مبحث انتخاب کن" hint="بعد از انتخاب، فهرست بزرگ سؤال‌ها با چهار گزینه باز می‌شود." />
        ) : (
          <>
            <Card
              title={
                <span>
                  {flatTopics.find((node) => node.id === topicId)?.title} — بانک تست
                </span>
              }
              action={
                <div className="flex gap-2">
                  <button className="btn-ghost btn-xs" onClick={() => setShowCompact((value) => !value)}>
                    چسباندن فشرده
                  </button>
                  <button className="btn-primary btn-xs" disabled={saving} onClick={saveDraft}>
                    ذخیره پاسخ‌نامه‌های این صفحه
                  </button>
                </div>
              }
            >
              <div className="mb-4 grid gap-3 sm:grid-cols-3">
                <Stat label="سؤال‌ها" value={toPersianDigits(summary.total ?? questions.length)} />
                <Stat label="با پاسخ‌نامه" value={toPersianDigits(summary.with_answer_key ?? 0)} />
                <Stat label="بدون پاسخ‌نامه" value={toPersianDigits(summary.without_answer_key ?? 0)} />
              </div>

              {notice && <div className="mb-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}

              <div className="mb-4 grid gap-3 rounded-xl bg-ink-50 p-3 sm:grid-cols-4">
                <div>
                  <label className="label">افزودن بازه از</label>
                  <input className="input" inputMode="numeric" value={rangeFrom} onChange={(e) => setRangeFrom(e.target.value)} />
                </div>
                <div>
                  <label className="label">تا</label>
                  <input className="input" inputMode="numeric" value={rangeTo} onChange={(e) => setRangeTo(e.target.value)} />
                </div>
                <div>
                  <label className="label">سطح سختی (اختیاری)</label>
                  <input className="input" inputMode="numeric" value={rangeLevel} onChange={(e) => setRangeLevel(e.target.value)} />
                </div>
                <div className="flex items-end">
                  <button className="btn-soft btn-xs w-full" onClick={addRange}>
                    افزودن بازه
                  </button>
                </div>
              </div>

              {showCompact && (
                <div className="mb-4 rounded-xl border border-ink-200 p-3">
                  <label className="label">
                    قالب‌های مجاز: <code dir="ltr">1:2,2:3,3:1</code> یا رشته ارقام <code dir="ltr">2314</code> — رقم صفر یعنی «بدون پاسخ»
                  </label>
                  <textarea
                    className="input min-h-[70px]"
                    dir="ltr"
                    value={compact}
                    onChange={(event) => setCompact(event.target.value)}
                    placeholder="1:2,2:3,3:1,4:0"
                  />
                  <button className="btn-primary btn-xs mt-2" onClick={applyCompact}>
                    اعمال روی پاسخ‌نامه
                  </button>
                </div>
              )}

              <p className="muted mb-2">
                کلیدهای میان‌بر: <span className="num">۱ تا ۴</span> انتخاب گزینه، <span className="num">۰</span> یا{" "}
                <span className="num">Space</span> یعنی «نزده»، <span className="num">Enter</span> سؤال بعدی.
              </p>

              {questions.length === 0 ? (
                <Empty title="سؤالی ثبت نشده" hint="با «افزودن بازه» سؤال‌ها را بساز (مثلاً ۱ تا ۳۰)." />
              ) : (
                <ul ref={listRef} className="grid gap-1" onKeyDown={onKeyDown}>
                  {questions.map((row, index) => {
                    const value = draft[row.id] ?? row.answer_key ?? "";
                    const dirty = draft[row.id] !== undefined;
                    return (
                      <li
                        key={row.id}
                        className={`flex flex-wrap items-center gap-2 rounded-xl border p-2 ${
                          index === cursor ? "border-brand-300 bg-brand-50/40" : "border-ink-200"
                        }`}
                      >
                        <span className="num w-12 text-center text-xs text-ink-600">
                          {toPersianDigits(row.sequence_no)}
                        </span>
                        <div className="flex gap-1">
                          {OPTIONS.map((option) => (
                            <button
                              key={option}
                              className={`h-8 w-9 rounded-lg border text-sm ${
                                value === option
                                  ? "border-brand-500 bg-brand-600 text-white"
                                  : "border-ink-200 bg-white text-ink-800 hover:bg-ink-50"
                              }`}
                              onClick={() => assign(index, option)}
                            >
                              {toPersianDigits(option)}
                            </button>
                          ))}
                          <button
                            className={`h-8 rounded-lg border px-2 text-xs ${
                              value === "0"
                                ? "border-warn-600 bg-warn-100 text-warn-600"
                                : "border-ink-200 bg-white text-ink-600 hover:bg-ink-50"
                            }`}
                            onClick={() => assign(index, "0")}
                          >
                            نزده
                          </button>
                        </div>
                        <input
                          data-index={index}
                          className="input h-8 w-20 text-center"
                          inputMode="numeric"
                          value={value === "0" ? "" : value}
                          placeholder="—"
                          onFocus={() => setCursor(index)}
                          onChange={(event) =>
                            setDraft((prev) => ({ ...prev, [row.id]: toLatinDigits(event.target.value).replace(/[^0-4]/g, "") }))
                          }
                        />
                        {row.has_answer_key ? (
                          <Badge tone={dirty ? "warn" : "ok"}>
                            {dirty ? "در حال تغییر" : `کلید ${toPersianDigits(row.answer_key ?? "")}`}
                          </Badge>
                        ) : (
                          <Badge tone="warn">بدون کلید</Badge>
                        )}
                        {row.answer_key_version && row.answer_key_version > 1 && (
                          <Badge tone="muted">نسخه {toPersianDigits(row.answer_key_version)}</Badge>
                        )}
                        {row.difficulty_level ? <Badge tone="muted">سطح {toPersianDigits(row.difficulty_level)}</Badge> : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
