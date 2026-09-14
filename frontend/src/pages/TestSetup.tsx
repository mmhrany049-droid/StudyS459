import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { getBookTree, listBooks } from "@/api/books";
import { createSession, getParityState } from "@/api/tests";
import { PARITY_OPTIONS, SelectableNodeTree, parityLabel } from "@/features/tests";
import type { Book, BookTree, TreeNode } from "@/types/books";
import type { InsufficientDetails, Parity, ParityState } from "@/types/test";
import { cn } from "@/utils/cn";

export default function TestSetup() {
  const navigate = useNavigate();
  const [books, setBooks] = useState<Book[]>([]);
  const [bookId, setBookId] = useState<number | null>(null);
  const [tree, setTree] = useState<BookTree | null>(null);
  const [node, setNode] = useState<TreeNode | null>(null);
  const [parityState, setParityState] = useState<ParityState | null>(null);

  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [count, setCount] = useState("10");
  const [parity, setParity] = useState<Parity>("any");
  const [timed, setTimed] = useState(false);
  const [limitMin, setLimitMin] = useState("20");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shortage, setShortage] = useState<InsufficientDetails | null>(null);

  useEffect(() => {
    listBooks()
      .then((all) => {
        const active = all.filter((b) => b.active);
        setBooks(all);
        if (active.length > 0) setBookId(active[0].id);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "خطا"));
  }, []);

  useEffect(() => {
    if (bookId === null) return;
    setTree(null);
    setNode(null);
    getBookTree(bookId)
      .then(setTree)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "خطا"));
  }, [bookId]);

  const pickNode = (n: TreeNode) => {
    setNode(n);
    setParityState(null);
    getParityState(n.id).then(setParityState).catch(() => setParityState(null));
  };

  const start = async () => {
    if (!node) {
      setError("اول یک مبحث انتخاب کنید.");
      return;
    }
    setBusy(true);
    setError(null);
    setShortage(null);
    try {
      const view = await createSession({
        node_id: node.id,
        count: Math.max(1, Number(count) || 1),
        sequence_from: from === "" ? null : Number(from),
        sequence_to: to === "" ? null : Number(to),
        parity,
        timed,
        time_limit_seconds: timed ? Math.max(1, Number(limitMin) || 1) * 60 : null,
      });
      navigate(`/test/${view.session.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`${err.message} (کد: ${err.code})`);
        if (err.code === "insufficient_questions") {
          setShortage(err.details as InsufficientDetails);
        }
      } else {
        setError(err instanceof Error ? err.message : "خطای نامشخص");
      }
    } finally {
      setBusy(false);
    }
  };

  const book = books.find((b) => b.id === bookId) ?? null;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">تست جدید</h1>

      <div className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 font-semibold">۱. کتاب و مبحث</h2>
        <select
          value={bookId ?? ""}
          onChange={(e) => setBookId(Number(e.target.value))}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          {books.map((b) => (
            <option key={b.id} value={b.id} disabled={!b.active}>
              {b.title} — {b.publisher} {!b.active ? "(غیرفعال)" : ""}
            </option>
          ))}
        </select>
        {book && !book.active && (
          <p className="mt-2 text-sm text-red-600">
            این کتاب غیرفعال است؛ برای ساخت تست ابتدا آن را در صفحه کتاب‌ها فعال کنید.
          </p>
        )}
        {tree && (
          <div className="mt-3 max-h-72 overflow-auto rounded border border-slate-200 p-2">
            <SelectableNodeTree nodes={tree.nodes} selectedId={node?.id ?? null} onSelect={pickNode} />
          </div>
        )}
        {node && (
          <p className="mt-2 text-sm">
            مبحث انتخاب‌شده: <strong>{node.title}</strong>
            {parityState && (
              <span className="mr-2 text-slate-500">
                — آخرین زوج/فرد: {parityLabel(parityState.last_parity)}
                {parityState.suggested_parity && (
                  <>
                    {" "}— پیشنهاد:{" "}
                    <button
                      type="button"
                      onClick={() => setParity(parityState.suggested_parity as Parity)}
                      className="rounded bg-blue-100 px-2 py-0.5 text-blue-800 hover:bg-blue-200"
                    >
                      {parityLabel(parityState.suggested_parity)}
                    </button>
                  </>
                )}
              </span>
            )}
          </p>
        )}
      </div>

      <div className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 font-semibold">۲. بازه و زوج/فرد و تعداد</h2>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="flex flex-col gap-1">
            از سؤال
            <input
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              inputMode="numeric"
              placeholder="—"
              className="w-24 rounded border border-slate-300 px-2 py-1"
            />
          </label>
          <label className="flex flex-col gap-1">
            تا سؤال
            <input
              value={to}
              onChange={(e) => setTo(e.target.value)}
              inputMode="numeric"
              placeholder="—"
              className="w-24 rounded border border-slate-300 px-2 py-1"
            />
          </label>
          <label className="flex flex-col gap-1">
            تعداد
            <input
              value={count}
              onChange={(e) => setCount(e.target.value)}
              inputMode="numeric"
              className="w-24 rounded border border-slate-300 px-2 py-1"
            />
          </label>
          <div className="flex flex-col gap-1">
            <span>زوج / فرد</span>
            <div className="flex gap-1">
              {PARITY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setParity(opt.value)}
                  className={cn(
                    "rounded border px-3 py-1",
                    parity === opt.value
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-slate-300 hover:bg-slate-100",
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 font-semibold">۳. زمان</h2>
        <div className="flex items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={timed} onChange={(e) => setTimed(e.target.checked)} />
            زمان‌دار
          </label>
          {timed && (
            <label className="flex items-center gap-2">
              <input
                value={limitMin}
                onChange={(e) => setLimitMin(e.target.value)}
                inputMode="numeric"
                className="w-20 rounded border border-slate-300 px-2 py-1"
              />
              دقیقه
            </label>
          )}
          {!timed && <span className="text-slate-500">بدون محدودیت زمانی (مدت واقعی ثبت می‌شود).</span>}
        </div>
      </div>

      {error && (
        <div className="rounded bg-red-50 p-3 text-sm text-red-700">
          <p>❌ {error}</p>
          {shortage && (
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="w-full text-red-600">
                موجودی این بازه: {shortage.available} سؤال (فرد: {shortage.available_odd} — زوج:{" "}
                {shortage.available_even})
              </span>
              <button
                type="button"
                onClick={() => setCount(String(Math.max(1, shortage.available)))}
                className="rounded border border-red-300 px-2 py-1 hover:bg-red-100"
              >
                تعداد = {shortage.available}
              </button>
              {parity !== "even" && shortage.available_even > 0 && (
                <button
                  type="button"
                  onClick={() => setParity("even")}
                  className="rounded border border-red-300 px-2 py-1 hover:bg-red-100"
                >
                  سوییچ به زوج ({shortage.available_even})
                </button>
              )}
              {parity !== "odd" && shortage.available_odd > 0 && (
                <button
                  type="button"
                  onClick={() => setParity("odd")}
                  className="rounded border border-red-300 px-2 py-1 hover:bg-red-100"
                >
                  سوییچ به فرد ({shortage.available_odd})
                </button>
              )}
              {parity !== "any" && (
                <button
                  type="button"
                  onClick={() => setParity("any")}
                  className="rounded border border-red-300 px-2 py-1 hover:bg-red-100"
                >
                  همه ({shortage.available_odd + shortage.available_even})
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => void start()}
        disabled={busy || !node}
        className="rounded bg-slate-900 px-6 py-2 text-white hover:bg-slate-700 disabled:opacity-50"
      >
        {busy ? "در حال ساخت…" : "شروع تست"}
      </button>
    </div>
  );
}
