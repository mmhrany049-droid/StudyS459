"""Hardening tests (Phase 8): concurrency race guard (spec 13)."""

import random
import uuid

import pytest
from sqlalchemy.orm import Session

from app.repositories import tests as repo
from app.schemas.tests import AnswerItem
from app.services import test_engine as engine
from tests.helpers import import_base, node_map


def test_concurrent_double_submit_becomes_duplicate(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate the losing side of a concurrent double-submit race.

    The first visibility check misses (the winner hasn't committed yet),
    the insert hits the UNIQUE constraint, and the handler re-reads the
    winner instead of failing: duplicate=True, one row total.
    """
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    view = engine.create_session(
        db_session, user_id=1, node_id=nodes["t1"], count=1,
        sequence_from=None, sequence_to=None, parity="any",
        timed=False, time_limit_seconds=None, task_id=None,
        rng=random.Random(3))
    qid = view.questions[0].question_id
    client_id = uuid.uuid4()

    # The "winner": committed directly, as the racing request would.
    repo.create_attempt(
        db_session, session_id=view.session.id, question_id=qid,
        user_id=1, answer="2", response_time_seconds=None,
        client_attempt_id=str(client_id))
    db_session.commit()

    real_get = repo.get_attempt_by_client_id
    calls = 0

    def flaky_get(db: Session, cid: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None  # race: winner invisible at first check
        return real_get(db, cid)

    monkeypatch.setattr(repo, "get_attempt_by_client_id", flaky_get)
    out = engine.submit_answers(
        db_session, user_id=1, session_id=view.session.id,
        answers=[AnswerItem(question_id=qid, answer="2",
                            client_attempt_id=client_id)])
    assert out.attempts[0].duplicate is True
    assert repo.count_attempts(db_session, view.session.id) == 1
