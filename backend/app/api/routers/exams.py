"""Exams router: school exams, mock exams, planned/actual topics, retakes, analysis."""

from __future__ import annotations

import datetime as _dt

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.timeutil import today_local, week_end, week_start
from ...db import models
from ... import config
from ...db.base import get_db
from ...services import common, exams as exams_service, recommendation
from ..deps import current_user, parse_day

router = APIRouter(tags=["exams"])


class ExamPayload(BaseModel):
    exam_type: str = "school"
    title: str
    subject_id: Optional[int] = None
    provider: Optional[str] = None
    exam_date: Optional[str] = None
    date: Optional[str] = None  # UI convenience alias for exam_date
    start_time: Optional[str] = None
    total_questions: Optional[int] = None
    planned_question_count: Optional[int] = None
    planned_duration_minutes: Optional[int] = None
    keep_for_retake: Optional[bool] = None
    use_for_future_prep: Optional[bool] = None
    retake_of_id: Optional[int] = None
    files: list[dict] = []
    notes: Optional[str] = None
    status: Optional[str] = None


class TopicMarkPayload(BaseModel):
    topic_id: int
    mark_kind: str = "planned"
    checked: bool = True
    cascade: bool = True
    subject_id: Optional[int] = None
    question_from: Optional[int] = None
    question_to: Optional[int] = None


class AttemptPayload(BaseModel):
    date: Optional[str] = None
    duration_minutes: Optional[int] = None
    per_subject: dict = {}
    answers: dict = {}
    answer_key: dict = {}
    score: Optional[float] = None
    max_score: Optional[float] = None
    total_questions: Optional[int] = None
    correct_count: Optional[int] = None
    wrong_count: Optional[int] = None
    unanswered_count: Optional[int] = None
    percentage: Optional[float] = None
    attempt_no: Optional[int] = None
    note: Optional[str] = None


@router.get("/exams")
def list_exams(
    exam_type: Optional[str] = None,
    upcoming_only: bool = False,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = exams_service.list_exams(db, user, exam_type=exam_type, upcoming_only=upcoming_only)
    return {
        "exams": rows,
        "today": common.jdate(today_local()),
        "note": "امتحان‌ها رویدادهای آینده‌محور درجه‌یک هستند؛ پوشش «برنامه‌ریزی‌شده» و «واقعی» جدا نگه داشته می‌شود.",
    }


@router.post("/exams")
def create_exam(payload: ExamPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    data = payload.model_dump()
    data["exam_date"] = data.get("exam_date") or data.pop("date", None)
    exam = exams_service.create_exam(db, user, data)
    db.commit()
    return exams_service.exam_payload(db, exam, detailed=True)


@router.get("/exams/calendar")
def calendar(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    # upcoming exams matter months ahead, so the default window is ~3 months
    start = parse_day(from_date) or today_local()
    end = parse_day(to_date) or (start + _dt.timedelta(days=config.value("exam.calendar_horizon_days")))
    return exams_service.exam_calendar(db, user, start, end)


@router.get("/mocks/calendar")
def mock_calendar(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    start = parse_day(from_date) or today_local()
    end = parse_day(to_date) or (start + _dt.timedelta(days=config.value("exam.calendar_horizon_days")))
    payload = exams_service.exam_calendar(db, user, start, end)
    payload["exams"] = [exam for exam in payload["exams"] if exam["exam_type"] == "mock"]
    return payload


@router.get("/mocks/retake-list")
def retake_list(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    rows = list(
        db.query(models.Exam).filter(
            models.Exam.user_id == user.id,
            models.Exam.exam_type == "mock",
            models.Exam.keep_for_retake.is_(True),
        )
    )
    return {
        "mocks": [exams_service.exam_payload(db, row) for row in rows],
        "policy": "تکرار آزمون، نوبت جدید می‌سازد و تاریخچه قبلی را overwrite نمی‌کند.",
    }


@router.get("/mocks/quiet-suggestions")
def mock_suggestions(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {
        "suggestions": recommendation.quiet_suggestions(db, user),
        "policy": "حداکثر یک کارت در روز، قابل رد کردن، بدون اصرار و بدون امتیاز منفی.",
    }


@router.get("/exams/prep-suggestions")
def prep_suggestions(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {
        "suggestions": recommendation.exam_readiness_suggestions(db, user, limit=3),
        "note": "پیشنهاد از مباحث تیک‌خورده همان امتحان ساخته می‌شود و کم‌سروصدا ارائه می‌گردد.",
    }


@router.get("/exams/{exam_id}")
def get_exam(exam_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    exam = db.get(models.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("امتحان پیدا نشد.")
    return exams_service.exam_payload(db, exam, detailed=True)


@router.patch("/exams/{exam_id}")
def update_exam(
    exam_id: int, changes: dict = Body(...), user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    exam = exams_service.update_exam(db, user, exam_id, changes)
    db.commit()
    return exams_service.exam_payload(db, exam)


@router.post("/exams/{exam_id}/topics")
def mark_topic(
    exam_id: int, payload: TopicMarkPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = exams_service.set_topic_marks(
        db,
        user,
        exam_id,
        payload.topic_id,
        mark_kind=payload.mark_kind,
        checked=payload.checked,
        cascade=payload.cascade,
        subject_id=payload.subject_id,
        question_from=payload.question_from,
        question_to=payload.question_to,
    )
    db.commit()
    return result


@router.get("/exams/{exam_id}/topics")
def exam_topics(
    exam_id: int,
    mark_kind: Optional[str] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    exam = db.get(models.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("امتحان پیدا نشد.")
    return exams_service.exam_topics(db, exam_id, mark_kind)


@router.post("/exams/{exam_id}/attempts")
def record_attempt(
    exam_id: int, payload: AttemptPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = exams_service.record_attempt(db, user, exam_id, payload.model_dump())
    db.commit()
    return result


@router.get("/exams/{exam_id}/analysis")
def analysis(exam_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return exams_service.post_analysis(db, user, exam_id)


@router.post("/exams/{exam_id}/retake")
def retake(
    exam_id: int, payload: dict = Body(...), user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    exam = exams_service.create_retake(db, user, exam_id, payload)
    db.commit()
    return exams_service.exam_payload(db, exam, detailed=True)
