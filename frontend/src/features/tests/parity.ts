import type { Parity } from "@/types/test";

export const PARITY_OPTIONS: Array<{ value: Parity; label: string }> = [
  { value: "odd", label: "فرد" },
  { value: "even", label: "زوج" },
  { value: "any", label: "همه" },
];

export function parityLabel(parity: Parity | null | undefined): string {
  if (parity === "odd") return "فرد";
  if (parity === "even") return "زوج";
  if (parity === "any") return "همه";
  return "—";
}
