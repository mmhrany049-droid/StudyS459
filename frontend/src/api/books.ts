import { api } from "./client";
import type { Activation, Book, BookTree, ImportResult } from "@/types/books";

export function listBooks(): Promise<Book[]> {
  return api.get<Book[]>("/books");
}

export function getBook(bookId: number): Promise<Book> {
  return api.get<Book>(`/books/${bookId}`);
}

export function getBookTree(bookId: number): Promise<BookTree> {
  return api.get<BookTree>(`/books/${bookId}/nodes`);
}

export function activateBook(bookId: number): Promise<Activation> {
  return api.post<Activation>(`/users/me/books/${bookId}/activate`);
}

export function deactivateBook(bookId: number): Promise<Activation> {
  return api.delete<Activation>(`/users/me/books/${bookId}/activate`);
}

export function importBook(config: unknown): Promise<ImportResult> {
  return api.post<ImportResult>("/books/import", config);
}
