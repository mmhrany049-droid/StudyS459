"""Persistence access — SQLAlchemy queries only, no business rules."""

from app.repositories.books import (
    create_book,
    get_activation,
    get_book,
    get_book_by_stable_key,
    get_latest_import,
    get_node,
    get_or_create_subject,
    get_subject,
    list_books,
    list_children,
    list_nodes_for_book,
    list_test_sets_for_book,
    question_counts_by_test_set,
    record_import,
    set_activation,
)

__all__ = [
    "create_book",
    "get_activation",
    "get_book",
    "get_book_by_stable_key",
    "get_latest_import",
    "get_node",
    "get_or_create_subject",
    "get_subject",
    "list_books",
    "list_children",
    "list_nodes_for_book",
    "list_test_sets_for_book",
    "question_counts_by_test_set",
    "record_import",
    "set_activation",
]
