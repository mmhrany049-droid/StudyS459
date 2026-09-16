/** کلاینت API — SS459 backend */

const BASE = '/api'

export class ApiError extends Error {
  status: number
  detail: any
  constructor(status: number, detail: any) {
    super(typeof detail === 'string' ? detail : (detail?.message ?? `خطای ${status}`))
    this.status = status
    this.detail = detail
  }
}

async function request<T = any>(method: string, path: string, body?: any, query?: Record<string, any>): Promise<T> {
  let url = BASE + path
  if (query) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null) qs.set(k, String(v))
    const s = qs.toString()
    if (s) url += (url.includes('?') ? '&' : '?') + s
  }
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail: any = null
    try { detail = await res.json() } catch { /* ignore */ }
    throw new ApiError(res.status, detail?.detail ?? detail)
  }
  if (res.status === 204) return null as T
  return res.json()
}

export const api = {
  get: <T = any>(path: string, query?: Record<string, any>) => request<T>('GET', path, undefined, query),
  post: <T = any>(path: string, body?: any, query?: Record<string, any>) => request<T>('POST', path, body ?? {}, query),
  patch: <T = any>(path: string, body?: any) => request<T>('PATCH', path, body ?? {}),
  put: <T = any>(path: string, body?: any) => request<T>('PUT', path, body ?? {}),
  del: <T = any>(path: string) => request<T>('DELETE', path),
}

export function errMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.detail && typeof e.detail === 'object' && e.detail.message) return e.detail.message
    if (typeof e.detail === 'string' && e.detail) return e.detail
    return e.message
  }
  return 'خطای غیرمنتظره رخ داد.'
}
