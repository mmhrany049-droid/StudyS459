import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import { activateBook, deactivateBook, importBook, listBooks } from "@/api/books";
import { BookCard } from "@/features/books";
import type { Book, ConfigIssue, ImportResult } from "@/types/books";

type ImportState =
  | { status: "idle" }
  | { status: "reading" | "sending" }
  | { status: "done"; result: ImportResult }
  | { status: "error"; message: string; issues: ConfigIssue[] };

export default function Books() {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [importState, setImportState] = useState<ImportState>({ status: "idle" });

  const refresh = useCallback(async () => {
    try {
      setBooks(await listBooks());
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "خطای نامشخص");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const toggleActive = async (book: Book) => {
    setBusyId(book.id);
    try {
      if (book.active) await deactivateBook(book.id);
      else await activateBook(book.id);
      await refresh();
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "خطای نامشخص");
    } finally {
      setBusyId(null);
    }
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setImportState({ status: "reading" });
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text()) as unknown;
    } catch {
      setImportState({ status: "error", message: "فایل JSON معتبر نیست.", issues: [] });
      return;
    }
    setImportState({ status: "sending" });
    try {
      const result = await importBook(parsed);
      setImportState({ status: "done", result });
      await refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        const details = err.details as { issues?: ConfigIssue[] } | null;
        setImportState({
          status: "error",
          message: `${err.message} (کد: ${err.code})`,
          issues: details?.issues ?? [],
        });
      } else {
        setImportState({
          status: "error",
          message: err instanceof Error ? err.message : "خطای نامشخص",
          issues: [],
        });
      }
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">کتاب‌ها</h1>

      <div className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 font-semibold">ایمپورت کتاب (فایل JSON)</h2>
        <input
          type="file"
          accept=".json,application/json"
          onChange={(e) => void onFile(e.target.files?.[0])}
          className="text-sm"
        />
        {(importState.status === "reading" || importState.status === "sending") && (
          <p className="mt-2 text-sm text-slate-500">در حال ایمپورت…</p>
        )}
        {importState.status === "done" && (
          <p className="mt-2 text-sm text-green-700">
            {importState.result.status === "imported" ? "✅ ایمپورت شد" : "ℹ️ بدون تغییر (قبلاً ایمپورت شده)"} —{" "}
            {importState.result.node_count} گره، {importState.result.test_set_count} آزمون،{" "}
            {importState.result.question_count} سؤال
          </p>
        )}
        {importState.status === "error" && (
          <div className="mt-2 text-sm">
            <p className="text-red-600">❌ {importState.message}</p>
            {importState.issues.length > 0 && (
              <ul className="mt-1 max-h-48 list-disc overflow-auto pr-5 text-red-700">
                {importState.issues.slice(0, 30).map((issue, i) => (
                  <li key={i}>
                    <code className="text-xs">{issue.path}</code>: {issue.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {loadError && <p className="text-sm text-red-600">{loadError}</p>}
      {books === null && !loadError && <p className="text-sm text-slate-500">در حال بارگذاری…</p>}
      {books !== null && books.length === 0 && (
        <p className="rounded bg-white p-4 text-sm text-slate-500 shadow">
          هنوز کتابی ایمپورت نشده است. از بخش بالا یک فایل کانفیگ JSON انتخاب کنید.
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {(books ?? []).map((book) => (
          <BookCard key={book.id} book={book} busy={busyId === book.id} onToggleActive={toggleActive} />
        ))}
      </div>
    </div>
  );
}
