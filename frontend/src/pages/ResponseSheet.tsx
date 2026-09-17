import { useEffect, useMemo, useRef, useState } from "react";
import { api, Book, TestSession, TopicNode, TreeResponse } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat, ExplainBox } from "../components/ui";
import { faNumber, minutes, percent, toPersianDigits } from "../lib/format";

type State = "ANSWERED" | "UNANSWERED" | "NOT_ENTERED";

const STATE_LABEL: Record<State, string> = {
  ANSWERED: "پاسخ داده",
  UNANSWERED: "نزده",
  NOT_ENTERED: "ثبت‌نشده",
};

export default function ResponseSheet() {
  const [books, setBooks] = useState<Book[]>([]);
  const [bookId, setBookId] = useState<number | null>(null);
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [count, setCount] = useState(10);
  const [pool, setPool] = useState<any>(null);
  const [session, setSession] = useState<TestSession | null>(null);
  const [choices, setChoices] = useState<Record<number, string | null>>({});
  const [cursor, setCursor] = useState(0);
  const [duration, setDuration] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
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

  useEffect(() => {
    if (!topicId) {
      setPool(null);
      return;
    }
    api
      .get<any>(`/test-engine/pool?topic_id=${topicId}&count=${count}`)
      .then(setPool)
      .catch((err) => setError(err.message));
  }, [topicId, count]);

  const leaves = useMemo(() => {
    const out: TopicNode[] = [];
    function walk(nodes: TopicNode[]) {
      nodes.forEach((node) => {
        if (node.is_leaf) out.push(node);
        walk(node.children ?? []);
      });
    }
    if (tree) walk(tree.topics);
    return out;
  }, [tree]);

  async function startSession() {
    if (!topicId) return;
    setStarting(true);
    setError(null);
    try {
      const created = await api.post<TestSession>("/test-sessions", {
        book_id: bookId,
        topic_id: topicId,
        count,
        start_now: true,
      });
      setSession(created);
      setChoices({});
      setCursor(0);
      setResult(null);
      setNotice(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setStarting(false);
    }
  }

  function setChoice(index: number, value: string | null) {
    const question = session?.questions?.[index];
    if (!question) return;
    setChoices((prev) => ({ ...prev, [question.question_id]: value }));
    setCursor(Math.min(index + 1, (session?.questions?.length ?? 1) - 1));
  }

  function onKeyDown(event: React.KeyboardEvent) {
    const index = Number((event.target as HTMLElement).dataset.index ?? cursor);
    if (["1", "2", "3", "4"].includes(event.key)) {
      event.preventDefault();
      setChoice(index, event.key);
    } else if (event.key === "0" || event.key === " ") {
      event.preventDefault();
      setChoice(index, "0");
    } else if (event.key === "Enter") {
      event.preventDefault();
      const next = listRef.current?.querySelector<HTMLElement>(`[data-index="${Math.min(index + 1, (session?.questions?.length ?? 1) - 1)}"]`);
      next?.focus();
      setCursor(Math.min(index + 1, (session?.questions?.length ?? 1) - 1));
    }
  }

  async function submit() {
    if (!session) return;
    const entries = (session.questions ?? []).map((question) => {
      const value = choices[question.question_id];
      if (value === undefined) {
        // untouched rows are NOT_ENTERED — never recorded as "unanswered" or "wrong"
        return { question_id: question.question_id, state: "NOT_ENTERED" };
      }
      if (value === null || value === "0") {
        return { question_id: question.question_id, state: "UNANSWERED" };
      }
      return { question_id: question.question_id, state: "ANSWERED", selected_choice: value };
    });
    try {
      const response = await api.post<any>(`/test-sessions/${session.id}/submit`, {
        entries,
        actual_duration_minutes: Number(duration) || undefined,
      });
      setResult(response);
      setNotice(
        response.pending_correction
          ? "بعضی سؤال‌ها پاسخ‌نامه نداشتند؛ نتیجه آن‌ها «قابل‌ارزیابی نیست» ثبت شد، نه غلط."
          : "جلسه ثبت شد؛ جمع درست + غلط + نزده = کل است.",
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  function counts() {
    const values = Object.values(choices);
    const answered = values.filter((value) => value && value !== "0").length;
    const unanswered = values.filter((value) => value === "0").length;
    const notEntered = (session?.questions?.length ?? 0) - answered - unanswered;
    return { answered, unanswered, notEntered };
  }

  if (error && !session) return <ErrorBox message={error} />;

  const summary = counts();

  return (
    <div className="grid gap-5 lg:grid-cols-4">
      <div className="lg:col-span-1 grid gap-5">
        <Card title="جلسه تست">
          <div className="grid gap-3">
            <div>
              <label className="label">کتاب</label>
              <select className="input" value={bookId ?? ""} onChange={(e) => setBookId(Number(e.target.value))}>
                {books.map((book) => (
                  <option key={book.id} value={book.id}>
                    {book.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">مبحث</label>
              <select className="input" value={topicId ?? ""} onChange={(e) => setTopicId(Number(e.target.value))}>
                <option value="">انتخاب کن…</option>
                {leaves.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">تعداد سؤال</label>
              <input
                className="input"
                inputMode="numeric"
                value={count}
                onChange={(e) => setCount(Math.max(1, Number(toPersianDigits(e.target.value).replace(/[^0-9]/g, "")) || 1))}
              />
            </div>
            {pool && (
              <div className="rounded-xl bg-ink-50 p-3 text-xs text-ink-600">
                موجودی بانک: <span className="num">{toPersianDigits(pool.available)}</span>
                {pool.without_answer_key > 0 && (
                  <>
                    {" "}
                    — بدون پاسخ‌نامه: <span className="num">{toPersianDigits(pool.without_answer_key)}</span>
                  </>
                )}
              </div>
            )}
            <button className="btn-primary" disabled={!topicId || starting} onClick={startSession}>
              {starting ? "در حال ساخت…" : "شروع جلسه"}
            </button>
          </div>
          <p className="muted mt-3">
            سیستم سؤال تکراری نمی‌دهد مگر لازم باشد؛ اگر بانک کافی نباشد صریح اعلام می‌شود و عدد الکی ساخته نمی‌شود.
          </p>
        </Card>

        {session && (
          <Card title="جمع‌بندی زنده">
            <div className="grid gap-3">
              <Stat label="پاسخ داده" value={toPersianDigits(summary.answered)} />
              <Stat label="نزده" value={toPersianDigits(summary.unanswered)} hint="خودت گفتی بلد نیستی/نزدی" />
              <Stat label="ثبت‌نشده" value={toPersianDigits(summary.notEntered)} hint="ردیف دست‌نخورده" />
            </div>
            <p className="muted mt-3">«ثبت‌نشده» ≠ «نزده»: اولی یعنی وارد نکردی، دومی یعنی نزدی.</p>
          </Card>
        )}
      </div>

      <div className="grid gap-5 lg:col-span-3">
        {!session ? (
          <Empty title="جلسه‌ای در جریان نیست" hint="یک مبحث انتخاب کن و جلسه را شروع کن." />
        ) : (
          <Card
            title={`پاسخ‌برگ — ${session.questions.length} سؤال`}
            action={<span className="muted">{session.planned_duration_label}</span>}
          >
            {notice && <div className="mb-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}
            <ul ref={listRef} className="mb-4 grid gap-1" onKeyDown={onKeyDown}>
              {session.questions.map((question, index) => {
                const value = choices[question.question_id];
                const state: State = value === undefined ? "NOT_ENTERED" : value === "0" ? "UNANSWERED" : "ANSWERED";
                return (
                  <li
                    key={question.question_id}
                    className={`flex flex-wrap items-center gap-2 rounded-xl border p-2 ${
                      index === cursor ? "border-brand-300 bg-brand-50/40" : "border-ink-200"
                    }`}
                  >
                    <span className="num w-10 text-center text-xs text-ink-600">{toPersianDigits(question.sequence_no)}</span>
                    <div className="flex gap-1">
                      {["1", "2", "3", "4"].map((option) => (
                        <button
                          key={option}
                          data-index={index}
                          className={`h-9 w-10 rounded-lg border text-sm ${
                            value === option
                              ? "border-brand-500 bg-brand-600 text-white"
                              : "border-ink-200 bg-white hover:bg-ink-50"
                          }`}
                          onClick={() => setChoice(index, option)}
                        >
                          {toPersianDigits(option)}
                        </button>
                      ))}
                      <button
                        data-index={index}
                        className={`h-9 rounded-lg border px-3 text-xs ${
                          value === "0"
                            ? "border-warn-600 bg-warn-100 text-warn-600"
                            : "border-ink-200 bg-white text-ink-600 hover:bg-ink-50"
                        }`}
                        onClick={() => setChoice(index, "0")}
                      >
                        نزده
                      </button>
                    </div>
                    <Badge tone={state === "ANSWERED" ? "ok" : state === "UNANSWERED" ? "warn" : "muted"}>
                      {STATE_LABEL[state]}
                    </Badge>
                    {question.has_answer_key === false && <Badge tone="bad">بدون پاسخ‌نامه</Badge>}
                  </li>
                );
              })}
            </ul>

            <div className="flex flex-wrap items-center gap-3 rounded-xl bg-ink-50 p-3">
              <label className="label mb-0">این جلسه چند دقیقه طول کشید؟</label>
              <input
                className="input max-w-[120px]"
                inputMode="numeric"
                value={duration}
                onChange={(event) => setDuration(event.target.value.replace(/[^0-9]/g, ""))}
                placeholder="مثلاً 35"
              />
              <button className="btn-primary" onClick={submit}>
                پایان و ثبت
              </button>
              <span className="muted">
                کاربر هیچ‌وقت زمان را از قبل پیش‌بینی نمی‌کند؛ زمان واقعی بعد از انجام پرسیده می‌شود.
              </span>
            </div>
          </Card>
        )}

        {result && (
          <Card title="نتیجه">
            <div className="grid gap-3 sm:grid-cols-5">
              <Stat label="کل" value={toPersianDigits(result.total ?? 0)} />
              <Stat label="درست" value={toPersianDigits(result.correct ?? 0)} />
              <Stat label="غلط" value={toPersianDigits(result.wrong ?? 0)} />
              <Stat label="نزده" value={toPersianDigits(result.unanswered ?? 0)} />
              <Stat label="ثبت‌نشده" value={toPersianDigits(result.not_entered ?? 0)} />
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-4">
              <Stat label="دقت" value={result.accuracy === null ? "نامعلوم" : percent(result.accuracy)} />
              <Stat label="قابل‌ارزیابی نیست" value={toPersianDigits(result.not_evaluable ?? 0)} />
              <Stat label="سکه" value={toPersianDigits(result.rewards?.coins ?? 0)} />
              <Stat label="وضعیت" value={result.status === "completed" ? "تمام‌شده" : (result.status ?? "")} />
            </div>
            {result.invariant_ok !== undefined && (
              <p className="muted mt-3">
                بررسی صحت: درست + غلط + نزده = کل {result.invariant_ok ? "✓" : "✗"}
              </p>
            )}
            <div className="mt-3">
              <ExplainBox
                compact
                explain={{
                  what: `زمان واقعی ${minutes(result.duration_minutes)} در برابر برآورد ${minutes(
                    result.planned_duration_low,
                  )} تا ${minutes(result.planned_duration_high)}`,
                  why: "پیش‌بینی زمان فقط از جلسه‌های واقعی قبلی ساخته می‌شود؛ در ماه اول عمداً محافظه‌کارانه است.",
                  evidence: {
                    total: result.total,
                    correct: result.correct,
                    wrong: result.wrong,
                    unanswered: result.unanswered,
                  },
                  what_can_i_change: ["زمان واقعی هر جلسه را ثبت کن تا برآورد دقیق‌تر شود."],
                }}
              />
            </div>
            {result.pending_correction ? (
              <p className="muted mt-3">
                {toPersianDigits(result.missing_answer_keys)} سؤال پاسخ‌نامه نداشت؛ نتیجه‌شان «قابل‌ارزیابی نیست» ماند و غلط شمرده نشد.
              </p>
            ) : (
              <p className="muted mt-3">غلط‌ها و نزده‌ها به صف مرور می‌روند؛ نزده «غلط» شمرده نمی‌شود.</p>
            )}
            <div className="mt-3 flex items-center gap-2">
              <button className="btn-soft btn-xs" onClick={startSession}>
                جلسه جدید همین مبحث
              </button>
              <span className="muted">
                میانگین هر سؤال:{" "}
                {result.average_seconds_per_question
                  ? `${faNumber(result.average_seconds_per_question)} ثانیه`
                  : "نامعلوم"}
              </span>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
