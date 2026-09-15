"""Integration tests: points + streak + badges (spec 10)."""

import random
import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.analytics.metrics import normalize_week
from app.repositories import rewards as reward_repo
from app.schemas.goals import GoalItemIn, WeekGoalCreate
from app.schemas.planner import PlacementIn, TaskCreate
from app.schemas.tests import AnswerItem
from app.services import goals as goals_service
from app.services import planner as planner_service
from app.services import rewards as service
from app.services import student_state
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


def _setup(db_session: Session) -> dict:
    book_id = import_base(db_session).book_id
    return {"book_id": book_id, "nodes": node_map(db_session, book_id)}


def test_session_points_and_recovery(db_session: Session) -> None:
    ctx = _setup(db_session)
    nodes = ctx["nodes"]
    # Session 1: drill1 wrong, drill2 correct, check skipped.
    view = _create(db_session, nodes["t1"])
    by_title_seq = {(q.test_set_title, q.sequence_no): q.question_id for q in view.questions}
    dq1 = by_title_seq[("تمرین ۱", 1)]
    dq2 = by_title_seq[("تمرین ۱", 2)]
    _answer(db_session, view.session.id, [(dq1, "9"), (dq2, "4")])
    fin1 = engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    assert fin1.result is not None and fin1.result.points_earned == 2  # 1 correct

    # Session 2 (t2 pool = check only): check correct after being skipped.
    s2 = _create(db_session, nodes["t2"], count=1)
    cq = s2.questions[0].question_id
    _answer(db_session, s2.session.id, [(cq, "1")])
    fin2 = engine.finish_session(db_session, user_id=1, session_id=s2.session.id)
    assert fin2.result is not None
    assert fin2.result.points_earned == 3  # 2 correct + 1 recovery

    assert reward_repo.total_points(db_session, 1) == 5


def test_streak_counts_pure() -> None:
    mon = date(2026, 9, 14)
    days = {mon - timedelta(days=i) for i in range(3)}
    assert service.streak_counts(days, mon) == (3, 3)
    # Today open: streak alive via yesterday.
    assert service.streak_counts({mon - timedelta(days=1)}, mon) == (1, 1)
    # A gap resets current but keeps longest.
    assert service.streak_counts({mon - timedelta(days=5), mon}, mon) == (1, 1)
    assert service.streak_counts(set(), mon) == (0, 0)


def test_study_task_points_and_streak_days(db_session: Session) -> None:
    _setup(db_session)
    t1 = planner_service.create_task(
        db_session, user_id=1,
        payload=TaskCreate(task_type="study", title="s1")).id
    done = planner_service.complete_task(db_session, user_id=1, task_id=t1)
    assert done.points_earned == 5 + 5  # study + first streak day

    # Second study task same day: +5, no new streak day.
    t2 = planner_service.create_task(
        db_session, user_id=1,
        payload=TaskCreate(task_type="study", title="s2")).id
    done2 = planner_service.complete_task(db_session, user_id=1, task_id=t2)
    assert done2.points_earned == 5

    # Test tasks earn no flat points.
    ctx_nodes = node_map(db_session, import_base(db_session).book_id)
    t3 = planner_service.create_task(
        db_session, user_id=1, payload=TaskCreate(
            task_type="test", title="t", node_id=ctx_nodes["t1"], question_count=1)).id
    done3 = planner_service.complete_task(db_session, user_id=1, task_id=t3)
    assert done3.points_earned == 0

    summary = service.summary(db_session, user_id=1)
    assert summary.total_points == 15
    assert (summary.current_streak, summary.longest_streak) == (1, 1)


def test_streak_across_days_and_reset(db_session: Session) -> None:
    _setup(db_session)
    from app.repositories import planner as planner_repo

    base = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    for i, title in [(3, "d-3"), (2, "d-2"), (0, "today")]:
        tid = planner_service.create_task(
            db_session, user_id=1, payload=TaskCreate(task_type="study", title=title)).id
        task = planner_repo.get_task(db_session, 1, tid)
        assert task is not None
        task.status = "completed"
        task.completed_at = base - timedelta(days=i)
        db_session.commit()
    summary = service.summary(db_session, user_id=1)
    # Gap on d-1: current streak is 1 (today), longest stays 2.
    assert (summary.current_streak, summary.longest_streak) == (1, 2)


def test_daily_goal_award_once(db_session: Session) -> None:
    _setup(db_session)
    day = date(2026, 9, 12)
    a = planner_service.create_task(
        db_session, user_id=1, payload=TaskCreate(task_type="review", title="a")).id
    b = planner_service.create_task(
        db_session, user_id=1, payload=TaskCreate(task_type="review", title="b")).id
    planner_service.put_placements(db_session, user_id=1, items=[
        PlacementIn(task_id=a, date=day, position=0),
        PlacementIn(task_id=b, date=day, position=1),
    ])
    first = planner_service.complete_task(db_session, user_id=1, task_id=a)
    assert first.points_earned == 0  # day still open
    second = planner_service.complete_task(db_session, user_id=1, task_id=b)
    assert second.points_earned == 15  # daily goal
    again = planner_service.complete_task(db_session, user_id=1, task_id=b)
    assert again.points_earned is None  # idempotent


def test_weekly_goal_award_and_topic_badge(db_session: Session) -> None:
    ctx = _setup(db_session)
    nodes = ctx["nodes"]
    week = normalize_week(date.today())[0].isoformat()
    goals_service.create_week_goal(
        db_session, user_id=1, week=week,
        payload=WeekGoalCreate(items=[
            GoalItemIn(goal_type="count", target_value=3),
            GoalItemIn(goal_type="topic", target_value=1.0, node_id=nodes["t1"]),
        ]),
    )
    view = _create(db_session, nodes["t1"])
    by_title_seq = {(q.test_set_title, q.sequence_no): q.question_id for q in view.questions}
    _answer(db_session, view.session.id, [
        (by_title_seq[("تمرین ۱", 1)], "2"),
        (by_title_seq[("تمرین ۱", 2)], "4"),
        (by_title_seq[("چکاپ ۱", 1)], "1"),
    ])
    fin = engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    assert fin.result is not None
    # 3 correct x2 = 6 session points + 50 weekly-goal bonus, all surfaced.
    assert fin.result.points_earned == 56
    assert reward_repo.total_points(db_session, 1) == 56
    codes = {b.code for b in service.list_badges(db_session, user_id=1) if b.earned}
    assert "weekly_topic_goal" in codes


def test_volume_and_accuracy_badges(db_session: Session) -> None:
    ctx = _setup(db_session)
    nodes = ctx["nodes"]
    # 7 sessions x 3 correct = 21 volume on t1 (accuracy 100%).
    for i in range(7):
        view = _create(db_session, nodes["t1"], rng=random.Random(i))
        by_title_seq = {(q.test_set_title, q.sequence_no): q.question_id for q in view.questions}
        _answer(db_session, view.session.id, [
            (by_title_seq[("تمرین ۱", 1)], "2"),
            (by_title_seq[("تمرین ۱", 2)], "4"),
            (by_title_seq[("چکاپ ۱", 1)], "1"),
        ])
        engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    codes = {b.code for b in service.list_badges(db_session, user_id=1) if b.earned}
    assert {"first_20_tests", "chapter_coverage_80", "accuracy_75"} <= codes
    summary = service.summary(db_session, user_id=1)
    assert summary.badge_count == 3
    assert summary.total_points == 7 * 6  # 3 correct x2, no recoveries


def test_state_signals(db_session: Session) -> None:
    ctx = _setup(db_session)
    nodes = ctx["nodes"]
    view = _create(db_session, nodes["t1"])
    by_title_seq = {(q.test_set_title, q.sequence_no): q.question_id for q in view.questions}
    _answer(db_session, view.session.id, [(by_title_seq[("تمرین ۱", 2)], "3")])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    planner_service.create_task(
        db_session, user_id=1, payload=TaskCreate(task_type="study", title="open"))

    signals = student_state.get_signals(db_session, user_id=1)
    assert signals.pending_reviews == 3  # wrong drill2 + untouched drill1/check
    assert signals.open_tasks == 1
    assert signals.overdue_tasks == 0
    assert nodes["t1"] in signals.weak_scores
    assert signals.review_by_node[nodes["t1"]]["high"] == 1
