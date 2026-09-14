"""Academic + exam routes (spec 14). Routes only."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db import get_db
from app.schemas.academic import (
    ClassSessionCreate,
    ClassSessionOut,
    ExamAnalyticsOut,
    ExamCreate,
    ExamOut,
    ExamQuestionsIn,
    HomeworkCreate,
    HomeworkOut,
    HomeworkPatch,
    ScheduleCreate,
    ScheduleOut,
    TaughtLessonCreate,
    TaughtLessonOut,
)
from app.services import academic as service

router = APIRouter(tags=["academic"])
exams_router = APIRouter(tags=["exams"])


@router.get("/schedules", response_model=list[ScheduleOut])
def list_schedules(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[ScheduleOut]:
    return service.list_schedules(db, user_id=user_id)


@router.post("/schedules", response_model=ScheduleOut)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ScheduleOut:
    return service.create_schedule(db, user_id=user_id, payload=payload)


@router.get("/class-sessions", response_model=list[ClassSessionOut])
def list_class_sessions(
    limit: int = Query(default=50),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[ClassSessionOut]:
    return service.list_class_sessions(db, user_id=user_id, limit=limit)


@router.post("/class-sessions", response_model=ClassSessionOut)
def create_class_session(
    payload: ClassSessionCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ClassSessionOut:
    return service.create_class_session(db, user_id=user_id, payload=payload)


@router.get("/taught-lessons", response_model=list[TaughtLessonOut])
def list_taught(
    limit: int = Query(default=50),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[TaughtLessonOut]:
    return service.list_taught(db, user_id=user_id, limit=limit)


@router.post("/taught-lessons", response_model=TaughtLessonOut)
def create_taught(
    payload: TaughtLessonCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TaughtLessonOut:
    return service.create_taught(db, user_id=user_id, payload=payload)


@router.get("/homework", response_model=list[HomeworkOut])
def list_homework(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[HomeworkOut]:
    return service.list_homework(db, user_id=user_id, status=status)


@router.post("/homework", response_model=HomeworkOut)
def create_homework(
    payload: HomeworkCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> HomeworkOut:
    return service.create_homework(db, user_id=user_id, payload=payload)


@router.patch("/homework/{homework_id}", response_model=HomeworkOut)
def patch_homework(
    homework_id: int,
    payload: HomeworkPatch,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> HomeworkOut:
    return service.patch_homework(
        db, user_id=user_id, homework_id=homework_id, payload=payload)


@exams_router.get("/exams", response_model=list[ExamOut])
def list_exams(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[ExamOut]:
    return service.list_exams(db, user_id=user_id)


@exams_router.post("/exams", response_model=ExamOut)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ExamOut:
    return service.create_exam(db, user_id=user_id, payload=payload)


@exams_router.get("/exams/{exam_id}", response_model=ExamOut)
def get_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ExamOut:
    return service.get_exam(db, user_id=user_id, exam_id=exam_id)


@exams_router.post("/exams/{exam_id}/questions", response_model=ExamOut)
def add_exam_questions(
    exam_id: int,
    payload: ExamQuestionsIn,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ExamOut:
    return service.add_exam_questions(
        db, user_id=user_id, exam_id=exam_id, questions=payload.questions)


@exams_router.get("/exams/{exam_id}/analytics", response_model=ExamAnalyticsOut)
def get_exam_analytics(
    exam_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ExamAnalyticsOut:
    return service.exam_analytics(db, user_id=user_id, exam_id=exam_id)
