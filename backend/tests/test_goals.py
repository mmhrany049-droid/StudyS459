"""Integration tests: weekly goals + candidate tasks (spec 02/08/13).

Base pools: t1 = 3q, t2 = 1q (shared check), ch1 = all 3.
Current week in tests = the week containing the finished session (today).
"""

import random
import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.analytics.metrics import normalize_week
from app.errors import AppError
from app.schemas.goals import GoalItemIn, WeekGoalCreate, WeekGoalPatch
from app.schemas.tests import AnswerItem
from app.services import books as book_service
from app.services import goals as service
from app.services import test_engine as engine
from tests.helpers import import_base, node_map


def _create(db_session: Session, node_id: int, **kw):
    params = {"user_id": 1, "node_id": node_id, "count": 3,
              "sequence_from": None, "sequence_to": None, "parity": "any",
              "timed": False, "time_limit_seconds": None, "task_id": None,
              "rng": random.Random(7)}
    params.update(kw)
    return engine.create_session(db_session, **params)


def _answer(db_session: Session, session_id: int, pairs: list[tuple[int, str | None]]):
    engine.submit_answers(
        db_session, user_id=1, session_id=session_id,
        answers=[AnswerItem(question_id=qid, answer=a, client_attempt_id=uuid.uuid4())
                 for qid, a in pairs],
    )


def _finish_mixed(db_session: Session, nodes: dict) -> None:
    """t1 session: drill1 correct, drill2 wrong, check skipped."""
    view = _create(db_session, nodes["t1"])
    by_title_seq = {(q.test_set_title, q.sequence_no): q.question_id for q in view.questions}
    _answer(db_session, view.session.id, [
        (by_title_seq[("تمرین ۱", 1)], "2"),
        (by_title_seq[("تمرین ۱", 2)], "3"),
    ])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)


def _today_week() -> str:
    return normalize_week(date.today())[0].isoformat()


def test_create_and_get_week_goal(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    out = service.create_week_goal(
        db_session, user_id=1, week=_today_week(),
        payload=WeekGoalCreate(items=[
            GoalItemIn(goal_type="count", target_value=50),
            GoalItemIn(goal_type="topic", target_value=1.0, node_id=nodes["t1"]),
        ]),
    )
    assert out.week_start.weekday() == 5  # Saturday
    assert (out.week_end - out.week_start).days == 6
    assert len(out.items) == 2
    assert out.items[0].title == "همه"
    assert out.items[1].title == "عنوان ۱"

    same = service.get_week_goal(db_session, user_id=1, week=date.today().isoformat())
    assert same.id == out.id  # any day resolves to its week

    with pytest.raises(AppError) as e:
        service.create_week_goal(
            db_session, user_id=1, week=_today_week(),
            payload=WeekGoalCreate(items=[GoalItemIn(goal_type="count", target_value=5)]),
        )
    assert e.value.code == "goal_exists"


def test_goal_validations(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    week = _today_week()

    def create(items):
        return service.create_week_goal(
            db_session, user_id=1, week=week, payload=WeekGoalCreate(items=items))

    with pytest.raises(AppError) as e:
        service.create_week_goal(
            db_session, user_id=1, week="not-a-date",
            payload=WeekGoalCreate(items=[GoalItemIn(goal_type="count", target_value=5)]),
        )
    assert e.value.code == "invalid_week"
    with pytest.raises(AppError) as e:
        create([GoalItemIn(goal_type="topic", target_value=1.0)])  # node missing
    assert e.value.code == "invalid_goal_item"
    with pytest.raises(AppError) as e:
        create([GoalItemIn(goal_type="topic", target_value=2.0, node_id=nodes["t1"])])
    assert e.value.code == "invalid_goal_item"
    with pytest.raises(AppError) as e:
        create([GoalItemIn(goal_type="count", target_value=2.5)])
    assert e.value.code == "invalid_goal_item"
    with pytest.raises(AppError) as e:
        create([GoalItemIn(goal_type="count", target_value=5, node_id=999)])
    assert e.value.code == "node_not_found"
    with pytest.raises(AppError) as e:
        create([GoalItemIn(goal_type="count", target_value=5, book_id=999)])
    assert e.value.code == "book_not_found"
    with pytest.raises(AppError):
        service.get_week_goal(db_session, user_id=1, week="2020-01-04")
    # Pydantic: empty items rejected before service.
    with pytest.raises(Exception):
        WeekGoalCreate(items=[])


def test_scope_consistency(db_session: Session) -> None:
    from tests.helpers import base_config

    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    cfg = base_config()
    cfg["book"]["stable_key"] = "other_book"
    other = import_base(db_session, cfg).book_id
    assert other != book_id
    with pytest.raises(AppError) as e:
        service.create_week_goal(
            db_session, user_id=1, week=_today_week(),
            payload=WeekGoalCreate(items=[
                GoalItemIn(goal_type="count", target_value=5,
                           node_id=nodes["t1"], book_id=other),
            ]),
        )
    assert e.value.code == "invalid_goal_item"


def test_count_and_topic_progress(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    _finish_mixed(db_session, nodes)
    out = service.create_week_goal(
        db_session, user_id=1, week=_today_week(),
        payload=WeekGoalCreate(items=[
            GoalItemIn(goal_type="count", target_value=10),
            GoalItemIn(goal_type="topic", target_value=1.0, node_id=nodes["t1"]),
            GoalItemIn(goal_type="topic", target_value=0.5, node_id=nodes["t2"]),
        ]),
    )
    count, t1, t2 = out.items
    assert (count.progress.volume, count.progress.remaining) == (3, 7.0)
    assert count.progress.done is False
    assert (t1.progress.attempted, t1.progress.pool_total) == (3, 3)
    assert t1.progress.coverage == 1.0 and t1.progress.done is True
    assert t1.progress.remaining == 0.0
    # t2 pool = 1 shared check question, seen this week -> coverage 1.0 >= 0.5.
    assert t2.progress.coverage == 1.0 and t2.progress.done is True
    assert out.sessions_in_week == 1
    # No double counting: one mixed session = 3 unique, even across 3 items.
    assert out.week_volume_unique == 3
    assert out.week_attempted_unique == 3


def test_topic_partial_remaining(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    # Only 1 of t1's 3 pool questions seen this week.
    view = _create(db_session, nodes["t1"], count=1, sequence_from=1, sequence_to=1)
    q = view.questions[0]
    key = "2" if q.test_set_title == "تمرین ۱" else "1"
    _answer(db_session, view.session.id, [(q.question_id, key)])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)

    out = service.create_week_goal(
        db_session, user_id=1, week=_today_week(),
        payload=WeekGoalCreate(items=[
            GoalItemIn(goal_type="topic", target_value=1.0, node_id=nodes["t1"]),
        ]),
    )
    p = out.items[0].progress
    assert p.attempted == 1 and p.coverage == pytest.approx(1 / 3)
    assert p.remaining == 2.0  # ceil((1 - 1/3) * 3)
    assert p.done is False


def test_patch_goal(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    out = service.create_week_goal(
        db_session, user_id=1, week=_today_week(),
        payload=WeekGoalCreate(items=[GoalItemIn(goal_type="count", target_value=10)]),
    )
    patched = service.update_goal(
        db_session, user_id=1, goal_id=out.id,
        payload=WeekGoalPatch(
            items=[GoalItemIn(goal_type="topic", target_value=0.5, node_id=nodes["t2"])],
            active=False,
        ),
    )
    assert patched.active is False
    assert len(patched.items) == 1 and patched.items[0].goal_type == "topic"
    active_only = service.update_goal(
        db_session, user_id=1, goal_id=out.id, payload=WeekGoalPatch(active=True))
    assert active_only.active is True and len(active_only.items) == 1
    with pytest.raises(AppError) as e:
        service.update_goal(db_session, user_id=1, goal_id=999,
                            payload=WeekGoalPatch(active=True))
    assert e.value.code == "goal_not_found"


def test_candidates_topic_priority_and_reason(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    _finish_mixed(db_session, nodes)  # t1 done; drill2 wrong + check skipped
    out = service.create_week_goal(
        db_session, user_id=1, week=_today_week(),
        payload=WeekGoalCreate(items=[
            GoalItemIn(goal_type="count", target_value=10),
            GoalItemIn(goal_type="topic", target_value=1.0, node_id=nodes["t2"]),
        ]),
    )
    cands = service.candidate_tasks(db_session, user_id=1, goal_id=out.id, limit=20)
    by_node = {c.node_id: c for c in cands.items}
    # t1: count-goal pick + weakness + review merged into ONE candidate.
    t1 = by_node[nodes["t1"]]
    assert "goal_count" in t1.sources and "review" in t1.sources
    assert "هدف تعداد هفته" in t1.recommendation_reason
    assert "مرور باز" in t1.recommendation_reason
    assert t1.kind == "test"
    # t2 topic goal already met -> no goal_topic source for t2...
    # ...but t2 is weak (shared skipped check) and in scope -> standalone/review.
    assert nodes["t2"] in by_node
    # Priority order: scores descend.
    scores = [c.priority_score for c in cands.items]
    assert scores == sorted(scores, reverse=True)
    # Parity suggestion present everywhere.
    assert all(c.suggested_parity in ("odd", "even", "any") for c in cands.items)


def test_candidates_parity_opposite(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    view = _create(db_session, nodes["t1"], count=1, parity="odd")
    q = view.questions[0]
    key = "2" if q.test_set_title == "تمرین ۱" else "1"
    _answer(db_session, view.session.id, [(q.question_id, key)])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)

    out = service.create_week_goal(
        db_session, user_id=1, week=_today_week(),
        payload=WeekGoalCreate(items=[
            GoalItemIn(goal_type="topic", target_value=1.0, node_id=nodes["t1"]),
        ]),
    )
    cands = service.candidate_tasks(db_session, user_id=1, goal_id=out.id, limit=20)
    t1 = next(c for c in cands.items if c.node_id == nodes["t1"])
    assert t1.suggested_parity == "even"  # opposite of last odd session
    assert "مخالف دفعه قبل" in t1.recommendation_reason
    assert t1.suggested_count == 2  # coverage need


def test_candidates_skip_inactive_books(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    book_service.set_book_active(db_session, user_id=1, book_id=book_id, active=False)
    out = service.create_week_goal(
        db_session, user_id=1, week=_today_week(),
        payload=WeekGoalCreate(items=[
            GoalItemIn(goal_type="topic", target_value=1.0, node_id=nodes["t1"]),
        ]),
    )
    assert out.items[0].progress.pool_total == 3  # progress still computed
    cands = service.candidate_tasks(db_session, user_id=1, goal_id=out.id, limit=20)
    assert cands.items == []  # ...but no candidates from inactive books
