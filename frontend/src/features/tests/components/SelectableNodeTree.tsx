import type { TreeNode } from "@/types/books";
import { cn } from "@/utils/cn";

interface Props {
  nodes: TreeNode[];
  selectedId: number | null;
  onSelect: (node: TreeNode) => void;
}

function Item({ node, depth, selectedId, onSelect }: Props & { node: TreeNode; depth: number }) {
  const selected = node.id === selectedId;
  const label = (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onSelect(node);
      }}
      className={cn(
        "rounded px-2 py-0.5 text-right text-sm",
        selected ? "bg-blue-600 text-white" : "hover:bg-slate-200",
      )}
    >
      <span className="ml-1 rounded bg-slate-200 px-1 text-xs text-slate-600">{node.node_type}</span>
      {node.title}
    </button>
  );
  if (node.children.length === 0) {
    return <div className="py-0.5">{label}</div>;
  }
  return (
    <details open={depth < 2} className="py-0.5">
      <summary className="cursor-pointer">{label}</summary>
      <div className="mr-4 border-r-2 border-slate-200 pr-2">
        {node.children.map((child) => (
          <Item key={child.id} node={child} depth={depth + 1} nodes={[]} selectedId={selectedId} onSelect={onSelect} />
        ))}
      </div>
    </details>
  );
}

export default function SelectableNodeTree({ nodes, selectedId, onSelect }: Props) {
  if (nodes.length === 0) {
    return <p className="text-sm text-slate-500">گرهی وجود ندارد.</p>;
  }
  return (
    <div>
      {nodes.map((node) => (
        <Item key={node.id} node={node} depth={0} nodes={[]} selectedId={selectedId} onSelect={onSelect} />
      ))}
    </div>
  );
}
