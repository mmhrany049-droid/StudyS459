"""Integration tests: Test Engine service (temp DB).

Base pool for node t1: drill1 seq{1,2} + check1 seq{1} = 3 questions.
Keys: drill seq1 -> "2", drill seq2 -> "4", check seq1 -> "1".
"""

import random
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.errors import AppError
from app.models import QuestionAttempt, TestSession
from app.repositories import tests as repo
from app.schemas.tests import AnswerItem, CorrectionItem
from app.services import books as book_service
from app.services import test_engine as engine
from tests.helpers import base_config, import_base, node_map


def _mk_session(db_session: Session, node_code: str = "t1", **kw):
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    params = {
        "user_id": 1, "node_id": nodes[node_code], "count": 2,
        "sequence_from": None, "sequence_to": None, "parity": "any",
        "timed": False, "time_limit_seconds": None, "task_id": None,
        "rng": random.Random(459),
    }
    params.update(kw)
    return engine.create_session(db_session, **params)


def _ans(qid: int, answer: str | None, **kw) -> AnswerItem:
    return AnswerItem(
        question_id=qid, answer=answer, response_time_seconds=kw.get("rt"),
        client_attempt_id=uuid.uuid4(),
    )


def test_create_odd_only(db_session: Session) -> None:
    view = _mk_session(db_session, count=2, parity="odd")
    seqs = [q.sequence_no for q in view.questions]
    assert all(s % 2 == 1 for s in seqs)
    assert len({q.question_id for q in view.questions}) == 2
    assert [q.display_order for q in view.questions] == [1, 2]
    assert view.session.status == "in_progress"
    assert view.result is None


def _book_of(db_session: Session, view) -> int:
    """Book id behind a session view (via its first question)."""
    from app.models import Question

    return db_session.execute(
        select(Question.book_id).where(Question.id == view.questions[0].question_id)
    ).scalar_one()


def test_create_even_and_parity_state_updates(db_session: Session) -> None:
    view = _mk_session(db_session, count=1, parity="even")
    assert view.questions[0].sequence_no == 2
    nodes = node_map(db_session, _book_of(db_session, view))
    state = engine.get_parity_state(db_session, user_id=1, node_id=nodes["t1"])
    assert state.last_parity == "even"
    assert state.suggested_parity == "odd"


def test_any_keeps_parity_history(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    engine.create_session(
        db_session, user_id=1, node_id=nodes["t1"], count=2,
        sequence_from=None, sequence_to=None, parity="odd",
        timed=False, time_limit_seconds=None, task_id=None, rng=random.Random(1),
    )
    engine.create_session(
        db_session, user_id=1, node_id=nodes["t1"], count=1,
        sequence_from=None, sequence_to=None, parity="any",
        timed=False, time_limit_seconds=None, task_id=None, rng=random.Random(2),
    )
    state = engine.get_parity_state(db_session, user_id=1, node_id=nodes["t1"])
    assert state.last_parity == "odd"  # "any" did not overwrite
    assert state.suggested_parity == "even"


def test_parity_state_empty_for_fresh_node(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    state = engine.get_parity_state(db_session, user_id=1, node_id=nodes["t1"])
    assert state.last_parity is None and state.suggested_parity is None


def test_insufficient_creates_no_session(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    with pytest.raises(AppError) as e:
        engine.create_session(
            db_session, user_id=1, node_id=nodes["t1"], count=3,
            sequence_from=None, sequence_to=None, parity="odd",
            timed=False, time_limit_seconds=None, task_id=None, rng=random.Random(1),
        )
    assert e.value.code == "insufficient_questions"
    assert e.value.status_code == 422
    assert "فقط 2" in e.value.message  # clear Persian message
    assert e.value.details["available"] == 2
    assert e.value.details["available_odd"] == 2
    assert e.value.details["available_even"] == 1  # range-level, pre-parity
    assert db_session.execute(select(func.count()).select_from(TestSession)).scalar() == 0


def test_range_filtering(db_session: Session) -> None:
    view = _mk_session(db_session, count=1, sequence_from=2, sequence_to=2)
    assert view.questions[0].sequence_no == 2
    view = _mk_session(db_session, count=1, sequence_from=2, sequence_to=None)
    assert view.questions[0].sequence_no == 2
    book_id = import_base(db_session, config=_other_book()).book_id
    nodes = node_map(db_session, book_id)
    with pytest.raises(AppError) as e:
        engine.create_session(
            db_session, user_id=1, node_id=nodes["t1"], count=1,
            sequence_from=5, sequence_to=9, parity="any",
            timed=False, time_limit_seconds=None, task_id=None,
        )
    assert e.value.details["available"] == 0


def _other_book() -> dict:
    cfg = base_config()
    cfg["book"]["stable_key"] = "demo_book_2"
    return cfg


def test_descendant_pooling(db_session: Session) -> None:
    view = _mk_session(db_session, node_code="ch1", count=3)  # drill(2) + check(1)
    assert len(view.questions) == 3


def test_inactive_book_rejected(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    book_service.set_book_active(db_session, user_id=1, book_id=book_id, active=False)
    with pytest.raises(AppError) as e:
        engine.create_session(
            db_session, user_id=1, node_id=nodes["t1"], count=1,
            sequence_from=None, sequence_to=None, parity="any",
            timed=False, time_limit_seconds=None, task_id=None,
        )
    assert e.value.code == "book_inactive"
    assert e.value.status_code == 409


def test_create_validations(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    base = {"user_id": 1, "node_id": nodes["t1"], "count": 1,
            "sequence_from": None, "sequence_to": None, "parity": "any",
            "timed": False, "time_limit_seconds": None, "task_id": None}
    with pytest.raises(AppError) as e:
        engine.create_session(db_session, **{**base, "sequence_from": 5, "sequence_to": 2})
    assert e.value.code == "invalid_range"
    with pytest.raises(AppError) as e:
        engine.create_session(db_session, **{**base, "timed": True})
    assert e.value.code == "invalid_timed_config"
    with pytest.raises(AppError) as e:
        engine.create_session(db_session, **{**base, "time_limit_seconds": 60})
    assert e.value.code == "invalid_timed_config"
    with pytest.raises(AppError) as e:
        engine.create_session(db_session, **{**base, "node_id": 999})
    assert e.value.code == "node_not_found"


def _finish_111(db_session: Session):
    """Session with 1 correct + 1 wrong + 1 unanswered. Returns (view, session_id)."""
    view = _mk_session(db_session, count=3)
    # drill seq1 key "2" (correct), drill seq2 -> wrong answer, check seq1 skipped
    drills = [q for q in view.questions if q.test_set_title == "تمرین ۱"]
    seq1 = next(q for q in drills if q.sequence_no == 1)
    seq2 = next(q for q in drills if q.sequence_no == 2)
    engine.submit_answers(
        db_session, user_id=1, session_id=view.session.id,
        answers=[_ans(seq1.question_id, "2"), _ans(seq2.question_id, "3", rt=30)],
    )
    return engine.finish_session(db_session, user_id=1, session_id=view.session.id)


def test_finish_scoring_and_result(db_session: Session) -> None:
    done = _finish_111(db_session)
    assert done.session.status == "completed"
    assert done.session.ended_at is not None
    r = done.result
    assert r is not None and (r.correct, r.wrong, r.unanswered, r.pending) == (1, 1, 1, 0)
    assert r.accuracy == 0.5
    assert r.duration_seconds is not None and r.duration_seconds >= 0
    assert r.average_response_time_seconds == 30.0
    assert r.parity == "any"
    assert len(r.topic_breakdown) >= 1
    assert sum(t.total for t in r.topic_breakdown) >= 3  # multi-topic counts twice
    assert done.questions[0].result in ("correct", "wrong", None)


def test_append_only_latest_wins(db_session: Session) -> None:
    view = _mk_session(db_session, count=1)
    qid = view.questions[0].question_id
    engine.submit_answers(db_session, user_id=1, session_id=view.session.id,
                          answers=[_ans(qid, "WRONG")])
    engine.submit_answers(db_session, user_id=1, session_id=view.session.id,
                          answers=[_ans(qid, "2")])
    assert repo.count_attempts(db_session, view.session.id) == 2  # no overwrite
    done = engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    # latest answer decides (qid may be drill-seq1 key"2" or other; assert consistency)
    latest = repo.latest_attempts_by_question(db_session, view.session.id)[qid]
    assert latest.answer == "2"
    assert done.result is not None


def test_retract_to_unanswered(db_session: Session) -> None:
    view = _mk_session(db_session, count=1)
    qid = view.questions[0].question_id
    engine.submit_answers(db_session, user_id=1, session_id=view.session.id,
                          answers=[_ans(qid, "2")])
    engine.submit_answers(db_session, user_id=1, session_id=view.session.id,
                          answers=[_ans(qid, None)])
    assert repo.count_attempts(db_session, view.session.id) == 2  # retract = new row
    done = engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    assert done.result is not None and done.result.unanswered == 1


def test_double_submit_same_id_no_duplicate(db_session: Session) -> None:
    view = _mk_session(db_session, count=1)
    qid = view.questions[0].question_id
    cid = uuid.uuid4()
    item = AnswerItem(question_id=qid, answer="2", client_attempt_id=cid)
    first = engine.submit_answers(db_session, user_id=1, session_id=view.session.id, answers=[item])
    second = engine.submit_answers(db_session, user_id=1, session_id=view.session.id, answers=[item])
    assert first.attempts[0].duplicate is False
    assert second.attempts[0].duplicate is True
    assert second.attempts[0].attempt_id == first.attempts[0].attempt_id
    assert repo.count_attempts(db_session, view.session.id) == 1


def test_finish_idempotent(db_session: Session) -> None:
    done = _finish_111(db_session)
    before = repo.count_attempts(db_session, done.session.id)
    again = engine.finish_session(db_session, user_id=1, session_id=done.session.id)
    assert again.result == done.result
    assert again.session.ended_at == done.session.ended_at
    assert repo.count_attempts(db_session, done.session.id) == before


def test_answer_after_finish_rejected(db_session: Session) -> None:
    done = _finish_111(db_session)
    qid = done.questions[0].question_id
    with pytest.raises(AppError) as e:
        engine.submit_answers(db_session, user_id=1, session_id=done.session.id,
                              answers=[_ans(qid, "1")])
    assert e.value.code == "session_not_in_progress"


def test_answer_foreign_question_rejected(db_session: Session) -> None:
    view = _mk_session(db_session, count=1)
    with pytest.raises(AppError) as e:
        engine.submit_answers(db_session, user_id=1, session_id=view.session.id,
                              answers=[_ans(999999, "1")])
    assert e.value.code == "question_not_in_session"


def test_timeout_is_deterministic(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    view = engine.create_session(
        db_session, user_id=1, node_id=nodes["t1"], count=1,
        sequence_from=None, sequence_to=None, parity="any",
        timed=True, time_limit_seconds=3600, task_id=None, rng=random.Random(1),
    )
    session = repo.get_session(db_session, view.session.id)
    assert session is not None
    session.started_at = utcnow() - timedelta(hours=2)  # time travel
    db_session.commit()

    # Read-only GET reports expiry but does NOT mutate.
    peek = engine.get_session_view(db_session, user_id=1, session_id=view.session.id)
    assert peek.session.expired is True
    assert peek.session.remaining_seconds == 0
    assert peek.session.status == "in_progress"

    # Write path auto-completes with ended_at == deadline EXACTLY.
    with pytest.raises(AppError) as e:
        engine.submit_answers(db_session, user_id=1, session_id=view.session.id,
                              answers=[_ans(view.questions[0].question_id, "1")])
    assert e.value.code == "session_expired"
    after = engine.get_session_view(db_session, user_id=1, session_id=view.session.id)
    assert after.session.status == "completed"
    assert after.session.ended_at == after.session.started_at + timedelta(seconds=3600)
    assert after.result is not None and after.result.duration_seconds == 3600


def test_finish_after_expiry_uses_deadline(db_session: Session) -> None:
    view = _mk_session(db_session, count=1, timed=True, time_limit_seconds=120)
    session = repo.get_session(db_session, view.session.id)
    assert session is not None
    session.started_at = utcnow() - timedelta(hours=1)
    db_session.commit()
    done = engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    assert done.result is not None and done.result.duration_seconds == 120


def test_pending_correction_flow(db_session: Session) -> None:
    cfg = base_config()
    cfg["questions"][0]["answer_key"] = None  # drill seq1 keyless
    book_id = import_base(db_session, cfg).book_id
    nodes = node_map(db_session, book_id)
    view = engine.create_session(
        db_session, user_id=1, node_id=nodes["t1"], count=1,
        sequence_from=1, sequence_to=1, parity="any",
        timed=False, time_limit_seconds=None, task_id=None, rng=random.Random(1),
    )
    q = view.questions[0]
    assert q.has_answer_key is False
    engine.submit_answers(db_session, user_id=1, session_id=view.session.id,
                          answers=[_ans(q.question_id, "3")])
    done = engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    assert done.session.status == "pending_correction"
    assert done.result is not None and done.result.pending == 1
    assert done.result.accuracy is None  # unknown, never guessed

    out = engine.submit_corrections(
        db_session, user_id=1, session_id=view.session.id,
        corrections=[CorrectionItem(question_id=q.question_id, result="correct")],
    )
    assert out.status == "completed" and out.pending_remaining == 0
    final = engine.get_session_view(db_session, user_id=1, session_id=view.session.id)
    assert final.result is not None and final.result.correct == 1


def test_correction_guards(db_session: Session) -> None:
    done = _finish_111(db_session)  # completed, no pendings
    with pytest.raises(AppError) as e:
        engine.submit_corrections(
            db_session, user_id=1, session_id=done.session.id,
            corrections=[CorrectionItem(question_id=done.questions[0].question_id, result="correct")],
        )
    assert e.value.code == "session_completed"

    view = _mk_session(db_session, count=1)  # still in progress
    with pytest.raises(AppError) as e:
        engine.submit_corrections(
            db_session, user_id=1, session_id=view.session.id,
            corrections=[CorrectionItem(question_id=view.questions[0].question_id, result="wrong")],
        )
    assert e.value.code == "session_in_progress"


def test_ownership_enforced(db_session: Session) -> None:
    from app.models import User

    view = _mk_session(db_session, count=1)
    db_session.add(User(id=2, username="other", display_name="دیگر",
                        grade=11, track="mathematics", timezone="Asia/Tehran"))
    db_session.commit()
    with pytest.raises(AppError) as e:
        engine.get_session_view(db_session, user_id=2, session_id=view.session.id)
    assert e.value.code == "session_not_found"


def test_response_time_never_makes_timed(db_session: Session) -> None:
    view = _mk_session(db_session, count=1)
    engine.submit_answers(db_session, user_id=1, session_id=view.session.id,
                          answers=[_ans(view.questions[0].question_id, "2", rt=999)])
    done = engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    assert done.session.timed is False
    assert done.session.time_limit_seconds is None
    assert done.result is not None and done.result.timed is False
