"""Book structure context: tree, paths, pools, parity (shared by analytics/goals).

pool(node) = questions mapped to the node or any descendant — the same pool
the test engine selects from (spec 06).
"""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BookNode, NodeParityState, Question, QuestionTopicMap
from app.repositories import books as book_repo


@dataclass
class BookContext:
    book_id: int
    nodes: list[BookNode]
    by_id: dict[int, BookNode]
    children: dict[int | None, list[BookNode]]
    depth: dict[int, int]
    path: dict[int, str]
    pool: dict[int, set[int]]  # node_id -> question ids (node + descendants)
    parity: dict[int, str]  # node_id -> last_parity


def build_book_context(db: Session, *, user_id: int, book_id: int) -> BookContext:
    nodes = book_repo.list_nodes_for_book(db, book_id)
    by_id = {n.id: n for n in nodes}
    children: dict[int | None, list[BookNode]] = defaultdict(list)
    for n in nodes:
        children[n.parent_id].append(n)
    depth: dict[int, int] = {}
    path: dict[int, str] = {}

    def walk(n: BookNode, d: int, trail: str) -> None:
        depth[n.id] = d
        path[n.id] = f"{trail} / {n.title}" if trail else n.title
        for c in children.get(n.id, []):
            walk(c, d + 1, path[n.id])

    for root in children.get(None, []):
        walk(root, 0, "")
    # Orphan-safe: unreachable nodes still get depth/path.
    for n in nodes:
        depth.setdefault(n.id, 0)
        path.setdefault(n.id, n.title)

    rows = db.execute(
        select(QuestionTopicMap.question_id, QuestionTopicMap.node_id)
        .join(Question, Question.id == QuestionTopicMap.question_id)
        .where(Question.book_id == book_id)
    ).all()
    direct: dict[int, set[int]] = defaultdict(set)
    for qid, nid in rows:
        direct[nid].add(qid)
    pool: dict[int, set[int]] = {}

    def pool_of(nid: int) -> set[int]:
        if nid in pool:
            return pool[nid]
        sub = set(direct.get(nid, set()))
        for c in children.get(nid, []):
            sub |= pool_of(c.id)
        pool[nid] = sub
        return sub

    for n in nodes:
        pool_of(n.id)

    parity_rows = db.execute(
        select(NodeParityState.node_id, NodeParityState.last_parity).where(
            NodeParityState.user_id == user_id,
            NodeParityState.node_id.in_([n.id for n in nodes]) if nodes else False,
        )
    ).all()
    return BookContext(
        book_id=book_id, nodes=nodes, by_id=by_id, children=children,
        depth=depth, path=path, pool=pool,
        parity={nid: p for nid, p in parity_rows},
    )
