/** Book Engine types — mirrors backend schemas/books.py. */

export interface Subject {
  id: number;
  name: string;
  grade: number;
  track: string;
  type: string;
}

export interface Book {
  id: number;
  stable_key: string;
  title: string;
  publisher: string;
  edition: string;
  config_version: number;
  grade: number;
  track: string;
  subject: Subject;
  active: boolean;
  activated_at: string | null;
  node_count: number;
  test_set_count: number;
  question_count: number;
}

export interface TestSetSummary {
  id: number;
  title: string;
  test_type: string;
  node_id: number | null;
  question_count: number;
  meta: Record<string, unknown>;
}

export interface TreeNode {
  id: number;
  parent_id: number | null;
  node_type: string;
  title: string;
  code: string;
  order_index: number;
  is_leaf: boolean;
  meta: Record<string, unknown>;
  test_sets: TestSetSummary[];
  children: TreeNode[];
}

export interface BookTree {
  book_id: number;
  nodes: TreeNode[];
}

export interface Activation {
  user_id: number;
  book_id: number;
  active: boolean;
  activated_at: string;
}

export interface ImportResult {
  status: "imported" | "unchanged";
  book_id: number;
  stable_key: string;
  node_count: number;
  test_set_count: number;
  question_count: number;
}

export interface ConfigIssue {
  path: string;
  message: string;
}
