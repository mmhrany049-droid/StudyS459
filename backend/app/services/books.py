"""Book read + activation services (spec 05/14)."""

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import BookNode, TestSet
from app.repositories import books as repo
from app.schemas.books import (
    ActivationOut,
    BookDetailOut,
    BookOut,
    BookTreeOut,
    ChildNodeOut,
    NodeChildrenOut,
    SubjectOut,
    TestSetSummaryOut,
    TreeNodeOut,
)
from app.services.users import get_or_create_single_user


def _subject_out(db: Session, book) -> SubjectOut:
    subject = repo.get_subject(db, book.subject_id)
    assert subject is not None  # FK guarantees it
    return SubjectOut(
        id=subject.id,
        name=subject.name,
        grade=subject.grade,
        track=subject.track,
        type=subject.subject_type,
    )


def _book_out(db: Session, book, *, user_id: int) -> BookOut:
    activation = repo.get_activation(db, user_id, book.id)
    return BookOut(
        id=book.id,
        stable_key=book.stable_key,
        title=book.title,
        publisher=book.publisher,
        edition=book.edition,
        config_version=book.config_version,
        grade=book.grade,
        track=book.track,
        subject=_subject_out(db, book),
        active=activation.active if activation else False,
        activated_at=activation.activated_at if activation else None,
        node_count=repo.count_nodes(db, book.id),
        test_set_count=repo.count_test_sets(db, book.id),
        question_count=repo.count_questions(db, book.id),
    )


def list_books(db: Session, *, user_id: int) -> list[BookOut]:
    get_or_create_single_user(db, user_id)
    return [_book_out(db, book, user_id=user_id) for book in repo.list_books(db)]


def get_book_detail(db: Session, *, user_id: int, book_id: int) -> BookDetailOut:
    get_or_create_single_user(db, user_id)
    book = repo.get_book(db, book_id)
    if book is None:
        raise AppError("book_not_found", "Book not found", status_code=404)
    return _book_out(db, book, user_id=user_id)


def _test_set_summaries(
    test_sets: list[TestSet], counts: dict[int, int], *, node_id: int | None = None
) -> list[TestSetSummaryOut]:
    out = []
    for ts in test_sets:
        if node_id is not None and ts.node_id != node_id:
            continue
        out.append(
            TestSetSummaryOut(
                id=ts.id,
                title=ts.title,
                test_type=ts.test_type,
                node_id=ts.node_id,
                question_count=counts.get(ts.id, 0),
                meta=ts.meta or {},
            )
        )
    return out


def get_book_tree(db: Session, *, book_id: int) -> BookTreeOut:
    book = repo.get_book(db, book_id)
    if book is None:
        raise AppError("book_not_found", "Book not found", status_code=404)
    nodes = repo.list_nodes_for_book(db, book_id)
    test_sets = repo.list_test_sets_for_book(db, book_id)
    counts = repo.question_counts_by_test_set(db, book_id)

    child_ids = {n.parent_id for n in nodes if n.parent_id is not None}
    by_parent: dict[int | None, list[BookNode]] = {}
    for node in nodes:
        by_parent.setdefault(node.parent_id, []).append(node)

    def build(node: BookNode) -> TreeNodeOut:
        return TreeNodeOut(
            id=node.id,
            parent_id=node.parent_id,
            node_type=node.node_type,
            title=node.title,
            code=node.code,
            order_index=node.order_index,
            is_leaf=node.id not in child_ids,
            meta=node.meta or {},
            test_sets=_test_set_summaries(test_sets, counts, node_id=node.id),
            children=[build(child) for child in by_parent.get(node.id, [])],
        )

    # Orphan-safe: nodes whose parent is missing still render at top level.
    known_ids = {n.id for n in nodes}
    roots = [n for n in nodes if n.parent_id is None or n.parent_id not in known_ids]
    return BookTreeOut(book_id=book_id, nodes=[build(root) for root in roots])


def get_node_children(db: Session, *, node_id: int) -> NodeChildrenOut:
    node = repo.get_node(db, node_id)
    if node is None:
        raise AppError("node_not_found", "Node not found", status_code=404)
    children = repo.list_children(db, node_id)
    test_sets = repo.list_test_sets_for_book(db, node.book_id)
    counts = repo.question_counts_by_test_set(db, node.book_id)
    child_ids = {c.parent_id for c in repo.list_nodes_for_book(db, node.book_id) if c.parent_id is not None}
    return NodeChildrenOut(
        node_id=node_id,
        children=[
            ChildNodeOut(
                id=child.id,
                parent_id=child.parent_id,
                node_type=child.node_type,
                title=child.title,
                code=child.code,
                order_index=child.order_index,
                is_leaf=child.id not in child_ids,
                meta=child.meta or {},
                test_sets=_test_set_summaries(test_sets, counts, node_id=child.id),
            )
            for child in children
        ],
    )


def set_book_active(db: Session, *, user_id: int, book_id: int, active: bool) -> ActivationOut:
    get_or_create_single_user(db, user_id)
    book = repo.get_book(db, book_id)
    if book is None:
        raise AppError("book_not_found", "Book not found", status_code=404)
    try:
        row = repo.set_activation(db, user_id, book_id, active=active)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ActivationOut(user_id=user_id, book_id=book_id, active=row.active, activated_at=row.activated_at)
