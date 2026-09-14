/** Typed fetch client. Relative URLs by default (Vite proxies API paths). */

import type { ApiErrorBody } from "@/types/api";

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export class ApiError extends Error {
  code: string;
  status: number;
  details: unknown;

  constructor(body: ApiErrorBody, status: number) {
    super(body.message);
    this.name = "ApiError";
    this.code = body.code;
    this.status = status;
    this.details = body.details;
  }
}

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await parseBody(res);
  if (!res.ok) {
    const err = (body as { error?: ApiErrorBody } | null)?.error;
    throw new ApiError(
      {
        code: err?.code ?? "http_error",
        message: err?.message ?? `Request failed (${res.status})`,
        details: err?.details ?? null,
      },
      res.status,
    );
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, data?: unknown) =>
    apiFetch<T>(path, { method: "POST", body: JSON.stringify(data ?? {}) }),
  patch: <T>(path: string, data?: unknown) =>
    apiFetch<T>(path, { method: "PATCH", body: JSON.stringify(data ?? {}) }),
  put: <T>(path: string, data?: unknown) =>
    apiFetch<T>(path, { method: "PUT", body: JSON.stringify(data ?? {}) }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};
