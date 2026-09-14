import type { TreeNode } from "@/types/books";

/** Flatten a node tree into id/label options (labels carry the full path). */
export function flattenTree(
  nodes: TreeNode[],
  prefix = "",
): Array<{ id: number; label: string }> {
  const out: Array<{ id: number; label: string }> = [];
  for (const n of nodes) {
    const label = prefix ? `${prefix} / ${n.title}` : n.title;
    out.push({ id: n.id, label });
    out.push(...flattenTree(n.children, label));
  }
  return out;
}
