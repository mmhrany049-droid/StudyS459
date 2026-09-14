import { api } from "./client";
import type { HealthResponse } from "@/types/api";

export function fetchHealth(): Promise<HealthResponse> {
  return api.get<HealthResponse>("/health");
}
