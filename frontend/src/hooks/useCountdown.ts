import { useEffect, useState } from "react";

/** Ticks down to zero from `initialSeconds`; freezes at 0. Null = disabled. */
export function useCountdown(initialSeconds: number | null): number | null {
  const [left, setLeft] = useState<number | null>(initialSeconds);

  useEffect(() => {
    setLeft(initialSeconds);
  }, [initialSeconds]);

  useEffect(() => {
    if (left === null || left <= 0) return;
    const t = window.setTimeout(() => setLeft(left - 1), 1000);
    return () => window.clearTimeout(t);
  }, [left]);

  return left;
}

/** Seconds elapsed since mount (display only — server owns real durations). */
export function useElapsed(active: boolean): number {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setSecs((s) => s + 1), 1000);
    return () => window.clearInterval(t);
  }, [active]);
  return secs;
}
