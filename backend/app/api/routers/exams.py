"""Exams router: school exams, mock exams, planned/actual topics, retakes, analysis."""

from __future__ import annotations

import datetime as _dt

from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.errors import ValidationError
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
    source: Optional[str] = None
    subjects: list[int] = []
    question_count: Optional[int] = None
    answer_key: dict | str = {}
    answer_key_source: Optional[str] = None
    coverage_range: dict = {}
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
    question_count: Optional[int] = None
    duration_spent: Optional[int] = None
    note: Optional[str] = None


class AnswerKeyPayload(BaseModel):
    answer_key: dict | str = {}
    key: Optional[dict | str] = None
    mode: str = "replace"  # replace | merge
    source: Optional[str] = "manual"


@router.get("/exam-center")
def exam_center(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Exam Center: «گذشته با نتیجه» و «آینده با آماده‌سازی» در یک صفحه."""
    return exams_service.exam_center(db, user)


@router.get("/exams/prep-plan/{exam_id}")
def prep_plan(
    exam_id: int,
    days: Optional[int] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    return exams_service.prep_plan(db, user, exam_id, days=days)


@router.get("/exams/{exam_id}/prep-plan")
def exam_prep_plan(
    exam_id: int,
    days: Optional[int] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    return exams_service.prep_plan(db, user, exam_id, days=days)


@router.put("/exams/{exam_id}/answer-key")
def set_exam_answer_key(
    exam_id: int,
    payload: AnswerKeyPayload,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = exams_service.set_answer_key(db, user, exam_id, payload.model_dump())
    db.commit()
    return result


@router.get("/exams/{exam_id}/answer-key")
def get_exam_answer_key(exam_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    exam = exams_service._owned_exam(db, user, exam_id)
    key = exam.answer_key or {}
    return {
        "exam_id": exam.id,
        "answer_key": key,
        "count": len([value for value in key.values() if value]),
        "cleared": len([value for value in key.values() if not value]),
        "source": exam.answer_key_source,
        "note": "کلید آزمون جدا از برگهٔ پاسخ ذخیره می‌شود و می‌تواند بخشی خالی بماند.",
    }


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


# ---------------------------------------------------------------------------
# Exam files: the paper/answer-sheet scan the student keeps for this exam.
# Stored outside git (backend/data/) with metadata on the exam row.
# ---------------------------------------------------------------------------

MAX_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".docx", ".txt", ".heic"}


def _files_root() -> str:
    import os

    root = os.environ.get("STUDYS459_FILES_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "exam_files"
    )
    return os.path.abspath(root)


@router.post("/exams/{exam_id}/files")
async def upload_exam_file(
    exam_id: int,
    file: UploadFile = File(...),
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    import os
    import re

    exam = db.get(models.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("امتحان پیدا نشد.")
    raw_name = os.path.basename(file.filename or "file")
    suffix = os.path.splitext(raw_name)[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValidationError("فقط فایل PDF، تصویر یا متن برای امتحان قابل ضمیمه است.")
    content = await file.read()
    if not content:
        raise ValidationError("فایل خالی است.")
    if len(content) > MAX_FILE_BYTES:
        raise ValidationError("حجم فایل بیش از حد مجاز است (۲۵ مگابایت).")

    safe = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.splitext(raw_name)[0])[:60] or "file"
    folder = os.path.join(_files_root(), str(exam_id))
    os.makedirs(folder, exist_ok=True)
    stored_name = f"{today_local().isoformat()}-{safe}{suffix}"  # storage name stays ASCII
    with open(os.path.join(folder, stored_name), "wb") as handle:
        handle.write(content)

    metadata = {
        "name": raw_name,
        "stored_name": stored_name,
        "size": len(content),
        "content_type": file.content_type,
        "uploaded_at": common.jdatetime(_dt.datetime.now()),
    }
    files = list(exam.files or [])
    files = [item for item in files if item.get("stored_name") != stored_name] + [metadata]
    exam.files = files
    db.commit()
    return {"exam_id": exam_id, "files": files, "note": "فایل روی همین دستگاه ذخیره می‌شود و در گیت نمی‌آید."}


@router.get("/exams/{exam_id}/files/{stored_name}")
def download_exam_file(
    exam_id: int, stored_name: str, user: models.User = Depends(current_user), db: Session = Depends(get_db)
):
    import os

    from fastapi.responses import FileResponse

    exam = db.get(models.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("امتحان پیدا نشد.")
    if not any(item.get("stored_name") == stored_name for item in (exam.files or [])):
        from ...core.errors import NotFoundError

        raise NotFoundError("فایل پیدا نشد.")
    path = os.path.join(_files_root(), str(exam_id), os.path.basename(stored_name))
    if not os.path.exists(path):
        from ...core.errors import NotFoundError

        raise NotFoundError("فایل روی دیسک پیدا نشد.")
    return FileResponse(path, filename=os.path.basename(stored_name))
