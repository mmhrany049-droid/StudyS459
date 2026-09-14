import { Link } from "react-router-dom";
import type { Book } from "@/types/books";
import { cn } from "@/utils/cn";

interface Props {
  book: Book;
  onToggleActive: (book: Book) => void;
  busy: boolean;
}

export default function BookCard({ book, onToggleActive, busy }: Props) {
  return (
    <div className="rounded bg-white p-4 shadow">
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link
            to={`/books/${book.id}`}
            className="text-lg font-bold text-slate-900 hover:underline"
          >
            {book.title}
          </Link>
          <p className="text-sm text-slate-500">
            {book.publisher} — چاپ {book.edition} — {book.subject.name}
          </p>
        </div>
        <span
          className={cn(
            "rounded px-2 py-0.5 text-xs font-semibold",
            book.active ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-600",
          )}
        >
          {book.active ? "فعال" : "غیرفعال"}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-2 text-center text-sm">
        <div className="rounded bg-slate-50 p-2">
          <dt className="text-xs text-slate-500">گره‌ها</dt>
          <dd className="font-bold">{book.node_count}</dd>
        </div>
        <div className="rounded bg-slate-50 p-2">
          <dt className="text-xs text-slate-500">آزمون‌ها</dt>
          <dd className="font-bold">{book.test_set_count}</dd>
        </div>
        <div className="rounded bg-slate-50 p-2">
          <dt className="text-xs text-slate-500">سؤال‌ها</dt>
          <dd className="font-bold">{book.question_count}</dd>
        </div>
      </dl>
      <div className="mt-3 flex gap-2">
        <Link
          to={`/books/${book.id}`}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
        >
          ساختار کتاب
        </Link>
        <button
          type="button"
          disabled={busy}
          onClick={() => onToggleActive(book)}
          className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50"
        >
          {book.active ? "غیرفعال کن" : "فعال کن"}
        </button>
      </div>
    </div>
  );
}
