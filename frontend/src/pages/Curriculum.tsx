import { useEffect, useMemo, useState } from "react";
import { api, Book, TopicNode, TreeResponse } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat } from "../components/ui";
import { percent, toPersianDigits } from "../lib/format";

const NODE_LABEL: Record<string, string> = {
  book: "کتاب",
  chapter: "فصل",
  lesson: "درس",
  section: "بخش",
  subsection: "زیربخش",
  topic: "مبحث",
};

export default function Curriculum() {
  const [books, setBooks] = useState<Book[]>([]);
  const [activeBook, setActiveBook] = useState<number | null>(null);
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [overview, setOverview] = useState<any>(null);
  const [grade, setGrade] = useState<string | null>(null);
  const [outlineText, setOutlineText] = useState("");
  const [outlineBusy, setOutlineBusy] = useState(false);
  const [outlinePreview, setOutlinePreview] = useState<any>(null);
  const [outlineNotice, setOutlineNotice] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ books: Book[] }>("/books")
      .then((payload) => {
        setBooks(payload.books);
        if (payload.books[0]) setActiveBook(payload.books[0].id);
      })
      .catch((err) => setError(err.message));
    api
      .get<any>("/curriculum/overview")
      .then((payload) => {
        setOverview(payload);
        setGrade((current: string | null) => current ?? Object.keys(payload.grades ?? {})[0] ?? null);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!activeBook) return;
    api.get<TreeResponse>(`/books/${activeBook}/tree`).then(setTree).catch((err) => setError(err.message));
  }, [activeBook]);

  const stats = tree?.stats ?? {};

  async function refreshBook() {
    if (!activeBook) return;
    setTree(await api.get<TreeResponse>(`/books/${activeBook}/tree`));
    const fresh = await api.get<{ books: Book[] }>("/books");
    setBooks(fresh.books);
  }

  async function previewOutline() {
    if (!activeBook || !outlineText.trim()) return;
    setOutlineBusy(true);
    setOutlineNotice(null);
    try {
      setOutlinePreview(await api.post<any>(`/books/${activeBook}/outline`, { text: outlineText }));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setOutlineBusy(false);
    }
  }

  async function applyOutline() {
    if (!activeBook || !outlineText.trim()) return;
    setOutlineBusy(true);
    setOutlineNotice(null);
    try {
      const result = await api.post<any>(`/books/${activeBook}/outline`, { text: outlineText, apply: true });
      setOutlineNotice(
        `${toPersianDigits(result.created)} مبحث اضافه شد؛ ${toPersianDigits(result.reused)} مورد از قبل بود و دست‌نخورده ماند. ` +
          (result.markers ? `${toPersianDigits(result.markers)} آزمون چکاپ/جامع هم به بازه‌های پوشش اضافه شد.` : ""),
      );
      setOutlinePreview(null);
      await refreshBook();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setOutlineBusy(false);
    }
  }

  async function pickOutlineFile(file: File) {
    const text = await file.text();
    setOutlineText(text);
    setOutlinePreview(null);
    setOutlineNotice(`فایل «${file.name}» خوانده شد؛ اول پیش‌نمایش بگیر، بعد اضافه کن.`);
  }

  const flatCount = useMemo(() => {
    function count(nodes: TopicNode[]): number {
      return nodes.reduce((sum, node) => sum + 1 + count(node.children ?? []), 0);
    }
    return tree ? count(tree.topics) : 0;
  }, [tree]);

  async function toggle(node: TopicNode, next: boolean) {
    setBusy(node.id);
    setNotice(null);
    try {
      const result = await api.post<any>(`/topics/${node.id}/taught`, { taught: next, cascade: true });
      setNotice(
        next
          ? `«${node.title}» و ${toPersianDigits(Math.max(0, (result.affected?.length ?? 1) - 1))} زیرمبحث آن تدریس‌شده شدند.`
          : `تیک «${node.title}» و زیرمباحثش برداشته شد. تاریخچه پاک نشد؛ فقط وضعیت تدریس تغییر کرد.`,
      );
      if (activeBook) {
        const fresh = await api.get<TreeResponse>(`/books/${activeBook}/tree`);
        setTree(fresh);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  function renderNodes(nodes: TopicNode[], depth = 0) {
    return nodes.map((node) => {
      const isOpen = expanded[node.id] ?? depth < 1;
      const hasChildren = (node.children ?? []).length > 0;
      return (
        <li key={node.id}>
          <div
            className="flex flex-wrap items-center gap-2 rounded-xl px-2 py-2 hover:bg-ink-50"
            style={{ marginInlineStart: `${depth * 14}px` }}
          >
            <button
              className="grid h-6 w-6 place-items-center rounded-lg border border-ink-200 text-xs text-ink-600 disabled:opacity-30"
              disabled={!hasChildren}
              onClick={() => setExpanded({ ...expanded, [node.id]: !isOpen })}
              aria-label="باز و بسته کردن"
            >
              {hasChildren ? (isOpen ? "−" : "+") : "•"}
            </button>

            <label className="flex flex-1 cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4 accent-brand-600"
                disabled={busy === node.id}
                checked={node.taught_state === "checked"}
                ref={(element) => {
                  if (element) element.indeterminate = node.taught_state === "indeterminate";
                }}
                onChange={(event) => toggle(node, event.target.checked)}
              />
              <span className="text-sm">{node.title}</span>
            </label>

            <span className="badge-muted">{NODE_LABEL[node.node_type] ?? node.node_type}</span>
            {typeof node.total_questions === "number" && node.total_questions > 0 && (
              <span className="badge-muted num">{toPersianDigits(node.total_questions)} سؤال</span>
            )}
            {node.is_leaf && (
              <span className={(node.direct_question_count ?? 0) > 0 ? "badge-ok" : "badge-muted"}>
                {(node.direct_question_count ?? 0) > 0 ? "بانک تست دارد" : "بانک تست خالی"}
              </span>
            )}
            <span className={node.plannable ? "badge-ok" : "badge-muted"} title={node.plannable_reason}>
              {node.plannable ? "قابل برنامه‌ریزی" : "فقط نمایشی"}
            </span>
          </div>
          {hasChildren && isOpen && <ul>{renderNodes(node.children, depth + 1)}</ul>}
        </li>
      );
    });
  }

  if (error) return <ErrorBox message={error} />;

  return (
    <div className="grid gap-5 lg:grid-cols-4">
      <div className="lg:col-span-3">
        <Card
          title={<span>{tree?.book?.title ?? "مباحث کتاب‌ها"}</span>}
          action={
            <span className="muted">
              {toPersianDigits(stats.taught_topics ?? 0)} از {toPersianDigits(stats.topic_count ?? 0)} مبحث تدریس‌شده
            </span>
          }
        >
          {overview && (
            <div className="mb-3 grid gap-2">
              <div className="flex flex-wrap gap-2">
                {Object.keys(overview.grades ?? {}).map((name) => (
                  <button
                    key={name}
                    className={name === grade ? "btn-primary btn-xs" : "btn-ghost btn-xs"}
                    onClick={() => setGrade(name)}
                  >
                    پایه {name}
                  </button>
                ))}
              </div>
              <p className="muted">
                {(overview.grades?.[grade ?? ""] ?? []).length} کتاب در این پایه · قابل برنامه‌ریزی:{" "}
                {toPersianDigits(
                  (overview.grades?.[grade ?? ""] ?? []).reduce(
                    (sum: number, row: any) => sum + (row.plannable_topic_count ?? 0),
                    0,
                  ),
                )}{" "}
                مبحث · فقط نمایشی:{" "}
                {toPersianDigits(
                  (overview.grades?.[grade ?? ""] ?? []).reduce(
                    (sum: number, row: any) => sum + (row.visible_only_topic_count ?? 0),
                    0,
                  ),
                )}{" "}
                مبحث
              </p>
            </div>
          )}

          <div className="mb-3 flex flex-wrap gap-2">
            {books
              .filter((book) => !grade || !overview?.grades?.[grade] || (overview.grades[grade] as any[]).some((row) => row.book_id === book.id))
              .map((book) => (
              <button
                key={book.id}
                className={book.id === activeBook ? "btn-primary btn-xs" : "btn-ghost btn-xs"}
                onClick={() => setActiveBook(book.id)}
              >
                  {book.title}
                </button>
              ))}
          </div>

          <p className="muted mb-3">
            تیک زدن یک فصل، همه زیرمباحثش را تیک می‌زند؛ برداشتن تیک هم همین‌طور. «تدریس‌شده» با «یادگرفته‌شده» یکی نیست.
          </p>

          {notice && <div className="mb-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{notice}</div>}

          {!tree ? <Spinner /> : tree.topics.length === 0 ? <Empty title="مبحثی ثبت نشده" /> : <ul>{renderNodes(tree.topics)}</ul>}
          {tree && flatCount === 0 && <Empty title="درختی برای این کتاب نیست" />}
        </Card>
      </div>

      <div className="grid gap-5">
        <Card title="فهرست کتاب (فصل‌ها)">
          <p className="muted text-xs leading-6">
            فصل‌های کتابی که در برنامه نیست را اینجا اضافه کن: متن فهرست کتاب را بچسبان یا فایل متنی (UTF-8) را انتخاب کن.
            اول پیش‌نمایش را ببین؛ فقط «افزودن» انجام می‌شود و هیچ مبحثی پاک، جابه‌جا یا تغییرنام نمی‌شود.
          </p>
          <input
            type="file"
            accept=".txt,text/plain"
            className="mt-3 text-xs"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void pickOutlineFile(file);
            }}
          />
          <textarea
            className="input mt-2 min-h-[130px] font-mono text-xs"
            placeholder={"فصل ۱: ...\n• مبحث اول\n• آزمون چکاپ اول\nفصل ۲: ..."}
            value={outlineText}
            onChange={(event) => {
              setOutlineText(event.target.value);
              setOutlinePreview(null);
            }}
          />
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="btn-ghost btn-xs" disabled={!outlineText.trim() || outlineBusy} onClick={() => void previewOutline()}>
              پیش‌نمایش
            </button>
            <button className="btn-primary btn-xs" disabled={!outlineText.trim() || outlineBusy} onClick={() => void applyOutline()}>
              افزودن به کتاب
            </button>
          </div>
          {outlineNotice && <div className="mt-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">{outlineNotice}</div>}
          {outlinePreview && (
            <div className="mt-3 grid gap-2 text-xs">
              <div className="flex flex-wrap gap-2">
                <Badge>فصل {toPersianDigits(outlinePreview.stats.chapters)}</Badge>
                <Badge>بخش {toPersianDigits(outlinePreview.stats.sections)}</Badge>
                <Badge>زیربخش {toPersianDigits(outlinePreview.stats.subsections)}</Badge>
                {outlinePreview.stats.markers > 0 && (
                  <Badge tone="warn">چکاپ/جامع {toPersianDigits(outlinePreview.stats.markers)}</Badge>
                )}
              </div>
              <p className="muted">
                مبحث جدید: {toPersianDigits(outlinePreview.comparison.new_titles)} · از قبل موجود:{" "}
                {toPersianDigits(outlinePreview.comparison.already_present)}
              </p>
              <ul className="grid gap-1 text-ink-600">
                {(outlinePreview.sample ?? []).map((row: any, index: number) => (
                  <li key={index} style={{ paddingInlineStart: `${(row.depth ?? 0) * 12}px` }}>
                    <span className="muted">{NODE_LABEL[row.node_type] ?? ""} · </span>
                    {row.title}
                  </li>
                ))}
              </ul>
              {(outlinePreview.warnings ?? []).map((warning: string, index: number) => (
                <p key={index} className="rounded-lg bg-warn-50 p-2 text-warn-700">
                  {warning}
                </p>
              ))}
              <p className="muted">{outlinePreview.policy}</p>
            </div>
          )}
        </Card>

        <Card title="وضعیت این کتاب">
          <div className="grid gap-3">
            <Stat label="مباحث" value={toPersianDigits(stats.topic_count ?? 0)} />
            <Stat label="سؤال‌ها" value={toPersianDigits(stats.question_count ?? 0)} />
            <Stat label="با پاسخ‌نامه" value={toPersianDigits(stats.questions_with_answer_key ?? 0)} />
            <Stat
              label="بدون پاسخ‌نامه"
              value={toPersianDigits(stats.questions_missing_answer_key ?? 0)}
              hint="بدون پاسخ‌نامه، نتیجه «قابل‌ارزیابی نیست» می‌ماند و غلط شمرده نمی‌شود."
            />
          </div>
        </Card>

        <Card title="پیشرفت کتاب‌ها">
          <ul className="grid gap-3">
            {books.map((book) => {
              const bookStats = (book.stats ?? {}) as Record<string, number>;
              const taught = bookStats.taught_topics ?? 0;
              const topics = bookStats.topic_count ?? book.topic_count ?? 0;
              const withKey = bookStats.questions_with_answer_key ?? 0;
              const questions = bookStats.question_count ?? 0;
              return (
                <li key={book.id}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium">{book.title}</span>
                    <span className="num text-ink-600">
                      تدریس‌شده {toPersianDigits(taught)} از {toPersianDigits(topics)}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-ink-100">
                    <div
                      className="h-full rounded-full bg-brand-500"
                      style={{ width: `${Math.min(100, (taught / Math.max(1, topics)) * 100)}%` }}
                    />
                  </div>
                  <p className="muted mt-1 text-[11px]">
                    پوشش پاسخ‌نامه: {percent(questions ? withKey / questions : null, 0)} از {toPersianDigits(questions)} سؤال
                  </p>
                </li>
              );
            })}
          </ul>
          <p className="muted mt-3">
            پوشش و تدریس‌شده دو چیز جدا هستند: ممکن است مبحثی تدریس شده باشد ولی هنوز سؤالی از آن دیده نشده باشد.
          </p>
        </Card>

        <Card title="راهنما">
          <ul className="grid gap-2 text-xs leading-6 text-ink-600">
            <li>
              برای هر مبحث، «بانک تست» جدا در دسترس است: از صفحه <span className="font-medium text-ink-800">بانک تست</span> مبحث را انتخاب کن.
            </li>
            <li>
              اگر مبحثی تدریس نشده باشد، سؤال دادن از آن با هشدار همراه است؛ چون داده بی‌معنی تولید می‌کند.
            </li>
            <li>پیش‌نیازها را می‌توانی در همین صفحه از مسیر API ثبت کنی؛ چرخه‌ها رد می‌شوند.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
