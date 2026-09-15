"""Academic records: schedules, sessions, taught, homework, exams (spec 09).

Invariants:
- Taught lessons never feed analytics (taught != learned).
- Exam analytics are count-based only (open decisions #1/#6).
- Schedules shrink planner capacity (school rows only on school days).
"""

from datetime import date

from sqlalchemy.orm import Session

from app.db import utcnow
from app.errors import AppError
from app.models import Homework, Schedule
from app.repositories import academic as repo
from app.repositories import books as book_repo
from app.schemas.academic import (
    ClassSessionCreate,
    ClassSessionOut,
    ExamAnalyticsOut,
    ExamCreate,
    ExamOut,
    ExamQuestionIn,
    ExamQuestionOut,
    ExamSubjectRowOut,
    HomeworkCreate,
    HomeworkOut,
    HomeworkPatch,
    ScheduleCreate,
    ScheduleOut,
    TaughtLessonCreate,
    TaughtLessonOut,
)
from app.services.users import get_or_create_single_user


def _minutes(start, end) -> int:
    return int((end.hour * 60 + end.minute) - (start.hour * 60 + start.minute))


def _schedule_out(row: Schedule) -> ScheduleOut:
    return ScheduleOut(
        id=row.id, schedule_type=row.schedule_type,  # type: ignore[arg-type]
        title=row.title, day_of_week=row.day_of_week,
        start_time=row.start_time, end_time=row.end_time,
        recurring=row.recurring, date=row.date,
        subject_id=row.subject_id, node_id=row.node_id, source=row.source,
        duration_minutes=_minutes(row.start_time, row.end_time),
    )


def _subject_name(db: Session, subject_id: int) -> str:
    subject = book_repo.get_subject(db, subject_id)
    return subject.name if subject else f"درس {subject_id}"


def _node_title(db: Session, node_id: int | None) -> str | None:
    if node_id is None:
        return None
    node = book_repo.get_node(db, node_id)
    return node.title if node else None


# -- schedules -----------------------------------------------------------

def list_schedules(db: Session, *, user_id: int) -> list[ScheduleOut]:
    user = get_or_create_single_user(db, user_id)
    return [_schedule_out(r) for r in repo.list_schedules(db, user.id)]


def create_schedule(db: Session, *, user_id: int, payload: ScheduleCreate) -> ScheduleOut:
    user = get_or_create_single_user(db, user_id)
    if payload.end_time <= payload.start_time:
        raise AppError("invalid_schedule", "ساعت پایان باید بعد از شروع باشد.", status_code=422)
    if payload.recurring and payload.date is not None:
        raise AppError("invalid_schedule", "برنامه تکرارشونده تاریخ ندارد.", status_code=422)
    if not payload.recurring:
        if payload.date is None:
            raise AppError("invalid_schedule", "برنامه تک‌جلسه‌ای نیاز به تاریخ دارد.", status_code=422)
        if payload.date.weekday() != payload.day_of_week:
            raise AppError("invalid_schedule", "day_of_week با تاریخ هماهنگ نیست.", status_code=422)
    if payload.subject_id and book_repo.get_subject(db, payload.subject_id) is None:
        raise AppError("subject_not_found", "درس یافت نشد.", status_code=404)
    if payload.node_id and book_repo.get_node(db, payload.node_id) is None:
        raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
    try:
        row = repo.create_schedule(
            db, user_id=user.id, schedule_type=payload.schedule_type,
            title=payload.title, day_of_week=payload.day_of_week,
            start_time=payload.start_time, end_time=payload.end_time,
            recurring=payload.recurring, date=payload.date,
            subject_id=payload.subject_id, node_id=payload.node_id,
            source=payload.source,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _schedule_out(row)


def day_schedules(
    db: Session, user_id: int, day: date, *, is_school_day: bool
) -> tuple[int, list[Schedule]]:
    """(scheduled_minutes, rows) eating capacity on `day`.

    External rows always apply; school rows only on school days.
    """
    minutes = 0
    rows: list[Schedule] = []
    for s in repo.list_schedules(db, user_id):
        applies = (s.recurring and s.day_of_week == day.weekday()) or (
            not s.recurring and s.date == day)
        if not applies:
            continue
        if s.schedule_type == "school" and not is_school_day:
            continue
        minutes += _minutes(s.start_time, s.end_time)
        rows.append(s)
    return minutes, rows


# -- class sessions --------------------------------------------------------

def list_class_sessions(db: Session, *, user_id: int, limit: int) -> list[ClassSessionOut]:
    user = get_or_create_single_user(db, user_id)
    return [
        ClassSessionOut(
            id=r.id, schedule_id=r.schedule_id, date=r.date, subject_id=r.subject_id,
            subject_name=_subject_name(db, r.subject_id),
            attended=r.attended, notes=r.notes,
        )
        for r in repo.list_class_sessions(db, user.id, limit=limit)
    ]


def create_class_session(
    db: Session, *, user_id: int, payload: ClassSessionCreate
) -> ClassSessionOut:
    user = get_or_create_single_user(db, user_id)
    if book_repo.get_subject(db, payload.subject_id) is None:
        raise AppError("subject_not_found", "درس یافت نشد.", status_code=404)
    if payload.schedule_id is not None:
        from app.models import Schedule as ScheduleModel

        sched = db.get(ScheduleModel, payload.schedule_id)
        if sched is None or sched.user_id != user.id:
            raise AppError("schedule_not_found", "برنامه یافت نشد.", status_code=404)
    try:
        row = repo.create_class_session(
            db, user_id=user.id, schedule_id=payload.schedule_id,
            date=payload.date, subject_id=payload.subject_id,
            attended=payload.attended, notes=payload.notes,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ClassSessionOut(
        id=row.id, schedule_id=row.schedule_id, date=row.date,
        subject_id=row.subject_id, subject_name=_subject_name(db, row.subject_id),
        attended=row.attended, notes=row.notes,
    )


# -- taught lessons (record-only; never analytics) -------------------------

def list_taught(db: Session, *, user_id: int, limit: int) -> list[TaughtLessonOut]:
    user = get_or_create_single_user(db, user_id)
    return [
        TaughtLessonOut(
            id=r.id, class_session_id=r.class_session_id, subject_id=r.subject_id,
            subject_name=_subject_name(db, r.subject_id), node_id=r.node_id,
            node_title=_node_title(db, r.node_id), taught_at=r.taught_at,
            duration_minutes=r.duration_minutes, notes=r.notes,
        )
        for r in repo.list_taught(db, user.id, limit=limit)
    ]


def create_taught(db: Session, *, user_id: int, payload: TaughtLessonCreate) -> TaughtLessonOut:
    user = get_or_create_single_user(db, user_id)
    if book_repo.get_subject(db, payload.subject_id) is None:
        raise AppError("subject_not_found", "درس یافت نشد.", status_code=404)
    if payload.node_id and book_repo.get_node(db, payload.node_id) is None:
        raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
    if payload.class_session_id is not None:
        from app.models import ClassSession as ClassSessionModel

        cs = db.get(ClassSessionModel, payload.class_session_id)
        if cs is None or cs.user_id != user.id:
            raise AppError("class_session_not_found", "جلسه کلاس یافت نشد.", status_code=404)
    if payload.duration_minutes < 0:
        raise AppError("invalid_taught", "مدت نمی‌تواند منفی باشد.", status_code=422)
    try:
        row = repo.create_taught(
            db, user_id=user.id, class_session_id=payload.class_session_id,
            subject_id=payload.subject_id, node_id=payload.node_id,
            taught_at=payload.taught_at, duration_minutes=payload.duration_minutes,
            notes=payload.notes,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return TaughtLessonOut(
        id=row.id, class_session_id=row.class_session_id, subject_id=row.subject_id,
        subject_name=_subject_name(db, row.subject_id), node_id=row.node_id,
        node_title=_node_title(db, row.node_id), taught_at=row.taught_at,
        duration_minutes=row.duration_minutes, notes=row.notes,
    )


# -- homework --------------------------------------------------------------

def _homework_out(db: Session, row: Homework) -> HomeworkOut:
    from app.repositories import planner as planner_repo

    task = planner_repo.latest_task_by_source(db, "homework", row.id)
    return HomeworkOut(
        id=row.id, source_type=row.source_type,  # type: ignore[arg-type]
        title=row.title, subject_id=row.subject_id,
        subject_name=_subject_name(db, row.subject_id), node_id=row.node_id,
        node_title=_node_title(db, row.node_id), due_at=row.due_at,
        estimated_minutes=row.estimated_minutes, priority=row.priority,
        status=row.status,  # type: ignore[arg-type]
        task_id=task.id if task else None,
    )


def list_homework(db: Session, *, user_id: int, status: str | None) -> list[HomeworkOut]:
    user = get_or_create_single_user(db, user_id)
    if status is not None and status not in ("pending", "done", "cancelled"):
        raise AppError("invalid_status", "وضعیت نامعتبر است.", status_code=422)
    return [_homework_out(db, r) for r in repo.list_homework(db, user.id, status=status)]


def create_homework(db: Session, *, user_id: int, payload: HomeworkCreate) -> HomeworkOut:
    from app.schemas.planner import TaskCreate
    from app.services import planner as planner_service

    user = get_or_create_single_user(db, user_id)
    if book_repo.get_subject(db, payload.subject_id) is None:
        raise AppError("subject_not_found", "درس یافت نشد.", status_code=404)
    if payload.node_id and book_repo.get_node(db, payload.node_id) is None:
        raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
    if payload.estimated_minutes < 0:
        raise AppError("invalid_homework", "زمان تخمینی نمی‌تواند منفی باشد.", status_code=422)
    if not 0 <= payload.priority <= 1:
        raise AppError("invalid_homework", "اولویت باید بین ۰ تا ۱ باشد.", status_code=422)
    try:
        row = repo.create_homework(
            db, user_id=user.id, source_type=payload.source_type,
            title=payload.title, subject_id=payload.subject_id,
            node_id=payload.node_id, due_at=payload.due_at,
            estimated_minutes=payload.estimated_minutes,
            priority=payload.priority, status="pending",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    if payload.create_task:
        planner_service.create_task(
            db, user_id=user.id,
            payload=TaskCreate(
                task_type="study", title=f"تکلیف: {row.title}",
                source_type="homework", source_id=row.id,
                node_id=row.node_id, priority=row.priority,
                estimated_minutes=row.estimated_minutes, due_at=row.due_at,
            ),
        )
    return _homework_out(db, row)


def patch_homework(db: Session, *, user_id: int, homework_id: int, payload: HomeworkPatch) -> HomeworkOut:
    from app.repositories import planner as planner_repo

    user = get_or_create_single_user(db, user_id)
    row = repo.get_homework(db, user.id, homework_id)
    if row is None:
        raise AppError("homework_not_found", "تکلیف یافت نشد.", status_code=404)
    if payload.node_id and book_repo.get_node(db, payload.node_id) is None:
        raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
    if payload.estimated_minutes is not None and payload.estimated_minutes < 0:
        raise AppError("invalid_homework", "زمان تخمینی نمی‌تواند منفی باشد.", status_code=422)
    if payload.priority is not None and not 0 <= payload.priority <= 1:
        raise AppError("invalid_homework", "اولویت باید بین ۰ تا ۱ باشد.", status_code=422)
    try:
        if payload.title is not None:
            row.title = payload.title
        if payload.node_id is not None:
            row.node_id = payload.node_id
        if payload.due_at is not None:
            row.due_at = payload.due_at
        if payload.estimated_minutes is not None:
            row.estimated_minutes = payload.estimated_minutes
        if payload.priority is not None:
            row.priority = payload.priority
        if payload.status is not None:
            row.status = payload.status
            if payload.status == "done":
                from app.services import rewards as rewards_service

                flipped = planner_repo.complete_tasks_by_source(
                    db, "homework", row.id,
                    completed_at=utcnow().replace(tzinfo=None))
                for task in flipped:
                    rewards_service.on_task_completed(
                        db, user.id, task, tz=user.timezone)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _homework_out(db, row)


# -- exams -------------------------------------------------------------------

def _exam_out(db: Session, exam_id: int):
    from app.models import Exam as ExamModel

    exam = db.get(ExamModel, exam_id)
    assert exam is not None
    return ExamOut(
        id=exam.id, title=exam.title, exam_type=exam.exam_type,
        provider=exam.provider, exam_date=exam.exam_date,
        total_questions=exam.total_questions, total_score=exam.total_score,
        images_metadata=exam.images_metadata,
        questions=[
            ExamQuestionOut(
                sequence_no=q.sequence_no, question_id=q.question_id,
                topic_node_id=q.topic_node_id, answer_key=q.answer_key,
                user_answer=q.user_answer, result=q.result,  # type: ignore[arg-type]
            )
            for q in repo.list_exam_questions(db, exam.id)
        ],
    )


def list_exams(db: Session, *, user_id: int) -> list[ExamOut]:
    user = get_or_create_single_user(db, user_id)
    return [_exam_out(db, e.id) for e in repo.list_exams(db, user.id)]


def create_exam(db: Session, *, user_id: int, payload: ExamCreate) -> ExamOut:
    user = get_or_create_single_user(db, user_id)
    if payload.total_questions is not None and payload.total_questions < 1:
        raise AppError("invalid_exam", "total_questions باید مثبت باشد.", status_code=422)
    try:
        row = repo.create_exam(
            db, user_id=user.id, title=payload.title, exam_type=payload.exam_type,
            provider=payload.provider, exam_date=payload.exam_date,
            total_questions=payload.total_questions, total_score=payload.total_score,
            images_metadata=payload.images_metadata,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _exam_out(db, row.id)


def get_exam(db: Session, *, user_id: int, exam_id: int) -> ExamOut:
    user = get_or_create_single_user(db, user_id)
    if repo.get_exam(db, user.id, exam_id) is None:
        raise AppError("exam_not_found", "امتحان یافت نشد.", status_code=404)
    return _exam_out(db, exam_id)


def add_exam_questions(
    db: Session, *, user_id: int, exam_id: int, questions: list[ExamQuestionIn]
) -> ExamOut:
    from app.models import Question as QuestionModel

    user = get_or_create_single_user(db, user_id)
    if repo.get_exam(db, user.id, exam_id) is None:
        raise AppError("exam_not_found", "امتحان یافت نشد.", status_code=404)
    seqs = [q.sequence_no for q in questions]
    if len(set(seqs)) != len(seqs):
        raise AppError("invalid_exam_questions", "sequence_no تکراری در بدنه درخواست.", status_code=422)
    for q in questions:
        if q.question_id is not None and db.get(QuestionModel, q.question_id) is None:
            raise AppError("question_not_found", f"سؤال {q.question_id} یافت نشد.", status_code=404)
        if q.topic_node_id is not None and book_repo.get_node(db, q.topic_node_id) is None:
            raise AppError("node_not_found", f"گره {q.topic_node_id} یافت نشد.", status_code=404)
    try:
        for q in questions:
            repo.upsert_exam_question(
                db, exam_id, sequence_no=q.sequence_no, question_id=q.question_id,
                topic_node_id=q.topic_node_id, answer_key=q.answer_key,
                user_answer=q.user_answer, result=q.result,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _exam_out(db, exam_id)


def exam_analytics(db: Session, *, user_id: int, exam_id: int) -> ExamAnalyticsOut:
    """Count-based exam report. No percentages/scores (open decisions #1/#6)."""
    from collections import Counter

    user = get_or_create_single_user(db, user_id)
    if repo.get_exam(db, user.id, exam_id) is None:
        raise AppError("exam_not_found", "امتحان یافت نشد.", status_code=404)
    correct = wrong = unanswered = ungraded = unmapped = 0
    seen: set[int] = set()
    per_subject_correct: Counter[int] = Counter()
    per_subject_wrong: Counter[int] = Counter()
    per_subject_unanswered: Counter[int] = Counter()
    for q in repo.list_exam_questions(db, exam_id):
        if q.result is None:
            ungraded += 1
            continue
        if q.result == "correct":
            correct += 1
        elif q.result == "wrong":
            wrong += 1
        else:
            unanswered += 1
        subject_id = _exam_question_subject(db, q.question_id, q.topic_node_id)
        if subject_id is None:
            unmapped += 1
            continue
        seen.add(subject_id)
        if q.result == "correct":
            per_subject_correct[subject_id] += 1
        elif q.result == "wrong":
            per_subject_wrong[subject_id] += 1
        else:
            per_subject_unanswered[subject_id] += 1
    subjects = [
        ExamSubjectRowOut(
            subject_id=sid, subject_name=_subject_name(db, sid),
            correct=per_subject_correct[sid], wrong=per_subject_wrong[sid],
            unanswered=per_subject_unanswered[sid],
        )
        for sid in sorted(seen)
    ]
    return ExamAnalyticsOut(
        exam_id=exam_id, correct=correct, wrong=wrong,
        unanswered=unanswered, ungraded=ungraded, unmapped=unmapped,
        subjects=subjects,
    )


def _exam_question_subject(
    db: Session, question_id: int | None, topic_node_id: int | None
) -> int | None:
    from app.models import Question as QuestionModel

    if question_id is not None:
        question = db.get(QuestionModel, question_id)
        if question is not None:
            book = book_repo.get_book(db, question.book_id)
            if book is not None:
                return book.subject_id
    if topic_node_id is not None:
        node = book_repo.get_node(db, topic_node_id)
        if node is not None:
            book = book_repo.get_book(db, node.book_id)
            if book is not None:
                return book.subject_id
    return None
