/** Shared API types — mirrors the backend error envelope (app/errors.py). */

export interface ApiErrorBody {
  code: string;
  message: string;
  details: unknown;
}

export interface ApiErrorResponse {
  error: ApiErrorBody;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  env: string;
  timezone: string;
}
