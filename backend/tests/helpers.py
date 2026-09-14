"""Shared builders for Book/Test Engine tests."""

import copy

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BookNode
from app.services.book_importer import import_book_config

_BASE_CONFIG = {
    "book": {
        "stable_key": "demo_book",
        "title": "کتاب نمایشی",
        "publisher": "ناشر نمایشی",
        "grade": 11,
        "track": "mathematics",
        "edition": "1404",
        "config_version": 1,
        "subject": {"name": "شیمی", "type": "specialized"},
    },
    "node_types": ["chapter", "title"],
    "nodes": [
        {"key": "ch1", "type": "chapter", "title": "فصل ۱", "order": 1},
        {"key": "t1", "type": "title", "title": "عنوان ۱", "order": 1, "parent": "ch1"},
        {"key": "t2", "type": "title", "title": "عنوان ۲", "order": 2, "parent": "ch1"},
    ],
    "test_sets": [
        {"key": "drill1", "title": "تمرین ۱", "test_type": "normal", "node": "t1"},
        {"key": "check1", "title": "چکاپ ۱", "test_type": "checkup"},
    ],
    "questions": [
        {"test_set": "drill1", "sequence_no": 1, "answer_key": "2"},
        {"test_set": "drill1", "sequence_no": 2, "answer_key": "4"},
        {"test_set": "check1", "sequence_no": 1, "answer_key": "1", "topics": ["t1", "t2"]},
    ],
}


def base_config() -> dict:
    """Fresh minimal VALID config (mutate freely per test)."""
    return copy.deepcopy(_BASE_CONFIG)


def import_base(db_session: Session, config: dict | None = None):
    """Import base_config (or override) for user 1; return ImportOut."""
    return import_book_config(db_session, user_id=1, config=config or base_config())


def node_map(db_session: Session, book_id: int) -> dict[str, int]:
    """Map node code -> id for a book (base config uses code == key)."""
    rows = db_session.execute(
        select(BookNode.code, BookNode.id).where(BookNode.book_id == book_id)
    ).all()
    return {code: nid for code, nid in rows}
