import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getBook, getBookTree } from "@/api/books";
import { NodeTree } from "@/features/books";
import type { Book, BookTree } from "@/types/books";

export default function BookDetail() {
  const { id } = useParams<{ id: string }>();
  const [book, setBook] = useState<Book | null>(null);
  const [tree, setTree] = useState<BookTree | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const bookId = Number(id);
    if (!Number.isInteger(bookId)) {
      setError("شناسه کتاب نامعتبر است.");
      return;
    }
    let alive = true;
    Promise.all([getBook(bookId), getBookTree(bookId)])
      .then(([b, t]) => {
        if (alive) {
          setBook(b);
          setTree(t);
        }
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "خطای نامشخص");
      });
    return () => {
      alive = false;
    };
  }, [id]);

  if (error) {
    return (
      <div className="space-y-2">
        <Link to="/books" className="text-sm text-blue-700 hover:underline">
          → بازگشت به کتاب‌ها
        </Link>
        <p className="text-red-600">{error}</p>
      </div>
    );
  }
  if (!book || !tree) {
    return <p className="text-sm text-slate-500">در حال بارگذاری…</p>;
  }
  return (
    <div className="space-y-4">
      <Link to="/books" className="text-sm text-blue-700 hover:underline">
        → بازگشت به کتاب‌ها
      </Link>
      <div>
        <h1 className="text-2xl font-bold">{book.title}</h1>
        <p className="text-sm text-slate-500">
          {book.publisher} — چاپ {book.edition} — {book.subject.name} —{" "}
          {book.active ? "فعال" : "غیرفعال"} — {book.node_count} گره / {book.test_set_count} آزمون /{" "}
          {book.question_count} سؤال
        </p>
      </div>
      <NodeTree nodes={tree.nodes} />
    </div>
  );
}
