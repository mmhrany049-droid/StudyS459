"""Integration tests: analytics service + review population (spec 07).

Base pools: t1 = drill(2q) + check(1q); t2 = check(1q); ch1 = all 3.
Keys: drill seq1 -> "2", drill seq2 -> "4", check seq1 -> "1".
"""

import random
import uuid
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.errors import AppError
from app.repositories import analytics as repo
from app.schemas.tests import AnswerItem
from app.services import analytics as service
from app.services import books as book_service
from app.services import test_engine as engine
from tests.helpers import base_config, import_base, node_map


def _create(db_session: Session, node_id: int, **kw):
    params = {"user_id": 1, "node_id": node_id, "count": 3,
              "sequence_from": None, "sequence_to": None, "parity": "any",
              "timed": False, "time_limit_seconds": None, "task_id": None,
              "rng": random.Random(11)}
    params.update(kw)
    return engine.create_session(db_session, **params)


def _answer(db_session: Session, session_id: int, pairs: list[tuple[int, str | None]]):
    engine.submit_answers(
        db_session, user_id=1, session_id=session_id,
        answers=[AnswerItem(question_id=qid, answer=a, client_attempt_id=uuid.uuid4())
                 for qid, a in pairs],
    )


def _setup_mixed(db_session: Session) -> dict:
    """Session: drill-seq1 correct, drill-seq2 wrong, check skipped."""
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    view = _create(db_session, nodes["t1"])
    by_title_seq = {(q.test_set_title, q.sequence_no): q.question_id for q in view.questions}
    dq1 = by_title_seq[("تمرین ۱", 1)]
    dq2 = by_title_seq[("تمرین ۱", 2)]
    _answer(db_session, view.session.id, [(dq1, "2"), (dq2, "3")])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    return {"book_id": book_id, "nodes": nodes, "dq1": dq1, "dq2": dq2}


def test_topic_table_metrics(db_session: Session) -> None:
    ctx = _setup_mixed(db_session)
    out = service.book_topics(db_session, user_id=1, book_id=ctx["book_id"])
    rows = {r.code: r for r in out.topics}
    t1, t2, ch1 = rows["t1"], rows["t2"], rows["ch1"]

    assert (t1.total, t1.attempted, t1.volume) == (3, 3, 3)
    assert (t1.correct, t1.wrong, t1.unanswered, t1.pending) == (1, 1, 1, 0)
    assert t1.coverage == 1.0 and t1.accuracy == 0.5
    assert t1.is_leaf is True and t1.last_activity is not None
    assert "فصل ۱" in t1.path and t1.depth == 1

    # t2 shares the skipped check question only.
    assert (t2.total, t2.attempted, t2.volume) == (1, 1, 1)
    assert t2.unanswered == 1 and t2.accuracy is None

    assert (ch1.total, ch1.volume) == (3, 3)
    assert ch1.is_leaf is False


def _correct_key(question) -> str:
    """Correct answer for whatever seq-1 question was sampled (drill or check)."""
    return "2" if question.test_set_title == "تمرین ۱" else "1"


def test_coverage_is_not_accuracy(db_session: Session) -> None:
    """Low coverage + high accuracy must stay distinguishable (rule 10)."""
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    view = _create(db_session, nodes["t1"], count=1, sequence_from=1, sequence_to=1)
    q = view.questions[0]
    _answer(db_session, view.session.id, [(q.question_id, _correct_key(q))])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)

    out = service.book_topics(db_session, user_id=1, book_id=book_id)
    t1 = next(r for r in out.topics if r.code == "t1")
    assert t1.attempted == 1 and t1.total == 3
    assert t1.coverage == pytest.approx(1 / 3)
    assert t1.accuracy == 1.0  # perfect on the seen part


def test_in_progress_excluded(db_session: Session) -> None:
    ctx = _setup_mixed(db_session)
    before = service.overview(db_session, user_id=1)
    _create(db_session, ctx["nodes"]["t1"], count=1)  # unfinished session
    after = service.overview(db_session, user_id=1)
    assert after.sessions_total == before.sessions_total + 1
    assert after.sessions_completed == before.sessions_completed
    assert after.volume == before.volume
    assert after.coverage == before.coverage


def test_overview_and_inactive_scope(db_session: Session) -> None:
    ctx = _setup_mixed(db_session)
    out = service.overview(db_session, user_id=1)
    assert (out.sessions_total, out.sessions_completed) == (1, 1)
    assert (out.volume, out.correct, out.wrong, out.unanswered) == (3, 1, 1, 1)
    assert out.accuracy == 0.5 and out.coverage == 1.0
    assert len(out.books) == 1 and out.books[0].active is True

    book_service.set_book_active(db_session, user_id=1, book_id=ctx["book_id"], active=False)
    out = service.overview(db_session, user_id=1)
    assert out.books[0].active is False
    assert out.books[0].volume == 3  # history stays visible
    assert out.volume == 0 and out.coverage is None  # ...but out of global scope


def test_node_drilldown(db_session: Session) -> None:
    ctx = _setup_mixed(db_session)
    out = service.node_progress(db_session, user_id=1, node_id=ctx["nodes"]["ch1"])
    assert out.node.code == "ch1"
    assert [c.code for c in out.children] == ["t1", "t2"]
    assert out.children[0].volume == 3
    with pytest.raises(AppError) as e:
        service.node_progress(db_session, user_id=1, node_id=999)
    assert e.value.code == "node_not_found"


def test_question_history(db_session: Session) -> None:
    ctx = _setup_mixed(db_session)  # check question presented but skipped (no rows)
    # t2 pool = check only -> deterministic target. Correct, then wrong x2.
    s2 = _create(db_session, ctx["nodes"]["t2"], count=1)
    check_qid = s2.questions[0].question_id
    _answer(db_session, s2.session.id, [(check_qid, "1")])
    engine.finish_session(db_session, user_id=1, session_id=s2.session.id)
    s3 = _create(db_session, ctx["nodes"]["t2"], count=1)
    _answer(db_session, s3.session.id, [(check_qid, "9")])
    _answer(db_session, s3.session.id, [(check_qid, "8")])  # changed mind
    engine.finish_session(db_session, user_id=1, session_id=s3.session.id)

    h = service.question_history(db_session, user_id=1, question_id=check_qid)
    assert h.sessions_count == 2  # sessions with >= 1 row (skipped one excluded)
    assert h.attempt_count == 3  # every row kept (append-only)
    assert (h.correct, h.wrong) == (1, 1)  # finals per session
    assert h.last_answer == "8" and h.last_result == "wrong"
    assert h.first_seen_at is not None and h.last_seen_at >= h.first_seen_at
    assert sorted(t.node_id for t in h.topics) == sorted(
        [ctx["nodes"]["t1"], ctx["nodes"]["t2"]])
    with pytest.raises(AppError) as e:
        service.question_history(db_session, user_id=1, question_id=999)
    assert e.value.code == "question_not_found"


def test_trends_day_and_week(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    # Two finished sessions on Sat 2026-09-12 and Sun 2026-09-13 (Tehran days).
    for day, mode in [(12, "correct"), (13, "wrong")]:
        view = _create(db_session, nodes["t1"], count=1, sequence_from=1, sequence_to=1)
        s = engine.get_session_view(db_session, user_id=1, session_id=view.session.id).session
        from app.repositories import tests as test_repo

        row = test_repo.get_session(db_session, s.id)
        assert row is not None
        row.started_at = datetime(2026, 9, day, 12, 0, 0)  # 15:30 Tehran, same day
        row.ended_at = datetime(2026, 9, day, 12, 5, 0)
        db_session.commit()
        q = view.questions[0]
        ans = _correct_key(q) if mode == "correct" else "9"
        _answer(db_session, view.session.id, [(q.question_id, ans)])
        engine.finish_session(db_session, user_id=1, session_id=view.session.id)

    out = service.trends(db_session, user_id=1, days=3, group_by="day",
                         today=datetime(2026, 9, 14, 12, 0, 0))
    assert [str(p.period_start) for p in out.points] == ["2026-09-12", "2026-09-13", "2026-09-14"]
    assert [(p.sessions, p.volume) for p in out.points] == [(1, 1), (1, 1), (0, 0)]
    assert [p.accuracy for p in out.points] == [1.0, 0.0, None]

    weekly = service.trends(db_session, user_id=1, days=3, group_by="week",
                            today=datetime(2026, 9, 14, 12, 0, 0))
    assert len(weekly.points) == 1  # Sat 12 + Sun 13 + Mon 14 share one Iranian week
    assert str(weekly.points[0].period_start) == "2026-09-12"
    assert (weekly.points[0].sessions, weekly.points[0].volume) == (2, 2)
    assert weekly.points[0].accuracy == 0.5

    with pytest.raises(AppError):
        service.trends(db_session, user_id=1, days=3, group_by="month")
    with pytest.raises(AppError):
        service.trends(db_session, user_id=1, days=400, group_by="day")


def test_weaknesses_ranking(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    view = _create(db_session, nodes["t1"], count=3)
    by_title_seq = {(q.test_set_title, q.sequence_no): q.question_id for q in view.questions}
    _answer(db_session, view.session.id, [
        (by_title_seq[("تمرین ۱", 1)], "2"),   # correct
        (by_title_seq[("تمرین ۱", 2)], "3"),   # wrong
        (by_title_seq[("چکاپ ۱", 1)], "9"),    # wrong (shared with t2)
    ])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)

    out = service.weaknesses(db_session, user_id=1, limit=10, min_volume=1)
    assert out.items[0].title == "عنوان ۲"  # score 1.0 (single shared wrong)
    assert out.items[0].score == 1.0
    assert out.items[0].is_leaf is True
    scores = [i.score for i in out.items]
    assert scores == sorted(scores, reverse=True)

    strict = service.weaknesses(db_session, user_id=1, limit=10, min_volume=3)
    assert all(i.volume >= 3 for i in strict.items)
    assert all(i.node_id != nodes["t2"] for i in strict.items)  # t2 volume is 1


def test_review_population_and_dedupe(db_session: Session) -> None:
    ctx = _setup_mixed(db_session)  # 1 wrong + 1 unanswered
    rows = repo.pending_reviews(db_session, 1)
    assert len(rows) == 2
    assert {(r.reason, r.priority) for r in rows} == {("wrong", "high"), ("unanswered", "normal")}
    assert all(r.scheduled_for is None and r.status == "pending" for r in rows)

    # Same failures again -> no duplicates.
    view = _create(db_session, ctx["nodes"]["t1"], count=3)
    by_title_seq = {(q.test_set_title, q.sequence_no): q.question_id for q in view.questions}
    _answer(db_session, view.session.id, [
        (by_title_seq[("تمرین ۱", 2)], "3"),
    ])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    # +1 only: drill-seq1 newly unanswered; drill-seq2/check deduped.
    assert len(repo.pending_reviews(db_session, 1)) == 3


def test_review_from_correction(db_session: Session) -> None:
    cfg = base_config()
    cfg["questions"][0]["answer_key"] = None
    # Drill-only: seq-1 pool = exactly the keyless question (deterministic).
    cfg["test_sets"] = [ts for ts in cfg["test_sets"] if ts["key"] == "drill1"]
    cfg["questions"] = [q for q in cfg["questions"] if q["test_set"] == "drill1"]
    book_id = import_base(db_session, cfg).book_id
    nodes = node_map(db_session, book_id)
    view = _create(db_session, nodes["t1"], count=1, sequence_from=1, sequence_to=1)
    qid = view.questions[0].question_id
    _answer(db_session, view.session.id, [(qid, "3")])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    assert repo.pending_reviews(db_session, 1) == []  # pending != wrong

    from app.schemas.tests import CorrectionItem

    engine.submit_corrections(
        db_session, user_id=1, session_id=view.session.id,
        corrections=[CorrectionItem(question_id=qid, result="wrong")],
    )
    rows = repo.pending_reviews(db_session, 1)
    assert len(rows) == 1 and rows[0].reason == "wrong"
