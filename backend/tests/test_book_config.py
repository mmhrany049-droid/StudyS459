"""Unit tests: pure config validation (no DB, no framework)."""

import pytest

from app.domain.book_config import BookConfigError, content_hash, validate_book_config
from tests.helpers import base_config


def _issue_paths(exc: BookConfigError) -> list[str]:
    return [i.path for i in exc.issues]


def test_valid_config_defaults() -> None:
    v = validate_book_config(base_config())
    assert v.book.stable_key == "demo_book"
    assert v.book.subject.grade == 11  # defaulted from book
    assert v.book.subject.track == "mathematics"
    assert v.nodes[0].code == "ch1"  # code defaults to key
    q1, _, q3 = v.questions
    assert q1.stable_key == "demo_book:drill1:1"  # auto stable key
    assert q1.answer_type == "choice"
    assert q1.topic_keys == ("t1",)  # defaulted from test set's node
    assert q3.topic_keys == ("t1", "t2")  # explicit multi-topic kept


def test_top_level_must_be_object() -> None:
    with pytest.raises(BookConfigError) as e:
        validate_book_config([1, 2])
    assert _issue_paths(e.value) == ["$"]


def test_unknown_top_level_key_rejected() -> None:
    cfg = base_config()
    cfg["test_set"] = []  # typo trap (singular)
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert "$.test_set" in _issue_paths(e.value)


def test_missing_book_fields() -> None:
    with pytest.raises(BookConfigError) as e:
        validate_book_config({"book": {}, "nodes": [], "test_sets": [], "questions": []})
    paths = _issue_paths(e.value)
    assert "$.book.stable_key" in paths
    assert "$.book.subject" in paths
    assert "$.nodes" in paths


def test_duplicate_node_key() -> None:
    cfg = base_config()
    cfg["nodes"].append({"key": "t1", "type": "title", "title": "دوباره", "order": 9})
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("duplicate node key" in i.message for i in e.value.issues)


def test_unknown_parent() -> None:
    cfg = base_config()
    cfg["nodes"][1]["parent"] = "nope"
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("unknown parent" in i.message for i in e.value.issues)


def test_self_cycle() -> None:
    cfg = base_config()
    cfg["nodes"][1]["parent"] = "t1"
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("cycle detected" in i.message for i in e.value.issues)


def test_two_node_cycle() -> None:
    cfg = base_config()
    cfg["nodes"][0]["parent"] = "t2"  # ch1 -> t2 -> ch1
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("cycle detected" in i.message for i in e.value.issues)


def test_duplicate_sibling_order_rejected() -> None:
    cfg = base_config()
    cfg["nodes"][2]["order"] = 1  # t2 same order as t1 under ch1
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("duplicate order" in i.message for i in e.value.issues)


def test_same_order_under_different_parents_ok() -> None:
    cfg = base_config()
    cfg["nodes"].append({"key": "ch2", "type": "chapter", "title": "فصل ۲", "order": 2})
    cfg["nodes"].append({"key": "t3", "type": "title", "title": "عنوان ۳", "order": 1, "parent": "ch2"})
    validate_book_config(cfg)  # must not raise


def test_undeclared_node_type_rejected_when_declared() -> None:
    cfg = base_config()
    cfg["nodes"][1]["type"] = "lesson"
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("unknown node type" in i.message for i in e.value.issues)


def test_any_node_type_ok_when_not_declared() -> None:
    cfg = base_config()
    del cfg["node_types"]
    cfg["nodes"][1]["type"] = "custom_type"
    validate_book_config(cfg)  # must not raise


def test_bad_test_type() -> None:
    cfg = base_config()
    cfg["test_sets"][0]["test_type"] = "quiz"
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("must be one of" in i.message for i in e.value.issues)


def test_test_set_unknown_node() -> None:
    cfg = base_config()
    cfg["test_sets"][0]["node"] = "nope"
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("unknown node key" in i.message for i in e.value.issues)


def test_duplicate_sequence_rejected() -> None:
    cfg = base_config()
    cfg["questions"].append({"test_set": "drill1", "sequence_no": 2})
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("ascending" in i.message for i in e.value.issues)


def test_non_ascending_sequence_rejected() -> None:
    cfg = base_config()
    cfg["questions"] = [
        {"test_set": "drill1", "sequence_no": 5},
        {"test_set": "drill1", "sequence_no": 3},
    ]
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("ascending" in i.message for i in e.value.issues)


def test_sequences_tracked_per_test_set() -> None:
    cfg = base_config()
    cfg["questions"] = [
        {"test_set": "drill1", "sequence_no": 1},
        {"test_set": "check1", "sequence_no": 1, "topics": ["t1"]},
        {"test_set": "drill1", "sequence_no": 2},
        {"test_set": "check1", "sequence_no": 2, "topics": ["t2"]},
    ]
    validate_book_config(cfg)  # must not raise


def test_duplicate_question_stable_key() -> None:
    cfg = base_config()
    cfg["questions"][0]["stable_key"] = "Q"
    cfg["questions"][1]["stable_key"] = "Q"
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("duplicate question stable_key" in i.message for i in e.value.issues)


def test_unknown_topic() -> None:
    cfg = base_config()
    cfg["questions"][2]["topics"] = ["nope"]
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("unknown node key" in i.message for i in e.value.issues)


def test_question_without_any_topic_rejected() -> None:
    cfg = base_config()
    cfg["questions"][2]["topics"] = []  # check1 has no node either
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("maps to no topic" in i.message for i in e.value.issues)


def test_undeclared_difficulty_rejected() -> None:
    cfg = base_config()
    cfg["difficulty_levels"] = ["L1", "L2"]
    cfg["questions"][0]["difficulty"] = "L9"
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    assert any("unknown difficulty" in i.message for i in e.value.issues)


def test_any_difficulty_ok_when_not_declared() -> None:
    cfg = base_config()
    cfg["questions"][0]["difficulty"] = "hard"
    validate_book_config(cfg)  # must not raise


def test_json_booleans_rejected_as_ints() -> None:
    cfg = base_config()
    cfg["nodes"][1]["order"] = True
    cfg["questions"][0]["sequence_no"] = True
    with pytest.raises(BookConfigError) as e:
        validate_book_config(cfg)
    paths = _issue_paths(e.value)
    assert "$.nodes[1].order" in paths
    assert "$.questions[0].sequence_no" in paths


def test_empty_answer_key_rejected_but_null_ok() -> None:
    cfg = base_config()
    cfg["questions"][0]["answer_key"] = ""
    with pytest.raises(BookConfigError):
        validate_book_config(cfg)
    cfg["questions"][0]["answer_key"] = None  # missing-key flow (spec 11/13)
    validate_book_config(cfg)  # must not raise


def test_content_hash_deterministic() -> None:
    a = base_config()
    b = base_config()
    assert content_hash(a) == content_hash(b)
    b["book"]["title"] = "دیگر"
    assert content_hash(a) != content_hash(b)
