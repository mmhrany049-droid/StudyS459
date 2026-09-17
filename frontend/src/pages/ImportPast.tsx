import { useEffect, useState } from "react";
import { api, Book } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat } from "../components/ui";
import { JalaliDateInput } from "../components/JalaliDateInput";
import { todayJalali, toPersianDigits, toLatinDigits } from "../lib/format";

type SheetRow = {
  question_id: number;
  sequence_no: number;
  difficulty_level?: number | null;
  has_answer_key?: boolean;
  previous_state?: string | null;
  previous_choice?: string | null;
  previous_result?: string | null;
};

type SheetGroup = { topic_id: number; topic_title: string; questions: SheetRow[] };
type SheetChapter = { chapter_id: number; chapter_title: string; groups: SheetGroup[]; question_count: number };
type Sheet = {
  book: { id: number; title: string; publisher?: string };
  chapters: SheetChapter[];
  total_questions: number;
  instructions: string[];
};

/** The UX is fixed by the user request: کتاب → big grouped list → per row 1..4 or «نزده». */
export default function ImportPast() {
  const [books, setBooks] = useState<Book[]>([]);
  const [bookId, setBookId] = useState<number | null>(null);
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [marks, setMarks] = useState<Record<number, string>>({});
  const [date, setDate] = useState(todayJalali());
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    api
      .get<{ books: Book[] }>("/books")
      .then((payload) => {
        setBooks(payload.books);
        if (payload.books[0]) setBookId(payload.books[0].id);
      })
      .catch((err) => setError(err.message));
    api.get<any>("/attempts/import-summary").then(setSummary).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!bookId) return;
    setSheet(null);
    setMarks({});
    api.get<Sheet>(`/attempts/import-sheet?book_id=${bookId}`).then(setSheet).catch((err) => setError(err.message));
  }, [bookId]);

  function mark(questionId: number, value: string) {
    setMarks((prev) => {
      const next = { ...prev };
      if (next[questionId] === value) {
        delete next[questionId]; // untouched = NOT_ENTERED
      } else {
        next[questionId] = value;
      }
      return next;
    });
  }

  async function submit() {
    if (!bookId || !sheet) return;
    const items = Object.entries(marks).map(([questionId, value]) => {
      if (value === "0") return { question_id: Number(questionId), unanswered: true };
      return { question_id: Number(questionId), choice: value };
    });
    if (items.length === 0) {
      setError("هیچ ردیفی علامت نزده‌ای. حداقل یک سؤال را ۱ تا ۴ یا «نزده» کن.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<any>("/attempts/import-by-book", {
        book_id: bookId,
        items,
        date,
        note: note || undefined,
      });
      setNotice(
        `${toPersianDigits(result.attempts)} تلاش ثبت شد (${toPersianDigits(result.answered)} پاسخ‌داده، ${toPersianDigits(
          result.unanswered,
        )} نزده). این ورود سکه نمی‌دهد چون کار گذشته است.`,
      );
      setMarks({});
      const fresh = await api.get<Sheet>(`/attempts/import-sheet?book_id=${bookId}`);
      setSheet(fresh);
      api.get<any>("/attempts/import-summary").then(setSummary).catch(() => undefined);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const markedCount = Object.keys(marks).length;
  const unansweredCount = Object.values(marks).filter((value) => value === "0").length;

  if (error && !sheet) return <ErrorBox message={error} />;

  return (
    <div className="grid gap-5 lg:grid-cols-4">
      <div className="lg:col-span-1 grid gap-5">
        <Card title="۱. کتاب را انتخاب کن">
          <select className="input" value={bookId ?? ""} onChange={(event) => setBookId(Number(event.target.value))}>
            {books.map((book) => (
              <option key={book.id} value={book.id}>
                {book.title}
              </option>
            ))}
          </select>
          <p className="muted mt-3">
            لازم نیست اول مبحث انتخاب کنی؛ فهرست کامل سؤال‌های کتاب می‌آید و خودت ردیف‌ها را علامت می‌زنی.
          </p>
        </Card>

        <Card title="۲. تاریخ آزمون گذشته">
          <JalaliDateInput value={date} onChange={setDate} label="تاریخ (شمسی)" />
          <label className="label mt-3">یادداشت (اختیاری)</label>
          <input className="input" value={note} onChange={(event) => setNote(event.target.value)} placeholder="مثلاً آزمون کلاسی فصل ۱" />
          <div className="mt-3 grid gap-2">
            <Stat label="ردیف‌های علامت‌خورده" value={toPersianDigits(markedCount)} />
            <Stat label="از این تعداد «نزده»" value={toPersianDigits(unansweredCount)} />
          </div>
          <button className="btn-primary mt-3 w-full" disabled={busy || markedCount === 0} onClick={submit}>
            {busy ? "در حال ثبت…" : "ثبت نتیجه آزمون گذشته"}
          </button>
          <p className="muted mt-2">
            ردیف‌هایی که دست نمی‌زنی «ثبت‌نشده» می‌مانند: نه غلط، نه درست، نه نزده.
          </p>
        </Card>

        {summary && (
          <Card title="ورودهای قبلی">
            <div className="grid gap-2">
              <Stat label="جلسه‌های واردشده" value={toPersianDigits(summary.sessions ?? 0)} />
              <Stat label="تلاش‌ها" value={toPersianDigits(summary.attempts ?? 0)} />
              <Stat label="ثبت‌نشده" value={toPersianDigits(summary.not_entered ?? 0)} />
            </div>
            <p className="muted mt-2">{summary.note}</p>
          </Card>
        )}
      </div>

      <div className="lg:col-span-3">
        {!sheet ? (
          <Spinner />
        ) : sheet.total_questions === 0 ? (
          <Empty title="این کتاب سؤالی ندارد" hint="اول از صفحه «بانک تست» بازه سؤال‌ها را بساز." />
        ) : (
          <Card title={`۳. سؤال‌ها — ${sheet.book.title}`} action={<span className="muted">{toPersianDigits(sheet.total_questions)} سؤال</span>}>
            {notice && <div className="mb-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}
            {error && <div className="mb-3 rounded-xl bg-bad-100/60 p-3 text-xs text-bad-600">{error}</div>}
            <ul className="mb-3 grid gap-1 text-xs text-ink-600">
              {sheet.instructions.map((line, index) => (
                <li key={index}>• {line}</li>
              ))}
            </ul>

            <div className="grid max-h-[70vh] gap-4 overflow-y-auto pl-1">
              {sheet.chapters.map((chapter) => (
                <div key={chapter.chapter_id}>
                  <h3 className="mb-2 text-sm font-semibold text-ink-800">{chapter.chapter_title}</h3>
                  <div className="grid gap-3">
                    {chapter.groups.map((group) => (
                      <div key={group.topic_id} className="rounded-xl border border-ink-200 p-3">
                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-xs font-medium text-ink-800">{group.topic_title}</span>
                          <span className="muted">{toPersianDigits(group.questions.length)} سؤال</span>
                        </div>
                        <ul className="grid gap-1">
                          {group.questions.map((row) => {
                            const value = marks[row.question_id];
                            return (
                              <li key={row.question_id} className="flex flex-wrap items-center gap-2 rounded-lg px-2 py-1 hover:bg-ink-50">
                                <span className="num w-10 text-center text-xs text-ink-600">
                                  {toPersianDigits(row.sequence_no)}
                                </span>
                                <div className="flex gap-1">
                                  {["1", "2", "3", "4"].map((option) => (
                                    <button
                                      key={option}
                                      className={`h-8 w-9 rounded-lg border text-sm ${
                                        value === option
                                          ? "border-brand-500 bg-brand-600 text-white"
                                          : "border-ink-200 bg-white hover:bg-ink-50"
                                      }`}
                                      onClick={() => mark(row.question_id, option)}
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
                                    onClick={() => mark(row.question_id, "0")}
                                  >
                                    نزده
                                  </button>
                                </div>
                                <input
                                  className="input h-8 w-16 text-center"
                                  inputMode="numeric"
                                  value={value && value !== "0" ? value : ""}
                                  placeholder="—"
                                  onChange={(event) =>
                                    setMarks((prev) => ({
                                      ...prev,
                                      [row.question_id]: toLatinDigits(event.target.value).replace(/[^0-4]/g, ""),
                                    }))
                                  }
                                />
                                {row.has_answer_key === false && <Badge tone="bad">بدون پاسخ‌نامه</Badge>}
                                {row.previous_state && <Badge tone="muted">قبلاً: {row.previous_state}</Badge>}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
