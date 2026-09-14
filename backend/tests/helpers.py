"""Shared builders for Book Engine tests."""

import copy

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
