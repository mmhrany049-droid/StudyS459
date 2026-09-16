"""
امتحانات — اسناد 05_EXAMS_MEDIA_RESULTS و 06_MOCK_MULTI_SUBJECT.
فایل PDF/عکس + پاسخ‌نامه رسمی + نوبت‌های چندگانه با زمان + نگاشت چنددرسه.
"""
from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config as cfg
from .. import models as m
from ..utils import jalali
from . import rewards
from .common import node_full_title, parse_compact_answer_key


class ExamError(Exception):
    pass


def save_exam_file(db: Session, exam_id: int, filename: str, content: bytes,
                   file_kind: str = "exam_paper") -> m.ExamFile:
    ext = Path(filename).suffix.lower()
    if ext in cfg.ALLOWED_PDF_EXT:
        file_type, limit = "pdf", cfg.EXAM_PDF_MAX_BYTES
    elif ext in cfg.ALLOWED_IMAGE_EXT:
        file_type, limit = "image", cfg.EXAM_IMAGE_MAX_BYTES
    else:
        raise ExamError("فقط PDF یا عکس (png/jpg/jpeg/webp/gif) مجاز است.")
    if len(content) > limit:
        raise ExamError(
            f"حجم فایل بیش از حد مجاز است ({limit // (1024*1024)}MB برای {file_type})."
        )
    if file_kind not in cfg.EXAM_FILE_KINDS:
        file_kind = "exam_paper"

    folder = cfg.STORAGE_DIR / f"exam_{exam_id}"
    folder.mkdir(parents=True, exist_ok=True)
    safe = f"{uuid.uuid4().hex[:10]}{ext}"
    path = folder / safe
    path.write_bytes(content)

    row = m.ExamFile(
        exam_id=exam_id, file_path=str(path.relative_to(cfg.STORAGE_DIR)),
        original_name=filename, file_type=file_type, file_kind=file_kind,
        size_bytes=len(content),
    )
    db.add(row)
    db.flush()
    return row


def set_answer_key(db: Session, exam_id: int, items: list[dict],
                   compact: str | None = None) -> dict:
    payload: dict[int, int] = {}
    for it in items:
        if it.get("answer_key") is not None:
            payload[int(it["sequence_no"])] = int(it["answer_key"])
    if compact:
        for seq, key in parse_compact_answer_key(compact).items():
            if key is not None:
                payload[seq] = key
    for seq, key in payload.items():
        if key not in (1, 2, 3, 4):
            raise ExamError(f"گزینه نامعتبر برای سوال {seq}.")
        row = db.scalar(select(m.ExamAnswerKey).where(
            m.ExamAnswerKey.exam_id == exam_id, m.ExamAnswerKey.sequence_no == seq))
        if row:
            row.answer_key = key
        else:
            db.add(m.ExamAnswerKey(exam_id=exam_id, sequence_no=seq, answer_key=key))
    db.flush()
    exam = db.get(m.Exam, exam_id)
    if exam and payload:
        exam.total_questions = max(exam.total_questions, max(payload))
    return {"saved": len(payload)}


def add_attempt(db: Session, user: m.User, exam_id: int, label: str,
                attempted_at: date | None, duration_minutes: int,
                notes: str, answers: list[dict]) -> dict:
    exam = db.get(m.Exam, exam_id)
    if not exam:
        raise ExamError("امتحان یافت نشد.")
    keys = {
        r.sequence_no: r.answer_key
        for r in db.scalars(select(m.ExamAnswerKey).where(
            m.ExamAnswerKey.exam_id == exam_id)).all()
    }
    if not keys:
        raise ExamError("ابتدا پاسخ‌نامه رسمی امتحان را ثبت کن.")

    attempt = m.ExamAttempt(
        exam_id=exam_id, user_id=user.id,
        label=label or f"نوبت {len(list_attempts(db, exam_id)) + 1}",
        attempted_at=attempted_at or date.today(),
        duration_minutes=duration_minutes, notes=notes,
    )
    db.add(attempt)
    db.flush()

    correct = wrong = unanswered = 0
    given = {int(a["sequence_no"]): a.get("user_answer") for a in answers}
    for seq in sorted(keys):
        choice = given.get(seq)
        if choice is None:
            result = "unanswered"
            unanswered += 1
        elif int(choice) == keys[seq]:
            result = "correct"
            correct += 1
        else:
            result = "wrong"
            wrong += 1
        db.add(m.ExamAttemptAnswer(attempt_id=attempt.id, sequence_no=seq,
                                   user_answer=int(choice) if choice is not None else None,
                                   result=result))
    total = correct + wrong + unanswered
    attempt.correct_count = correct
    attempt.wrong_count = wrong
    attempt.unanswered_count = unanswered
    attempt.percentage = round(correct / total * 100, 2) if total else 0.0
    db.flush()
    rewards.check_badges(db, user)
    return attempt_detail(db, attempt)


def list_attempts(db: Session, exam_id: int) -> list[m.ExamAttempt]:
    return list(db.scalars(select(m.ExamAttempt).where(
        m.ExamAttempt.exam_id == exam_id).order_by(m.ExamAttempt.attempted_at)).all())


def attempt_detail(db: Session, attempt: m.ExamAttempt) -> dict:
    return {
        "id": attempt.id,
        "exam_id": attempt.exam_id,
        "label": attempt.label,
        "attempted_at": attempt.attempted_at.isoformat(),
        "attempted_at_jalali": jalali.to_jalali_str(attempt.attempted_at),
        "duration_minutes": attempt.duration_minutes,
        "correct": attempt.correct_count,
        "wrong": attempt.wrong_count,
        "unanswered": attempt.unanswered_count,
        "percentage": attempt.percentage,
        "notes": attempt.notes,
    }


def exam_detail(db: Session, user: m.User, exam_id: int) -> dict:
    exam = db.get(m.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        raise ExamError("امتحان یافت نشد.")
    keys = db.scalars(select(m.ExamAnswerKey).where(
        m.ExamAnswerKey.exam_id == exam_id).order_by(m.ExamAnswerKey.sequence_no)).all()
    files = db.scalars(select(m.ExamFile).where(m.ExamFile.exam_id == exam_id)).all()
    sections = db.scalars(select(m.ExamSubjectSection).where(
        m.ExamSubjectSection.exam_id == exam_id).order_by(
        m.ExamSubjectSection.sequence_from)).all()
    topic_map = db.scalars(select(m.ExamQuestionTopicMap).where(
        m.ExamQuestionTopicMap.exam_id == exam_id)).all()
    attempts = list_attempts(db, exam_id)

    return {
        "id": exam.id,
        "title": exam.title,
        "exam_kind": exam.exam_kind,
        "exam_type": exam.exam_type,
        "provider": exam.provider,
        "subject_id": exam.subject_id,
        "exam_date": exam.exam_date.isoformat(),
        "exam_date_jalali": jalali.to_jalali_str(exam.exam_date),
        "total_questions": exam.total_questions,
        "notes": exam.notes,
        "answer_key": [{"sequence_no": k.sequence_no, "answer_key": k.answer_key} for k in keys],
        "files": [
            {"id": f.id, "file_type": f.file_type, "file_kind": f.file_kind,
             "original_name": f.original_name, "size_bytes": f.size_bytes,
             "url": f"/api/exam-files/{f.id}"}
            for f in files
        ],
        "sections": [
            {"id": s.id, "subject_id": s.subject_id,
             "subject": db.get(m.Subject, s.subject_id).name if db.get(m.Subject, s.subject_id) else "",
             "sequence_from": s.sequence_from, "sequence_to": s.sequence_to,
             "duration_minutes": s.duration_minutes}
            for s in sections
        ],
        "topic_map": [
            {"sequence_no": t.sequence_no, "node_id": t.node_id,
             "node_title": node_full_title(db, t.node_id)}
            for t in sorted(topic_map, key=lambda x: x.sequence_no)
        ],
        "attempts": [attempt_detail(db, a) for a in attempts],
        "progress": _progress(attempts),
        "breakdown": analysis(db, exam_id),
    }


def _progress(attempts: list[m.ExamAttempt]) -> dict:
    """S9 — مقایسه نوبت‌ها (درصد و زمان)."""
    if not attempts:
        return {"points": [], "delta_percentage": None, "delta_minutes": None}
    pts = [
        {"label": a.label, "date_jalali": jalali.to_jalali_str(a.attempted_at),
         "percentage": a.percentage, "duration_minutes": a.duration_minutes}
        for a in attempts
    ]
    return {
        "points": pts,
        "delta_percentage": round(pts[-1]["percentage"] - pts[0]["percentage"], 2)
        if len(pts) > 1 else None,
        "delta_minutes": (pts[-1]["duration_minutes"] - pts[0]["duration_minutes"])
        if len(pts) > 1 else None,
    }


def analysis(db: Session, exam_id: int) -> dict:
    """نتیجه per subject و per topic برای آخرین نوبت."""
    attempts = list_attempts(db, exam_id)
    if not attempts:
        return {"per_subject": [], "per_topic": []}
    last = attempts[-1]
    answers = db.scalars(select(m.ExamAttemptAnswer).where(
        m.ExamAttemptAnswer.attempt_id == last.id)).all()
    by_seq = {a.sequence_no: a.result for a in answers}

    per_subject = []
    for s in db.scalars(select(m.ExamSubjectSection).where(
            m.ExamSubjectSection.exam_id == exam_id)).all():
        subject = db.get(m.Subject, s.subject_id)
        c = w = u = 0
        for seq in range(s.sequence_from, s.sequence_to + 1):
            r = by_seq.get(seq)
            if r == "correct":
                c += 1
            elif r == "wrong":
                w += 1
            elif r == "unanswered":
                u += 1
        total = c + w + u
        per_subject.append({
            "subject_id": s.subject_id,
            "subject": subject.name if subject else "",
            "range": [s.sequence_from, s.sequence_to],
            "correct": c, "wrong": w, "unanswered": u,
            "percentage": round(c / total * 100, 1) if total else 0.0,
            "duration_minutes": s.duration_minutes,
        })

    topic_rows: dict[int, dict] = {}
    for t in db.scalars(select(m.ExamQuestionTopicMap).where(
            m.ExamQuestionTopicMap.exam_id == exam_id)).all():
        r = by_seq.get(t.sequence_no)
        if r is None:
            continue
        row = topic_rows.setdefault(t.node_id, {
            "node_id": t.node_id, "title": node_full_title(db, t.node_id),
            "correct": 0, "wrong": 0, "unanswered": 0})
        row[r] += 1
    per_topic = []
    for row in topic_rows.values():
        total = row["correct"] + row["wrong"] + row["unanswered"]
        row["percentage"] = round(row["correct"] / total * 100, 1) if total else 0.0
        per_topic.append(row)
    per_topic.sort(key=lambda x: x["percentage"])
    return {"per_subject": per_subject, "per_topic": per_topic,
            "attempt_label": last.label}


def set_sections(db: Session, exam_id: int, sections: list[dict]) -> dict:
    db.execute(m.ExamSubjectSection.__table__.delete().where(
        m.ExamSubjectSection.exam_id == exam_id))
    for s in sections:
        if s["sequence_to"] < s["sequence_from"]:
            raise ExamError("بازه شماره سوال نامعتبر است.")
        db.add(m.ExamSubjectSection(
            exam_id=exam_id, subject_id=s["subject_id"],
            sequence_from=s["sequence_from"], sequence_to=s["sequence_to"],
            duration_minutes=s.get("duration_minutes"),
        ))
    exam = db.get(m.Exam, exam_id)
    if exam and sections:
        exam.total_questions = max(exam.total_questions,
                                   max(s["sequence_to"] for s in sections))
        exam.exam_kind = "mock" if len(sections) > 1 else exam.exam_kind
    db.flush()
    return {"sections": len(sections)}


def set_topic_map(db: Session, exam_id: int, items: list[dict]) -> dict:
    count = 0
    for it in items:
        for seq in range(it["sequence_from"], it["sequence_to"] + 1):
            row = db.scalar(select(m.ExamQuestionTopicMap).where(
                m.ExamQuestionTopicMap.exam_id == exam_id,
                m.ExamQuestionTopicMap.sequence_no == seq))
            if row:
                row.node_id = it["node_id"]
            else:
                db.add(m.ExamQuestionTopicMap(exam_id=exam_id, sequence_no=seq,
                                              node_id=it["node_id"]))
            count += 1
    db.flush()
    return {"mapped": count}
