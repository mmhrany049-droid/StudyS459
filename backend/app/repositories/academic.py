"""Academic persistence (spec 04 academic section)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ClassSession,
    Exam,
    ExamQuestion,
    Homework,
    Schedule,
    TaughtLesson,
)


def list_schedules(db: Session, user_id: int) -> list[Schedule]:
    return list(
        db.execute(
            select(Schedule).where(Schedule.user_id == user_id)
            .order_by(Schedule.day_of_week, Schedule.start_time)
        ).scalars().all()
    )


def create_schedule(db: Session, **fields) -> Schedule:
    row = Schedule(**fields)
    db.add(row)
    db.flush()
    return row


def list_class_sessions(db: Session, user_id: int, *, limit: int) -> list[ClassSession]:
    return list(
        db.execute(
            select(ClassSession).where(ClassSession.user_id == user_id)
            .order_by(ClassSession.date.desc(), ClassSession.id.desc())
            .limit(limit)
        ).scalars().all()
    )


def create_class_session(db: Session, **fields) -> ClassSession:
    row = ClassSession(**fields)
    db.add(row)
    db.flush()
    return row


def list_taught(db: Session, user_id: int, *, limit: int) -> list[TaughtLesson]:
    return list(
        db.execute(
            select(TaughtLesson).where(TaughtLesson.user_id == user_id)
            .order_by(TaughtLesson.taught_at.desc(), TaughtLesson.id.desc())
            .limit(limit)
        ).scalars().all()
    )


def create_taught(db: Session, **fields) -> TaughtLesson:
    row = TaughtLesson(**fields)
    db.add(row)
    db.flush()
    return row


def list_homework(db: Session, user_id: int, *, status: str | None) -> list[Homework]:
    stmt = select(Homework).where(Homework.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Homework.status == status)
    return list(
        db.execute(stmt.order_by(Homework.due_at, Homework.id)).scalars().all()
    )


def get_homework(db: Session, user_id: int, homework_id: int) -> Homework | None:
    return db.execute(
        select(Homework).where(Homework.id == homework_id, Homework.user_id == user_id)
    ).scalar_one_or_none()


def create_homework(db: Session, **fields) -> Homework:
    row = Homework(**fields)
    db.add(row)
    db.flush()
    return row


def list_exams(db: Session, user_id: int) -> list[Exam]:
    return list(
        db.execute(
            select(Exam).where(Exam.user_id == user_id)
            .order_by(Exam.exam_date.desc(), Exam.id.desc())
        ).scalars().all()
    )


def get_exam(db: Session, user_id: int, exam_id: int) -> Exam | None:
    return db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.user_id == user_id)
    ).scalar_one_or_none()


def create_exam(db: Session, **fields) -> Exam:
    row = Exam(**fields)
    db.add(row)
    db.flush()
    return row


def list_exam_questions(db: Session, exam_id: int) -> list[ExamQuestion]:
    return list(
        db.execute(
            select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.sequence_no)
        ).scalars().all()
    )


def get_exam_question(db: Session, exam_id: int, sequence_no: int) -> ExamQuestion | None:
    return db.execute(
        select(ExamQuestion).where(
            ExamQuestion.exam_id == exam_id,
            ExamQuestion.sequence_no == sequence_no,
        )
    ).scalar_one_or_none()


def upsert_exam_question(db: Session, exam_id: int, **fields) -> ExamQuestion:
    """Duplicate-safe: re-posting a sequence updates it instead of doubling."""
    row = get_exam_question(db, exam_id, fields["sequence_no"])
    if row is None:
        row = ExamQuestion(exam_id=exam_id, **fields)
        db.add(row)
    else:
        for key, value in fields.items():
            setattr(row, key, value)
    db.flush()
    return row
