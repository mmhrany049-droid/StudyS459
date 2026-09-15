import { api } from "./client";
import type { User } from "@/types/users";

export function fetchMe(): Promise<User> {
  return api.get<User>("/users/me");
}

export function patchMe(payload: { display_name?: string; timezone?: string }): Promise<User> {
  return api.patch<User>("/users/me", payload);
}
