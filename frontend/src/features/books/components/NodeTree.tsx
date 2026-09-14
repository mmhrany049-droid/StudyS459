import type { TreeNode } from "@/types/books";

/** Generic recursive tree — no per-book assumptions (spec 03/05). */

function NodeItem({ node, depth }: { node: TreeNode; depth: number }) {
  const hasKids = node.children.length > 0;
  const body = (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-600">
          {node.node_type}
        </span>
        <span className="font-semibold">{node.title}</span>
        {!node.is_leaf && (
          <span className="text-xs text-slate-400">({node.children.length})</span>
        )}
      </div>
      {node.test_sets.length > 0 && (
        <ul className="mt-1 space-y-1">
          {node.test_sets.map((ts) => (
            <li key={ts.id} className="text-sm text-slate-600">
              📝 {ts.title}
              <span className="mr-2 rounded bg-blue-50 px-1.5 text-xs text-blue-700">
                {ts.test_type}
              </span>
              <span className="mr-1 text-xs text-slate-400">
                {ts.question_count} سؤال
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );

  if (!hasKids) {
    return <div className="py-1">{body}</div>;
  }
  return (
    <details open={depth < 2} className="py-1">
      <summary className="cursor-pointer list-item">{body}</summary>
      <div className="mr-4 border-r-2 border-slate-200 pr-3">
        {node.children.map((child) => (
          <NodeItem key={child.id} node={child} depth={depth + 1} />
        ))}
      </div>
    </details>
  );
}

export default function NodeTree({ nodes }: { nodes: TreeNode[] }) {
  if (nodes.length === 0) {
    return <p className="text-sm text-slate-500">این کتاب هنوز گرهی ندارد.</p>;
  }
  return (
    <div className="rounded bg-white p-4 shadow">
      {nodes.map((node) => (
        <NodeItem key={node.id} node={node} depth={0} />
      ))}
    </div>
  );
}
