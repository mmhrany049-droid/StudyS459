import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, Card, Chip, ErrorBox, Loading, Stat } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { fa, pct } from "../lib/api";
import type { Book, TreeNode } from "../lib/types";

export default function Books() {
  const { data: books, error, loading, reload } = useFetch<Book[]>("/books");
  const [openBook, setOpenBook] = useState<number | null>(null);

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!books) return null;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-black">کتاب‌ها و بانک تست</h1>
        <p className="muted mt-1">
          کتاب را باز کن، به مبحث برو و برای همان مبحث سوال و پاسخ‌نامه چهارگزینه‌ای تعریف کن.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {books.map((b) => (
          <Card key={b.id} className="cursor-pointer" >
            <div onClick={() => setOpenBook(openBook === b.id ? null : b.id)}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="font-bold leading-6">{b.title}</h3>
                  <p className="muted mt-0.5">{b.publisher}</p>
                </div>
                <span
                  className="h-9 w-9 shrink-0 rounded-xl"
                  style={{ backgroundColor: b.color + "22", border: `2px solid ${b.color}` }}
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Chip tone="brand">{b.subject}</Chip>
                <Chip>{fa(b.chapters)} فصل</Chip>
                {b.has_difficulty_levels && <Chip tone="warn">۳ سطح سختی</Chip>}
              </div>
              <div className="mt-4 space-y-2.5">
                <div>
                  <div className="mb-1 flex justify-between text-xs text-ink-soft">
                    <span>Coverage</span>
                    <span className="tabular">{pct(b.coverage)}</span>
                  </div>
                  <Bar value={b.coverage} tone="brand" height="h-1.5" />
                </div>
                <div>
                  <div className="mb-1 flex justify-between text-xs text-ink-soft">
                    <span>Accuracy</span>
                    <span className="tabular">{pct(b.accuracy)}</span>
                  </div>
                  <Bar value={b.accuracy} tone="good" height="h-1.5" />
                </div>
              </div>
              <p className="mt-3 text-xs text-ink-mute">
                {fa(b.total_questions)} سوال در بانک • برای دیدن درخت مبحث کلیک کن
              </p>
            </div>
            <a
              href={`/api/books/${b.id}/export`}
              className="btn-ghost btn-xs mt-3 w-full"
              onClick={(e) => e.stopPropagation()}
            >
              ⬇️ خروجی JSON بانک
            </a>
          </Card>
        ))}
      </div>

      {openBook && <BookTree bookId={openBook} />}
    </div>
  );
}

function BookTree({ bookId }: { bookId: number }) {
  const { data, error, loading, reload } = useFetch<{ book: { title: string; publisher: string }; nodes: TreeNode[] }>(
    `/books/${bookId}/nodes`,
    [bookId]
  );
  const [q, setQ] = useState("");

  if (loading) return <Loading label="در حال بارگذاری درخت مبحث…" />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const totals = data.nodes.reduce(
    (acc, n) => {
      acc.total += n.stats?.total || 0;
      acc.key += n.stats?.with_answer_key || 0;
      acc.att += n.stats?.attempted || 0;
      return acc;
    },
    { total: 0, key: 0, att: 0 }
  );

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="section-title">{data.book.title}</h2>
        <input
          className="input max-w-xs"
          placeholder="جستجوی مبحث…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <div className="mb-4 grid grid-cols-3 gap-3">
        <Stat label="سوال در بانک" value={fa(totals.total)} />
        <Stat label="دارای پاسخ‌نامه" value={fa(totals.key)} tone="good" />
        <Stat label="حداقل یک‌بار زده‌شده" value={fa(totals.att)} tone="brand" />
      </div>
      <div className="space-y-1.5">
        {data.nodes.map((n) => (
          <NodeRow key={n.id} node={n} bookId={bookId} depth={0} filter={q} />
        ))}
      </div>
    </Card>
  );
}

function matches(n: TreeNode, f: string): boolean {
  if (!f) return true;
  if (n.title.includes(f)) return true;
  return n.children.some((c) => matches(c, f));
}

function NodeRow({ node, bookId, depth, filter }: { node: TreeNode; bookId: number; depth: number; filter: string }) {
  const [open, setOpen] = useState(depth === 0 ? false : true);
  if (!matches(node, filter)) return null;
  const s = node.stats;
  const hasChildren = node.children.length > 0;
  const isLeaf = !hasChildren && node.has_test_set;

  const typeChip: Record<string, [string, string]> = {
    concours: ["کنکور سراسری", "warn"],
    checkup: ["چکاپ", "sky"],
    comprehensive: ["جامع", "brand"],
    chapter_exam: ["آزمون فصل", "brand"],
  };
  const tc = typeChip[node.node_type];

  return (
    <div style={{ marginInlineStart: depth * 16 }}>
      <div
        className={`group flex items-center gap-2.5 rounded-xl px-3 py-2 transition hover:bg-surface-alt ${
          depth === 0 ? "bg-surface-alt/60 font-semibold" : ""
        }`}
      >
        {hasChildren ? (
          <button
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-xs text-ink-soft hover:bg-white"
            onClick={() => setOpen(!open)}
          >
            {open ? "▾" : "◂"}
          </button>
        ) : (
          <span className="w-6 shrink-0 text-center text-xs text-ink-mute">•</span>
        )}

        <span className="min-w-0 flex-1 truncate text-sm" title={node.title}>
          {node.title}
        </span>

        {tc && <Chip tone={tc[1]}>{tc[0]}</Chip>}

        {s && s.total > 0 && (
          <div className="hidden shrink-0 items-center gap-2 sm:flex">
            <span className="tabular text-xs text-ink-mute">{fa(s.total)} سوال</span>
            <div className="w-16">
              <Bar value={s.coverage} tone={s.coverage < 0.3 ? "bad" : "good"} height="h-1.5" />
            </div>
            <span className="tabular w-10 text-left text-xs text-ink-soft">{pct(s.coverage)}</span>
            {s.open_review > 0 && <Chip tone="bad">{fa(s.open_review)} مرور</Chip>}
          </div>
        )}

        {isLeaf && (
          <Link
            to={`/books/${bookId}/nodes/${node.id}/bank`}
            className="btn-soft btn-xs shrink-0 opacity-0 transition group-hover:opacity-100"
          >
            بانک تست
          </Link>
        )}
      </div>

      {open &&
        node.children.map((c) => (
          <NodeRow key={c.id} node={c} bookId={bookId} depth={depth + 1} filter={filter} />
        ))}
    </div>
  );
}
