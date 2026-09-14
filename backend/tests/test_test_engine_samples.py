"""Acceptance: Range + Odd/Even on the real shipped configs (spec 17: Test).

chem2 ch1 pool = exam1(10) + exam2(10) + check1(12) + check2(12)
               + concours-mapped-to-ch1 (seq 1,4,7,10,13) = 49 questions.
"""

import json
import random
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.errors import AppError
from app.schemas.tests import AnswerItem
from app.services import test_engine as engine
from app.services.book_importer import import_book_config
from tests.helpers import node_map

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "book_configs"


def _load(name: str) -> dict:
    return json.loads((CONFIGS_DIR / name).read_text(encoding="utf-8"))


def _chem(db_session: Session) -> dict[str, int]:
    book_id = import_book_config(db_session, user_id=1, config=_load("chem2_mobtakeren.json")).book_id
    return node_map(db_session, book_id)


def _create(db_session, node_id: int, **kw):
    params = {"user_id": 1, "node_id": node_id, "count": 5,
              "sequence_from": None, "sequence_to": None, "parity": "any",
              "timed": False, "time_limit_seconds": None, "task_id": None,
              "rng": random.Random(459)}
    params.update(kw)
    return engine.create_session(db_session, **params)


def test_ch1_odd_even_split(db_session: Session) -> None:
    nodes = _chem(db_session)
    odd = _create(db_session, nodes["ch1"], count=25, parity="odd")
    assert len(odd.questions) == 25
    assert all(q.sequence_no % 2 == 1 for q in odd.questions)
    even = _create(db_session, nodes["ch1"], count=24, parity="even")
    assert all(q.sequence_no % 2 == 0 for q in even.questions)

    try:
        _create(db_session, nodes["ch1"], count=26, parity="odd")
        raise AssertionError("expected insufficient_questions")
    except AppError as exc:
        assert exc.code == "insufficient_questions"
        assert exc.details["available"] == 25
        assert exc.details["available_odd"] == 25
        assert exc.details["available_even"] == 24


def test_ch1_full_pool_no_duplicates(db_session: Session) -> None:
    nodes = _chem(db_session)
    view = _create(db_session, nodes["ch1"], count=49)
    ids = [q.question_id for q in view.questions]
    assert len(set(ids)) == 49  # same sequence_no across sets coexist, ids unique
    assert [q.display_order for q in view.questions] == list(range(1, 50))


def test_range_filters_across_test_sets(db_session: Session) -> None:
    nodes = _chem(db_session)
    # check seqs max out at 12, exams at 10, concours-mapped at 13 -> 21..41 empty.
    try:
        _create(db_session, nodes["ch1"], count=1, sequence_from=21, sequence_to=41)
        raise AssertionError("expected insufficient_questions")
    except AppError as exc:
        assert exc.details["available"] == 0
    view = _create(db_session, nodes["ch1"], count=4, sequence_from=11, sequence_to=12)
    assert all(11 <= q.sequence_no <= 12 for q in view.questions)


def test_title_pool_is_checkup_only(db_session: Session) -> None:
    nodes = _chem(db_session)
    # t1 has no children; only check1's 12 questions map to it.
    view = _create(db_session, nodes["ch1_t1"], count=12)
    assert all(q.test_set_title == "چکاپ ۱ فصل ۱" for q in view.questions)


def test_hesab_difficulty_breakdown(db_session: Session) -> None:
    book_id = import_book_config(
        db_session, user_id=1, config=_load("hesab1_olgoo.json")).book_id
    nodes = node_map(db_session, book_id)
    view = _create(db_session, nodes["ch1_les1_sec1"], count=10)
    engine.submit_answers(
        db_session, user_id=1, session_id=view.session.id,
        answers=[AnswerItem(question_id=q.question_id, answer="1",
                            client_attempt_id=uuid.uuid4()) for q in view.questions],
    )
    done = engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    assert done.result is not None
    by_diff = {b.difficulty: b.total for b in done.result.difficulty_breakdown}
    assert by_diff == {"L1": 4, "L2": 3, "L3": 3}


def test_phys_subtree_pooling(db_session: Session) -> None:
    book_id = import_book_config(
        db_session, user_id=1, config=_load("phys2_kheilisabz.json")).book_id
    nodes = node_map(db_session, book_id)
    # ch1 = 3 section drills (36) + ch1 exam (12) = 48.
    view = _create(db_session, nodes["ch1"], count=48)
    assert len(view.questions) == 48
    # A subsection alone has no directly-mapped questions -> insufficient.
    try:
        _create(db_session, nodes["ch1_sec1_sub1"], count=1)
        raise AssertionError("expected insufficient_questions")
    except AppError as exc:
        assert exc.details["available"] == 0
