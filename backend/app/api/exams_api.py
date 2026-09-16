"""امتحانات، آزمون آزمایشی چنددرسه و آمادگی امتحان — اسناد 05/06/07."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config as cfg
from .. import models as m
from ..db import get_db
from ..schemas import (
    ExamAnswerKeyIn,
    ExamAttemptIn,
    ExamIn,
    ExamSectionsIn,
    ExamTopicMapIn,
    UpcomingExamIn,
)
from ..services import exams as exam_svc
from ..services import readiness as readiness_svc
from ..services.common import current_user
from ..utils import jalali

router = APIRouter(prefix="/api", tags=["exams"])


@router.get("/exams")
def list_exams(kind: str | None = None, db: Session = Depends(get_db)):
    user = current_user(db)
    q = select(m.Exam).where(m.Exam.user_id == user.id)
    if kind:
        q = q.where(m.Exam.exam_kind == kind)
    out = []
    for e in db.scalars(q.order_by(m.Exam.exam_date.desc())).all():
        attempts = exam_svc.list_attempts(db, e.id)
        files = db.scalars(select(m.ExamFile).where(m.ExamFile.exam_id == e.id)).all()
        subject = db.get(m.Subject, e.subject_id) if e.subject_id else None
        out.append({
            "id": e.id, "title": e.title, "exam_kind": e.exam_kind,
            "exam_type": e.exam_type, "provider": e.provider,
            "subject": subject.name if subject else None,
            "exam_date": e.exam_date.isoformat(),
            "exam_date_jalali": jalali.to_jalali_str(e.exam_date),
            "total_questions": e.total_questions,
            "file_count": len(files),
            "attempt_count": len(attempts),
            "best_percentage": max((a.percentage for a in attempts), default=None),
            "last_percentage": attempts[-1].percentage if attempts else None,
        })
    return out


@router.post("/exams")
def create_exam(body: ExamIn, db: Session = Depends(get_db)):
    user = current_user(db)
    exam = m.Exam(
        user_id=user.id, title=body.title, exam_kind=body.exam_kind,
        exam_type=body.exam_type, provider=body.provider, subject_id=body.subject_id,
        exam_date=body.exam_date or date.today(),
        total_questions=body.total_questions, notes=body.notes,
    )
    db.add(exam)
    db.commit()
    return exam_svc.exam_detail(db, user, exam.id)


@router.get("/exams/{exam_id}")
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    user = current_user(db)
    try:
        return exam_svc.exam_detail(db, user, exam_id)
    except exam_svc.ExamError as e:
        raise HTTPException(404, str(e))


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: int, db: Session = Depends(get_db)):
    user = current_user(db)
    exam = db.get(m.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        raise HTTPException(404, "امتحان یافت نشد.")
    for table, col in (
        (m.ExamAttemptAnswer, None), (m.ExamAttempt, m.ExamAttempt.exam_id),
        (m.ExamAnswerKey, m.ExamAnswerKey.exam_id), (m.ExamFile, m.ExamFile.exam_id),
        (m.ExamSubjectSection, m.ExamSubjectSection.exam_id),
        (m.ExamQuestionTopicMap, m.ExamQuestionTopicMap.exam_id),
    ):
        if col is None:
            ids = [a.id for a in exam_svc.list_attempts(db, exam_id)]
            if ids:
                db.execute(table.__table__.delete().where(table.attempt_id.in_(ids)))
        else:
            db.execute(table.__table__.delete().where(col == exam_id))
    db.delete(exam)
    db.commit()
    return {"deleted": True}


@router.post("/exams/{exam_id}/files")
async def upload_file(exam_id: int, file: UploadFile = File(...),
                      file_kind: str = Form("exam_paper"),
                      db: Session = Depends(get_db)):
    user = current_user(db)
    exam = db.get(m.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        raise HTTPException(404, "امتحان یافت نشد.")
    content = await file.read()
    try:
        row = exam_svc.save_exam_file(db, exam_id, file.filename or "file", content, file_kind)
        db.commit()
    except exam_svc.ExamError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    return {"id": row.id, "file_type": row.file_type, "file_kind": row.file_kind,
            "original_name": row.original_name, "size_bytes": row.size_bytes,
            "url": f"/api/exam-files/{row.id}"}


@router.get("/exam-files/{file_id}")
def download_file(file_id: int, db: Session = Depends(get_db)):
    row = db.get(m.ExamFile, file_id)
    if not row:
        raise HTTPException(404, "فایل یافت نشد.")
    path = cfg.STORAGE_DIR / row.file_path
    if not path.exists():
        raise HTTPException(404, "فایل روی دیسک موجود نیست.")
    return FileResponse(path, filename=row.original_name)


@router.delete("/exam-files/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    row = db.get(m.ExamFile, file_id)
    if not row:
        raise HTTPException(404, "فایل یافت نشد.")
    path = cfg.STORAGE_DIR / row.file_path
    if path.exists():
        path.unlink()
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.put("/exams/{exam_id}/answer-key")
def put_answer_key(exam_id: int, body: ExamAnswerKeyIn, db: Session = Depends(get_db)):
    try:
        res = exam_svc.set_answer_key(db, exam_id, [i.model_dump() for i in body.items],
                                      body.compact)
        db.commit()
        return res
    except exam_svc.ExamError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("/exams/{exam_id}/attempts")
def get_attempts(exam_id: int, db: Session = Depends(get_db)):
    if not db.get(m.Exam, exam_id):
        raise HTTPException(404, "امتحان یافت نشد.")
    return [exam_svc.attempt_detail(db, a) for a in exam_svc.list_attempts(db, exam_id)]


@router.post("/exams/{exam_id}/attempts")
def post_attempt(exam_id: int, body: ExamAttemptIn, db: Session = Depends(get_db)):
    user = current_user(db)
    try:
        res = exam_svc.add_attempt(db, user, exam_id, body.label, body.attempted_at,
                                   body.duration_minutes, body.notes,
                                   [a.model_dump() for a in body.answers])
        db.commit()
        return res
    except exam_svc.ExamError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.put("/exams/{exam_id}/sections")
def put_sections(exam_id: int, body: ExamSectionsIn, db: Session = Depends(get_db)):
    try:
        res = exam_svc.set_sections(db, exam_id, [s.model_dump() for s in body.sections])
        db.commit()
        return res
    except exam_svc.ExamError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.put("/exams/{exam_id}/topic-map")
def put_topic_map(exam_id: int, body: ExamTopicMapIn, db: Session = Depends(get_db)):
    res = exam_svc.set_topic_map(db, exam_id, [i.model_dump() for i in body.items])
    db.commit()
    return res


@router.get("/exams/{exam_id}/analysis")
def exam_analysis(exam_id: int, db: Session = Depends(get_db)):
    if not db.get(m.Exam, exam_id):
        raise HTTPException(404, "امتحان یافت نشد.")
    return exam_svc.analysis(db, exam_id)


# ----------------------------------------------------------- آمادگی امتحان
@router.get("/upcoming-exams")
def list_upcoming(db: Session = Depends(get_db)):
    return readiness_svc.list_upcoming(db, current_user(db))


@router.post("/upcoming-exams")
def create_upcoming(body: UpcomingExamIn, db: Session = Depends(get_db)):
    user = current_user(db)
    row = readiness_svc.create_upcoming(db, user, body.title, body.exam_date,
                                        body.node_ids, body.notes)
    from ..services.rewards import check_badges
    check_badges(db, user)
    db.commit()
    return {"id": row.id, "title": row.title,
            "exam_date_jalali": jalali.to_jalali_str(row.exam_date)}


@router.delete("/upcoming-exams/{upcoming_id}")
def delete_upcoming(upcoming_id: int, db: Session = Depends(get_db)):
    user = current_user(db)
    row = db.get(m.UpcomingExam, upcoming_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "یافت نشد.")
    db.execute(m.UpcomingExamTopic.__table__.delete().where(
        m.UpcomingExamTopic.upcoming_exam_id == upcoming_id))
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.get("/upcoming-exams/{upcoming_id}/suggested-tasks")
def suggested(upcoming_id: int, wrong_only: bool = False, db: Session = Depends(get_db)):
    try:
        return readiness_svc.suggested_tasks(db, current_user(db), upcoming_id, wrong_only)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/upcoming-exams/{upcoming_id}/materialize")
def materialize(upcoming_id: int, limit: int = 5, db: Session = Depends(get_db)):
    try:
        res = readiness_svc.materialize_tasks(db, current_user(db), upcoming_id, limit)
    except ValueError as e:
        db.rollback()
        raise HTTPException(404, str(e))
    db.commit()
    return res
