"""Integration tests: planner tasks, placements, capacity (spec 02/08)."""

import random
import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.errors import AppError
from app.schemas.planner import (
    OverrideIn,
    PlacementIn,
    TaskCreate,
    TaskPatch,
)
from app.schemas.tests import AnswerItem
from app.services import planner as service
from app.services import test_engine as engine
from tests.helpers import import_base, node_map

SATURDAY = date(2026, 9, 12)
THURSDAY = date(2026, 9, 17)


def _task(db_session: Session, **kw) -> int:
    payload = {"task_type": "study", "title": "مطالعه", "estimated_minutes": 30}
    payload.update(kw)
    return service.create_task(
        db_session, user_id=1, payload=TaskCreate(**payload)).id


def test_task_lifecycle(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    tid = service.create_task(
        db_session, user_id=1,
        payload=TaskCreate(task_type="test", title="تست ت۱", node_id=nodes["t1"],
                           question_count=10, parity="odd",
                           source_type="goal", estimated_minutes=20,
                           recommendation_reason="علت"),
    ).id
    t = service.patch_task(
        db_session, user_id=1, task_id=tid, payload=TaskPatch(status="in_progress"))
    assert t.status == "in_progress"
    done = service.complete_task(db_session, user_id=1, task_id=tid)
    assert done.status == "completed" and done.completed_at is not None
    again = service.complete_task(db_session, user_id=1, task_id=tid)  # idempotent
    assert again.status == "completed"
    with pytest.raises(AppError) as e:  # terminal: no reopen
        service.patch_task(db_session, user_id=1, task_id=tid,
                           payload=TaskPatch(status="planned"))
    assert e.value.code == "invalid_transition"


def test_task_validations(db_session: Session) -> None:
    import_base(db_session)
    with pytest.raises(AppError) as e:
        service.create_task(db_session, user_id=1, payload=TaskCreate(
            task_type="test", title="x", question_count=5))  # node missing
    assert e.value.code == "node_not_found"
    with pytest.raises(AppError) as e:
        service.create_task(db_session, user_id=1, payload=TaskCreate(
            task_type="test", title="x", node_id=999, question_count=5))
    assert e.value.code == "node_not_found"
    with pytest.raises(AppError) as e:
        service.create_task(db_session, user_id=1, payload=TaskCreate(
            task_type="study", title="x", priority=2.0))
    assert e.value.code == "invalid_task"
    with pytest.raises(AppError) as e:
        service.create_task(db_session, user_id=1, payload=TaskCreate(
            task_type="study", title="x", source_type="goal", source_id=999))
    assert e.value.code == "invalid_task_source"
    with pytest.raises(AppError) as e:
        service.create_task(db_session, user_id=1, payload=TaskCreate(
            task_type="study", title="x", source_type="homework"))
    assert e.value.code == "task_source_unavailable"
    with pytest.raises(AppError) as e:
        service.patch_task(db_session, user_id=1, task_id=999,
                           payload=TaskPatch(title="y"))
    assert e.value.code == "task_not_found"


def test_day_capacity_and_override(db_session: Session) -> None:
    sat = service.day_plan(db_session, user_id=1, day=SATURDAY)
    assert (sat.is_school_day, sat.capacity_minutes) == (True, 90)
    thu = service.day_plan(db_session, user_id=1, day=THURSDAY)
    assert (thu.is_school_day, thu.capacity_minutes) == (False, 240)

    out = service.set_override(
        db_session, user_id=1,
        payload=OverrideIn(date=SATURDAY, is_school_day=False, reason="مدرسه نمی‌روم"))
    assert out.is_school_day is False
    sat2 = service.day_plan(db_session, user_id=1, day=SATURDAY)
    assert (sat2.is_school_day, sat2.capacity_minutes, sat2.override) == (False, 240, True)


def test_placements_and_over_capacity(db_session: Session) -> None:
    a = _task(db_session, title="A", estimated_minutes=60)
    b = _task(db_session, title="B", estimated_minutes=60)
    days = service.put_placements(db_session, user_id=1, items=[
        PlacementIn(task_id=a, date=SATURDAY, position=1),
        PlacementIn(task_id=b, date=SATURDAY, position=0),
    ])
    assert len(days) == 1
    sat = days[0]
    assert [p.task.title for p in sat.placements] == ["B", "A"]  # position order
    assert sat.workload_minutes == 120 and sat.over_capacity is True  # 120 > 90
    assert {w.task_id for w in sat.workload} == {a, b}

    # Completed tasks leave the workload but stay visible.
    service.complete_task(db_session, user_id=1, task_id=a)
    sat2 = service.day_plan(db_session, user_id=1, day=SATURDAY)
    assert sat2.workload_minutes == 60 and sat2.over_capacity is False
    assert len(sat2.placements) == 2

    # Move B to Thursday and clear Saturday (named date, no rows).
    moved = service.put_placements(db_session, user_id=1, items=[
        PlacementIn(task_id=b, date=THURSDAY, position=0)], extra_dates=[SATURDAY])
    assert [str(d.date) for d in moved] == ["2026-09-12", "2026-09-17"]
    assert service.day_plan(db_session, user_id=1, day=SATURDAY).placements == []
    thu = service.day_plan(db_session, user_id=1, day=THURSDAY)
    assert [p.task.id for p in thu.placements] == [b]

    with pytest.raises(AppError) as e:
        service.put_placements(db_session, user_id=1, items=[])
    assert e.value.code == "empty_placements"
    with pytest.raises(AppError) as e:
        service.put_placements(db_session, user_id=1, items=[
            PlacementIn(task_id=999, date=SATURDAY)])
    assert e.value.code == "task_not_found"


def test_week_plan_and_catch_up(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    overdue = _task(db_session, title="overdue", source_type="manual",
                    due_at=datetime(2020, 1, 1))
    review = _task(db_session, task_type="review", title="rev",
                   node_id=nodes["t1"], source_type="review")
    _task(db_session, title="plain")
    week = service.week_plan(db_session, user_id=1, week="2026-09-12")
    assert (str(week.week_start), str(week.week_end)) == ("2026-09-12", "2026-09-18")
    assert len(week.days) == 7
    assert len(week.unplaced) == 3
    order = [t.id for t in week.catch_up]
    assert order[0] == overdue  # overdue first
    assert order[1] == review  # ...then review
    assert week.catch_up[0].is_overdue is True


def test_session_finish_completes_task(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    tid = service.create_task(
        db_session, user_id=1,
        payload=TaskCreate(task_type="test", title="t", node_id=nodes["t1"],
                           question_count=1, estimated_minutes=5),
    ).id
    view = engine.create_session(
        db_session, user_id=1, node_id=nodes["t1"], count=1,
        sequence_from=None, sequence_to=None, parity="any",
        timed=False, time_limit_seconds=None, task_id=tid, rng=random.Random(3))
    q = view.questions[0]
    engine.submit_answers(
        db_session, user_id=1, session_id=view.session.id,
        answers=[AnswerItem(question_id=q.question_id, answer="2",
                            client_attempt_id=uuid.uuid4())])
    engine.finish_session(db_session, user_id=1, session_id=view.session.id)
    task = service.patch_task(db_session, user_id=1, task_id=tid,
                              payload=TaskPatch(priority=0.9))
    assert task.status == "completed"  # flipped by the engine hook
    assert task.completed_at is not None
    # A day plan shows it without workload.
    today = date.today()
    service.put_placements(db_session, user_id=1, items=[
        PlacementIn(task_id=tid, date=today, position=0)])
    day = service.day_plan(db_session, user_id=1, day=today)
    assert day.workload_minutes == 0 and len(day.placements) == 1
