import { useEffect, useState } from "react";
import { fetchHealth } from "@/api/health";
import type { HealthResponse } from "@/types/api";

type State =
  | { status: "loading" }
  | { status: "ok"; data: HealthResponse }
  | { status: "error"; message: string };

export function useHealth(): State {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    fetchHealth()
      .then((data) => {
        if (alive) setState({ status: "ok", data });
      })
      .catch((err: unknown) => {
        if (alive) {
          setState({
            status: "error",
            message: err instanceof Error ? err.message : "خطای نامشخص",
          });
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
