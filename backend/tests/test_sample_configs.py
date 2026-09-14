"""Acceptance: the three shipped book structures load (spec 17: Books)."""

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Question, QuestionTopicMap, Subject
from app.services import books as book_service
from app.services.book_importer import import_book_config

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "book_configs"

EXPECTED = {
    "chem2_mobtakeren.json": {"nodes": 16, "sets": 9, "questions": 103},
    "hesab1_olgoo.json": {"nodes": 14, "sets": 12, "questions": 104},
    "phys2_kheilisabz.json": {"nodes": 17, "sets": 7, "questions": 84},
}


def _load(name: str) -> dict:
    return json.loads((CONFIGS_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_shipped_config_loads(db_session: Session, name: str) -> None:
    result = import_book_config(db_session, user_id=1, config=_load(name))
    exp = EXPECTED[name]
    assert result.status == "imported"
    assert result.node_count == exp["nodes"]
    assert result.test_set_count == exp["sets"]
    assert result.question_count == exp["questions"]


def test_three_structures_differ(db_session: Session) -> None:
    """The three books have genuinely different hierarchies (spec 01/17)."""
    type_sets = set()
    for name in EXPECTED:
        result = import_book_config(db_session, user_id=1, config=_load(name))
        tree = book_service.get_book_tree(db_session, book_id=result.book_id)

        def walk(nodes):
            for n in nodes:
                yield n.node_type
                yield from walk(n.children)

        type_sets.add(tuple(sorted(set(walk(tree.nodes)))))
    assert len(type_sets) == 3


def test_multi_topic_and_stable_ids(db_session: Session) -> None:
    import_book_config(db_session, user_id=1, config=_load("chem2_mobtakeren.json"))
    # At least one question maps to more than one topic.
    rows = db_session.execute(
        select(QuestionTopicMap.question_id, func.count(QuestionTopicMap.node_id))
        .group_by(QuestionTopicMap.question_id)
        .having(func.count(QuestionTopicMap.node_id) > 1)
    ).all()
    assert len(rows) > 0
    # Stable keys unique per book.
    keys = db_session.execute(select(Question.stable_key)).scalars().all()
    assert len(keys) == len(set(keys))


def test_all_three_coexist(db_session: Session) -> None:
    for name in EXPECTED:
        import_book_config(db_session, user_id=1, config=_load(name))
    assert db_session.execute(select(func.count()).select_from(Subject)).scalar() == 3
    books = book_service.list_books(db_session, user_id=1)
    assert len(books) == 3
    assert all(b.active for b in books)
    assert sum(b.question_count for b in books) == 103 + 104 + 84
