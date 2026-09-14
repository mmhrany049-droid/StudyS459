"""Integration tests: academic records + capacity effects (spec 09)."""

from datetime import date, datetime, time

import pytest
from sqlalchemy.orm import Session

from app.errors import AppError
from app.repositories import books as book_repo
from app.schemas.academic import (
    ClassSessionCreate,
    ExamCreate,
    ExamQuestionIn,
    HomeworkCreate,
    HomeworkPatch,
    ScheduleCreate,
    TaughtLessonCreate,
)
from app.services import academic as service
from app.services import analytics as analytics_service
from app.services import planner as planner_service
from tests.helpers import import_base, node_map


def _subject_id(db_session: Session, book_id: int) -> int:
    book = book_repo.get_book(db_session, book_id)
    assert book is not None
    return book.subject_id


def test_schedules_and_capacity(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    subject_id = _subject_id(db_session, book_id)
    # Saturday (5): 2h school + 1h external. Thursday (3): 1h external.
    service.create_schedule(db_session, user_id=1, payload=ScheduleCreate(
        schedule_type="school", title="مدرسه", day_of_week=5,
        start_time=time(8, 0), end_time=time(10, 0), subject_id=subject_id))
    service.create_schedule(db_session, user_id=1, payload=ScheduleCreate(
        schedule_type="external", title="کلاس زبان", day_of_week=5,
        start_time=time(16, 0), end_time=time(17, 0)))
    service.create_schedule(db_session, user_id=1, payload=ScheduleCreate(
        schedule_type="external", title="باشگاه", day_of_week=3,
        start_time=time(10, 0), end_time=time(11, 0)))

    sat = planner_service.day_plan(db_session, user_id=1, day=date(2026, 9, 12))
    assert sat.scheduled_minutes == 180
    assert sat.capacity_minutes == max(0, 90 - 180) == 0
    assert len(sat.schedules) == 2

    thu = planner_service.day_plan(db_session, user_id=1, day=date(2026, 9, 17))
    assert (thu.scheduled_minutes, thu.capacity_minutes) == (60, 180)

    # «مدرسه نمی‌روم»: school rows drop, external stay.
    from app.schemas.planner import OverrideIn

    planner_service.set_override(
        db_session, user_id=1,
        payload=OverrideIn(date=date(2026, 9, 12), is_school_day=False))
    sat2 = planner_service.day_plan(db_session, user_id=1, day=date(2026, 9, 12))
    assert sat2.scheduled_minutes == 60
    assert sat2.capacity_minutes == 180
    assert [s.schedule_type for s in sat2.schedules] == ["external"]


def test_one_off_schedule(db_session: Session) -> None:
    one = service.create_schedule(db_session, user_id=1, payload=ScheduleCreate(
        schedule_type="external", title="تک‌جلسه", day_of_week=6,
        start_time=time(9, 0), end_time=time(10, 0),
        recurring=False, date=date(2026, 9, 13)))
    assert one.duration_minutes == 60
    sun = planner_service.day_plan(db_session, user_id=1, day=date(2026, 9, 13))
    assert sun.scheduled_minutes == 60
    nxt = planner_service.day_plan(db_session, user_id=1, day=date(2026, 9, 20))
    assert nxt.scheduled_minutes == 0  # no repeat

    with pytest.raises(AppError) as e:  # dow/date mismatch
        service.create_schedule(db_session, user_id=1, payload=ScheduleCreate(
            schedule_type="external", title="x", day_of_week=0,
            start_time=time(9, 0), end_time=time(10, 0),
            recurring=False, date=date(2026, 9, 13)))
    assert e.value.code == "invalid_schedule"
    with pytest.raises(AppError) as e:  # end <= start
        service.create_schedule(db_session, user_id=1, payload=ScheduleCreate(
            schedule_type="school", title="x", day_of_week=5,
            start_time=time(10, 0), end_time=time(10, 0)))
    assert e.value.code == "invalid_schedule"


def test_class_session_and_taught(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    subject_id = _subject_id(db_session, book_id)
    sched = service.create_schedule(db_session, user_id=1, payload=ScheduleCreate(
        schedule_type="school", title="ریاضی", day_of_week=6,
        start_time=time(8, 0), end_time=time(9, 0), subject_id=subject_id))
    cs = service.create_class_session(db_session, user_id=1, payload=ClassSessionCreate(
        schedule_id=sched.id, date=date(2026, 9, 13), subject_id=subject_id,
        attended=True, notes="خوب بود"))
    assert cs.subject_name != ""
    taught = service.create_taught(db_session, user_id=1, payload=TaughtLessonCreate(
        class_session_id=cs.id, subject_id=subject_id, node_id=nodes["t1"],
        taught_at=datetime(2026, 9, 13, 8, 30), duration_minutes=45))
    assert taught.node_title == "عنوان ۱"

    # Taught != learned: analytics untouched.
    out = analytics_service.book_topics(db_session, user_id=1, book_id=book_id)
    t1 = next(t for t in out.topics if t.node_id == nodes["t1"])
    assert (t1.volume, t1.attempted) == (0, 0)


def test_homework_lifecycle_and_task_link(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    subject_id = _subject_id(db_session, book_id)
    hw = service.create_homework(db_session, user_id=1, payload=HomeworkCreate(
        source_type="school", title="تمرین صفحه ۲۰", subject_id=subject_id,
        node_id=nodes["t1"], due_at=datetime(2026, 9, 20, 20, 0),
        estimated_minutes=40, create_task=True))
    assert hw.task_id is not None
    assert hw.status == "pending"

    pending = service.list_homework(db_session, user_id=1, status="pending")
    assert len(pending) == 1

    done = service.patch_homework(
        db_session, user_id=1, homework_id=hw.id, payload=HomeworkPatch(status="done"))
    assert done.status == "done"
    # Linked task auto-completed.
    from app.repositories import planner as planner_repo

    task = planner_repo.latest_task_by_source(db_session, "homework", hw.id)
    assert task is not None and task.status == "completed"

    with pytest.raises(AppError) as e:
        service.patch_homework(db_session, user_id=1, homework_id=999,
                               payload=HomeworkPatch(status="done"))
    assert e.value.code == "homework_not_found"


def test_exams_questions_and_analytics(db_session: Session) -> None:
    book_id = import_base(db_session).book_id
    nodes = node_map(db_session, book_id)
    exam = service.create_exam(db_session, user_id=1, payload=ExamCreate(
        title="آزمون آزمایشی", exam_type="mock", exam_date=date(2026, 9, 10)))
    exam = service.add_exam_questions(db_session, user_id=1, exam_id=exam.id, questions=[
        ExamQuestionIn(sequence_no=1, topic_node_id=nodes["t1"], result="correct"),
        ExamQuestionIn(sequence_no=2, topic_node_id=nodes["t2"], result="wrong"),
        ExamQuestionIn(sequence_no=3, result="unanswered"),  # unmapped
        ExamQuestionIn(sequence_no=4, topic_node_id=nodes["t1"]),  # ungraded
    ])
    assert len(exam.questions) == 4

    # Duplicate-safe: re-post updates, no doubles.
    exam = service.add_exam_questions(db_session, user_id=1, exam_id=exam.id, questions=[
        ExamQuestionIn(sequence_no=2, topic_node_id=nodes["t2"], result="correct"),
    ])
    assert len(exam.questions) == 4
    assert next(q for q in exam.questions if q.sequence_no == 2).result == "correct"

    rep = service.exam_analytics(db_session, user_id=1, exam_id=exam.id)
    assert (rep.correct, rep.wrong, rep.unanswered) == (2, 0, 1)
    assert (rep.ungraded, rep.unmapped) == (1, 1)
    assert len(rep.subjects) == 1  # single subject in base config
    assert rep.subjects[0].correct == 2
    assert "percentage" not in rep.model_dump_json()  # no percent formulas (v1)

    with pytest.raises(AppError) as e:
        service.add_exam_questions(db_session, user_id=1, exam_id=exam.id, questions=[
            ExamQuestionIn(sequence_no=1), ExamQuestionIn(sequence_no=1)])
    assert e.value.code == "invalid_exam_questions"
    with pytest.raises(AppError) as e:
        service.get_exam(db_session, user_id=1, exam_id=999)
    assert e.value.code == "exam_not_found"
