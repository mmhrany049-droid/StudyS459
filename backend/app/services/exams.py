"""Exam engine: school exams and mock exams as first-class future oriented events.

Rules from the V3 specification:

* planned and actual topic coverage are separate data;
* a mock exam stores date/time, type, subjects, planned/actual topics,
  planned/actual question count, planned/actual duration, status, preparation
  relationship and retake relationship;
* upcoming exams raise the priority of relevant topics but never erase
  long-term goals, review or capacity;
* post-analysis covers score, accuracy, unanswered, time, topic/difficulty
  breakdown, errors, prerequisites and planned-vs-actual coverage.
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.errors import NotFoundError, ValidationError
from ..core.timeutil import clamp, now_utc, today_local
from ..db import models
from ..domain.enums import (
    EXAM_TYPE_HINTS_FA,
    EXAM_TYPE_LABELS_FA,
    ExamStatus,
    ExamType,
    TopicMarkKind,
)
from . import common

MODEL_VERSION = config.MODEL_VERSION


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# V3.1 unified exam model (doc 03): types, subjects, answer key, coverage range
# ---------------------------------------------------------------------------

ALLOWED_CHOICES = {"1", "2", "3", "4"}


def exam_type_label(exam_type: Optional[str]) -> str:
    return EXAM_TYPE_LABELS_FA.get(exam_type or "", "آزمون")


def normalize_subjects(payload: dict) -> list[int]:
    """`subjects[]` accepts ids; the legacy single `subject_id` still works."""
    raw = payload.get("subjects")
    ids: list[int] = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            value = common.to_int(item if not isinstance(item, dict) else item.get("id"))
            if value and value not in ids:
                ids.append(value)
    elif raw not in (None, ""):
        value = common.to_int(raw)
        if value:
            ids.append(value)
    primary = common.to_int(payload.get("subject_id"))
    if primary and primary not in ids:
        ids.insert(0, primary)
    return ids


def normalize_answer_key(raw) -> dict:
    """«۱:۲» / {"1": 2} / [1, 3, null] -> {"1": "2"} with only 1..4 kept.

    An empty choice means «کلید ثبت نشده» for that question: the question stays
    NOT_EVALUABLE instead of being counted wrong (V3 rule).
    """
    key: dict[str, str] = {}
    if not raw:
        return key
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, (list, tuple)):
        items = ((index + 1, value) for index, value in enumerate(raw))
    else:
        items = []
        for chunk in str(raw).replace("،", ",").split(","):
            if ":" in chunk:
                left, _, right = chunk.partition(":")
                items.append((left, right))
    for sequence, value in items:
        sequence_text = common.normalize_digits(str(sequence)).strip()
        if not sequence_text.isdigit():
            continue
        choice = common.normalize_digits(str(value if value is not None else "")).strip()
        if choice in ALLOWED_CHOICES:
            key[str(int(sequence_text))] = choice
        elif choice in ("", "0", "none", "null", "خالی", "-"):
            key[str(int(sequence_text))] = ""
    return key


def answer_key_size(exam: models.Exam) -> int:
    return len([value for value in (exam.answer_key or {}).values() if value])


def _subject_titles(db: Session, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    rows = db.scalars(select(models.Subject).where(models.Subject.id.in_(ids))).all()
    by_id = {row.id: row for row in rows}
    return [{"id": sid, "title": by_id[sid].name} for sid in ids if sid in by_id]


def set_answer_key(db: Session, user: models.User, exam_id: int, payload: dict) -> dict:
    exam = _owned_exam(db, user, exam_id)
    incoming = payload.get("answer_key", payload.get("key"))
    key = normalize_answer_key(incoming)
    previous = exam.answer_key or {}
    mode = payload.get("mode", "replace")
    if mode == "merge":
        merged = dict(previous)
        merged.update(key)
        key = merged
    exam.answer_key = key
    exam.answer_key_source = payload.get("source") or "manual"
    if not exam.question_count:
        exam.question_count = len(key)
    changed = sum(1 for seq, value in key.items() if previous.get(seq) != value)
    db.flush()
    common.audit(
        db, "exam_answer_key_updated", user_id=user.id, entity_type="exam", entity_id=exam.id,
        before={"count": len(previous)}, after={"count": len(key)},
    )
    return {
        "exam_id": exam.id,
        "count": len([value for value in key.values() if value]),
        "cleared": len([value for value in key.values() if not value]),
        "changed": changed,
        "answer_key": key,
        "recalc_required": changed > 0,
        "note": "کلید آزمون جدا از برگهٔ پاسخ نگه داشته می‌شود؛ هر تلاش با همان کلید زمان خودش تصحیح می‌شود.",
    }


def _attempt_count(db: Session, exam_id: int) -> int:
    return len(db.scalars(select(models.ExamAttempt).where(models.ExamAttempt.exam_id == exam_id)).all())


def _owned_exam(db: Session, user: models.User, exam_id: int) -> models.Exam:
    exam = db.get(models.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        raise NotFoundError("امتحان پیدا نشد.")
    return exam


def parse_clock(value) -> Optional[_dt.time]:
    """«۰۸:۳۰» / «8:30» / «8» -> datetime.time, so SQLite never sees a raw string."""
    if value in (None, ""):
        return None
    if isinstance(value, _dt.time):
        return value
    text = common.normalize_digits(str(value)).strip().replace(".", ":")
    if ":" in text:
        hour_text, _, minute_text = text.partition(":")
    else:
        hour_text, minute_text = text, "0"
    try:
        hour, minute = int(hour_text), int(minute_text or 0)
    except (TypeError, ValueError):
        raise ValidationError("ساعت شروع باید به شکل ۸:۳۰ باشد.")
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValidationError("ساعت شروع معتبر نیست.")
    return _dt.time(hour=hour, minute=minute)


def create_exam(db: Session, user: models.User, payload: dict) -> models.Exam:
    exam_type = payload.get("exam_type", ExamType.SCHOOL.value)
    if exam_type not in {t.value for t in ExamType}:
        raise ValidationError(
            "نوع امتحان باید یکی از این‌ها باشد: " + "، ".join(EXAM_TYPE_LABELS_FA.values())
        )
    exam_date = common.parse_date_if_string(payload.get("exam_date") or payload.get("date"))
    if not exam_date:
        raise ValidationError("تاریخ امتحان لازم است.")
    retake_of = common.to_int(payload.get("retake_of_id"))
    attempt_no = 1
    if retake_of:
        parent = db.get(models.Exam, retake_of)
        if parent and parent.user_id == user.id:
            attempt_no = (parent.attempt_no or 1) + 1
    subjects = normalize_subjects(payload)
    if subjects:
        known = {
            row.id for row in db.scalars(select(models.Subject).where(models.Subject.id.in_(subjects))).all()
        }
        unknown = [sid for sid in subjects if sid not in known]
        if unknown:
            # never store a dangling subject: the exam would silently lose a درس
            raise ValidationError("درس انتخاب‌شده پیدا نشد: " + "، ".join(str(value) for value in unknown))
    answer_key = normalize_answer_key(payload.get("answer_key"))
    exam = models.Exam(
        user_id=user.id,
        exam_type=exam_type,
        title=payload.get("title") or "امتحان",
        subject_id=subjects[0] if subjects else common.to_int(payload.get("subject_id")),
        subjects=subjects,
        source=payload.get("source") or payload.get("provider"),
        question_count=common.to_int(payload.get("question_count") or payload.get("total_questions")),
        answer_key=answer_key,
        answer_key_source=payload.get("answer_key_source") or ("manual" if answer_key else None),
        coverage_range=payload.get("coverage_range") or {},
        provider=payload.get("provider"),
        exam_date=exam_date,
        start_time=parse_clock(payload.get("start_time")),
        status=payload.get("status", ExamStatus.PLANNED.value),
        total_questions=common.to_int(payload.get("total_questions")),
        planned_question_count=common.to_int(payload.get("planned_question_count")),
        planned_duration_minutes=common.to_int(payload.get("planned_duration_minutes")),
        keep_for_retake=bool(payload.get("keep_for_retake", exam_type == ExamType.MOCK.value)),
        use_for_future_prep=bool(payload.get("use_for_future_prep", True)),
        retake_of_id=retake_of,
        attempt_no=attempt_no,
        files=payload.get("files") or [],
        notes=payload.get("notes"),
    )
    db.add(exam)
    db.flush()
    common.audit(db, "exam_created", user_id=user.id, entity_type="exam", entity_id=exam.id, after={"title": exam.title, "type": exam_type})
    common.observe(db, user.id, "exam_created", payload={"exam_id": exam.id, "type": exam_type, "date": str(exam_date)}, source="user")
    return exam


def update_exam(db: Session, user: models.User, exam_id: int, changes: dict) -> models.Exam:
    exam = db.get(models.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        raise NotFoundError("امتحان پیدا نشد.")
    mapping = {
        "title": "title",
        "provider": "provider",
        "start_time": "start_time",
        "status": "status",
        "total_questions": "total_questions",
        "planned_question_count": "planned_question_count",
        "actual_question_count": "actual_question_count",
        "planned_duration_minutes": "planned_duration_minutes",
        "actual_duration_minutes": "actual_duration_minutes",
        "score": "score",
        "max_score": "max_score",
        "percentage": "percentage",
        "correct_count": "correct_count",
        "wrong_count": "wrong_count",
        "unanswered_count": "unanswered_count",
        "keep_for_retake": "keep_for_retake",
        "use_for_future_prep": "use_for_future_prep",
        "notes": "notes",
        "files": "files",
        "source": "source",
        "question_count": "question_count",
        "coverage_range": "coverage_range",
    }
    for key, attribute in mapping.items():
        if key in changes:
            setattr(exam, attribute, parse_clock(changes[key]) if key == "start_time" else changes[key])
    if changes.get("exam_date"):
        exam.exam_date = common.parse_date_if_string(changes["exam_date"])
    db.flush()
    common.audit(db, "exam_updated", user_id=user.id, entity_type="exam", entity_id=exam_id, after=changes)
    return exam


def set_topic_marks(
    db: Session,
    user: models.User,
    exam_id: int,
    topic_id: int,
    *,
    mark_kind: str = "planned",
    checked: bool = True,
    cascade: bool = True,
    subject_id: Optional[int] = None,
    question_from: Optional[int] = None,
    question_to: Optional[int] = None,
) -> dict:
    """Same cascade behaviour as 'taught': checking a chapter marks every descendant."""
    exam = db.get(models.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        raise NotFoundError("امتحان پیدا نشد.")
    if mark_kind not in {k.value for k in TopicMarkKind}:
        raise ValidationError("mark_kind باید planned یا actual باشد.")
    topic = db.get(models.Topic, topic_id)
    if not topic:
        raise NotFoundError("مبحث پیدا نشد.")
    targets = [topic_id]
    if cascade:
        targets.extend(
            db.scalars(select(models.Topic.id).where(models.Topic.path.like(f"{topic.path}{topic.id}/%")))
        )
    existing = {
        (row.topic_id, row.mark_kind): row
        for row in db.scalars(select(models.ExamTopic).where(models.ExamTopic.exam_id == exam_id))
    }
    changed = 0
    for target_id in targets:
        key = (target_id, mark_kind)
        row = existing.get(key)
        target_topic = db.get(models.Topic, target_id)
        target_subject = subject_id or (db.get(models.Book, target_topic.book_id).subject_id if target_topic else None)
        if row is None:
            row = models.ExamTopic(
                exam_id=exam_id,
                topic_id=target_id,
                mark_kind=mark_kind,
                checked=checked,
                subject_id=target_subject,
                question_from=question_from if target_id == topic_id else None,
                question_to=question_to if target_id == topic_id else None,
            )
            db.add(row)
        else:
            row.checked = checked
        changed += 1
    db.flush()
    common.observe(
        db, user.id, "exam_topic_marked",
        payload={"exam_id": exam_id, "topic_id": topic_id, "mark_kind": mark_kind, "checked": checked, "cascade": cascade},
        source="user",
    )
    return {
        "exam_id": exam_id,
        "topic_id": topic_id,
        "mark_kind": mark_kind,
        "checked": checked,
        "affected": len(targets),
        "note": "لایه planned و actual جدا نگه داشته می‌شوند.",
    }


def exam_topics(db: Session, exam_id: int, mark_kind: Optional[str] = None) -> dict:
    stmt = select(models.ExamTopic).where(models.ExamTopic.exam_id == exam_id, models.ExamTopic.checked.is_(True))
    if mark_kind:
        stmt = stmt.where(models.ExamTopic.mark_kind == mark_kind)
    rows = list(db.scalars(stmt))
    topics = {
        topic.id: topic
        for topic in db.scalars(select(models.Topic).where(models.Topic.id.in_([row.topic_id for row in rows] or [0])))
    }
    grouped: dict[str, list[dict]] = {"planned": [], "actual": []}
    for row in rows:
        topic = topics.get(row.topic_id)
        grouped.setdefault(row.mark_kind, []).append(
            {
                "topic_id": row.topic_id,
                "title": topic.title if topic else None,
                "parent_id": topic.parent_id if topic else None,
                "subject_id": row.subject_id,
                "question_from": row.question_from,
                "question_to": row.question_to,
            }
        )
    planned_ids = {row["topic_id"] for row in grouped.get("planned", [])}
    actual_ids = {row["topic_id"] for row in grouped.get("actual", [])}
    return {
        "planned": grouped.get("planned", []),
        "actual": grouped.get("actual", []),
        "comparison": {
            "planned_count": len(planned_ids),
            "actual_count": len(actual_ids),
            "covered_as_planned": len(planned_ids & actual_ids),
            "planned_not_in_actual": len(planned_ids - actual_ids),
            "actual_not_planned": len(actual_ids - planned_ids),
            "note": "پوشش برنامه‌ریزی‌شده و واقعی جدا هستند و با هم مقایسه می‌شوند.",
        },
    }


def exam_payload(db: Session, exam: models.Exam, *, detailed: bool = False) -> dict:
    days_left = (exam.exam_date - today_local()).days
    payload = {
        "id": exam.id,
        "title": exam.title,
        "exam_type": exam.exam_type,
        "type_label": exam_type_label(exam.exam_type),
        "type_hint": EXAM_TYPE_HINTS_FA.get(exam.exam_type),
        "provider": exam.provider,
        "source": exam.source or exam.provider,
        "subject_id": exam.subject_id,
        "subjects": exam.subjects or ([exam.subject_id] if exam.subject_id else []),
        "subject_titles": [row["title"] for row in _subject_titles(db, exam.subjects or ([exam.subject_id] if exam.subject_id else []))],
        "question_count": exam.question_count or exam.total_questions,
        "answer_key_count": answer_key_size(exam),
        "answer_key_source": exam.answer_key_source,
        "has_answer_key": bool(answer_key_size(exam)),
        "coverage_range": exam.coverage_range or {},
        "attempt_count": _attempt_count(db, exam.id),
        "date": common.jdate(exam.exam_date),
        "date_long": common.jdate_long(exam.exam_date),
        "weekday": common.weekday_fa(exam.exam_date),
        "days_left": days_left,
        "status": exam.status,
        "start_time": exam.start_time.strftime("%H:%M") if exam.start_time else None,
        "total_questions": exam.total_questions,
        "planned_question_count": exam.planned_question_count,
        "actual_question_count": exam.actual_question_count,
        "planned_duration_minutes": exam.planned_duration_minutes,
        "actual_duration_minutes": exam.actual_duration_minutes,
        "score": exam.score,
        "max_score": exam.max_score,
        "percentage": exam.percentage,
        "correct_count": exam.correct_count,
        "wrong_count": exam.wrong_count,
        "unanswered_count": exam.unanswered_count,
        "keep_for_retake": exam.keep_for_retake,
        "use_for_future_prep": exam.use_for_future_prep,
        "attempt_no": exam.attempt_no,
        "retake_of_id": exam.retake_of_id,
        "files": exam.files or [],
        "notes": exam.notes,
    }
    if detailed:
        payload["topics"] = exam_topics(db, exam.id)
        payload["attempts"] = [
            {
                "id": attempt.id,
                "attempt_no": attempt.attempt_no,
                "date": common.jdate(attempt.date),
                "duration_minutes": attempt.duration_minutes,
                "percentage": attempt.percentage,
                "correct_count": attempt.correct_count,
                "wrong_count": attempt.wrong_count,
                "unanswered_count": attempt.unanswered_count,
                "per_subject": attempt.per_subject,
                "question_count": attempt.question_count,
                "summary": attempt.summary or {},
                "note": attempt.note,
            }
            for attempt in db.scalars(
                select(models.ExamAttempt).where(models.ExamAttempt.exam_id == exam.id).order_by(models.ExamAttempt.attempt_no)
            )
        ]
    return payload


def list_exams(db: Session, user: models.User, *, exam_type: Optional[str] = None, upcoming_only: bool = False) -> list[dict]:
    stmt = select(models.Exam).where(models.Exam.user_id == user.id)
    if exam_type:
        stmt = stmt.where(models.Exam.exam_type == exam_type)
    if upcoming_only:
        stmt = stmt.where(models.Exam.exam_date >= today_local(), models.Exam.status.in_(["planned", "in_progress"]))
    rows = list(db.scalars(stmt.order_by(models.Exam.exam_date)))
    payload = [exam_payload(db, exam) for exam in rows]
    if not upcoming_only:
        payload.extend(_prep_linked(db, user))
    return payload


def _prep_linked(db: Session, user: models.User) -> list[dict]:
    """Upcoming exams that inherit preparation from a previous mock / retake."""
    upcoming = list(
        db.scalars(
            select(models.Exam).where(
                models.Exam.user_id == user.id,
                models.Exam.status.in_(["planned", "in_progress"]),
                models.Exam.exam_date >= today_local(),
            )
        )
    )
    linked = []
    for exam in upcoming:
        mocks = list(
            db.scalars(
                select(models.Exam).where(
                    models.Exam.user_id == user.id,
                    models.Exam.exam_type == ExamType.MOCK.value,
                    models.Exam.use_for_future_prep.is_(True),
                    models.Exam.id != exam.id,
                )
            )
        )
        exam_topics_set = {
            row.topic_id
            for row in db.scalars(
                select(models.ExamTopic).where(models.ExamTopic.exam_id == exam.id, models.ExamTopic.checked.is_(True))
            )
        }
        for mock in mocks:
            mock_topics = {
                row.topic_id
                for row in db.scalars(
                    select(models.ExamTopic).where(
                        models.ExamTopic.exam_id == mock.id,
                        models.ExamTopic.checked.is_(True),
                        models.ExamTopic.mark_kind == "actual",
                    )
                )
            }
            overlap = exam_topics_set & mock_topics
            if not overlap:
                continue
            weak = []
            for topic_id in overlap:
                state = db.scalars(
                    select(models.LearningState).where(
                        models.LearningState.user_id == user.id, models.LearningState.topic_id == topic_id
                    )
                ).first()
                readiness = state.exam_readiness if state and state.exam_readiness is not None else 0.0
                if readiness < 0.6:
                    weak.append({"topic_id": topic_id, "readiness": readiness})
            if weak:
                linked.append(
                    {
                        "id": f"prep-{exam.id}-{mock.id}",
                        "exam_type": "preparation_link",
                        "title": f"آماده‌سازی «{exam.title}» از روی {mock.title}",
                        "date": common.jdate(mock.exam_date),
                        "overlap_topics": len(overlap),
                        "weak_topics": weak[:5],
                        "suggested_questions": min(
                            config.value("recommendation.package_max_questions"), max(8, 2 * len(weak))
                        ),
                        "short_reason": (
                            f"{len(weak)} مبحث مشترک بین این امتحان و آزمون آزمایشی «{mock.title}» آمادگی پایینی دارد."
                        ),
                    }
                )
    return linked


# ---------------------------------------------------------------------------
# Mock exam sittings + post analysis
# ---------------------------------------------------------------------------


def record_attempt(db: Session, user: models.User, exam_id: int, payload: dict) -> dict:
    """Store one attempt of an exam — additively, with the answer key of *its own time*.

    V3.1 doc 03: attempts are history. A retake appends a row; it never overwrites an
    older attempt, and NOT_ENTERED (a sequence the student never filled) stays
    distinct from UNANSWERED (filled as «نزده»).
    """
    exam = _owned_exam(db, user, exam_id)
    answers = payload.get("answers") or {}
    if isinstance(answers, str):
        answers = normalize_answer_key(answers)
    per_subject = payload.get("per_subject") or {}
    duration = common.to_int(payload.get("duration_minutes") or payload.get("duration_spent"))
    score = common.to_float(payload.get("score"))
    max_score = common.to_float(payload.get("max_score")) or exam.max_score
    question_count = (
        common.to_int(payload.get("question_count") or payload.get("total_questions"))
        or exam.question_count
        or exam.total_questions
        or len(answers)
    )
    key = normalize_answer_key(payload.get("answer_key")) or normalize_answer_key(exam.answer_key)
    correct = wrong = unanswered = not_entered = not_evaluable = 0
    for sequence, value in answers.items():
        choice = value.get("choice") if isinstance(value, dict) else value
        choice = common.normalize_digits(str(choice if choice is not None else "")).strip()
        sequence_key = str(common.normalize_digits(str(sequence)).strip())
        if choice in ("0", "", "none", "null", "-", "خالی"):
            unanswered += 1
            continue
        expected = key.get(sequence_key)
        if expected is None:
            not_evaluable += 1          # no key for this question: pending correction, not wrong
        elif str(expected) == str(choice):
            correct += 1
        else:
            wrong += 1
    if question_count and question_count > len(answers):
        not_entered = question_count - len(answers)
    if not key and payload.get("correct_count") is not None:
        correct = common.to_int(payload.get("correct_count")) or 0
        wrong = common.to_int(payload.get("wrong_count")) or 0
        unanswered = common.to_int(payload.get("unanswered_count")) or 0
    evaluable = correct + wrong
    percentage = common.to_float(payload.get("percentage"))
    if percentage is None and evaluable:
        percentage = round(100 * correct / evaluable, 2)
    attempt_no = common.to_int(payload.get("attempt_no")) or (exam.attempt_no or 1)
    summary = {
        "per_subject": per_subject,
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "not_entered": not_entered,
        "not_evaluable": not_evaluable,
        "question_count": question_count,
        "answer_key_size": answer_key_size(exam),
        "note": "هر تلاش جداگانه ثبت می‌شود؛ نوبت جدید نتیجهٔ نوبت قبلی را بازنویسی نمی‌کند.",
    }
    attempt = models.ExamAttempt(
        exam_id=exam_id,
        user_id=user.id,
        attempt_no=attempt_no,
        date=common.parse_date_if_string(payload.get("date")) or today_local(),
        duration_minutes=duration,
        per_subject=per_subject,
        answers=answers,
        score=score,
        percentage=percentage,
        correct_count=correct,
        wrong_count=wrong,
        unanswered_count=unanswered,
        question_count=question_count,
        summary=summary,
        note=payload.get("note"),
    )
    db.add(attempt)
    exam.status = ExamStatus.COMPLETED.value
    exam.actual_question_count = question_count
    exam.actual_duration_minutes = duration
    exam.correct_count, exam.wrong_count, exam.unanswered_count = correct, wrong, unanswered
    exam.percentage = percentage
    exam.score = score
    if max_score:
        exam.max_score = max_score
    db.flush()
    common.observe(
        db, user.id, "exam_attempt_recorded",
        payload={"exam_id": exam_id, "attempt_no": attempt_no, "duration": duration, "percentage": percentage},
        source="user",
    )
    return {
        "attempt_id": attempt.id,
        "attempt_no": attempt_no,
        "percentage": percentage,
        "duration_minutes": duration,
        "summary": summary,
        "attempts_kept": _attempt_count(db, exam_id),
        "note": "نتیجهٔ این نوبت ذخیره شد؛ نوبت‌های قبلی دست‌نخورده مانده‌اند.",
    }


def post_analysis(db: Session, user: models.User, exam_id: int) -> dict:
    exam = db.get(models.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        raise NotFoundError("امتحان پیدا نشد.")
    attempts = list(
        db.scalars(select(models.ExamAttempt).where(models.ExamAttempt.exam_id == exam_id).order_by(models.ExamAttempt.attempt_no))
    )
    marks = exam_topics(db, exam_id)
    topic_ids = {row["topic_id"] for row in marks["planned"]} | {row["topic_id"] for row in marks["actual"]}
    breakdown = []
    prerequisite_flags = []
    for topic_id in topic_ids:
        state = db.scalars(
            select(models.LearningState).where(
                models.LearningState.user_id == user.id, models.LearningState.topic_id == topic_id
            )
        ).first()
        topic = db.get(models.Topic, topic_id)
        entry = {
            "topic_id": topic_id,
            "title": topic.title if topic else None,
            "coverage": state.coverage if state else None,
            "accuracy": state.accuracy if state else None,
            "attempts": state.attempts if state else 0,
            "readiness": state.exam_readiness if state else None,
            "in_planned": any(row["topic_id"] == topic_id for row in marks["planned"]),
            "in_actual": any(row["topic_id"] == topic_id for row in marks["actual"]),
        }
        breakdown.append(entry)
        if state and state.prerequisite_health is not None and state.prerequisite_health < 0.45:
            prerequisite_flags.append({"topic_id": topic_id, "title": entry["title"], "prerequisite_health": state.prerequisite_health})
    breakdown.sort(key=lambda item: (item["readiness"] if item["readiness"] is not None else 0))
    total_unanswered = sum(attempt.unanswered_count or 0 for attempt in attempts)
    total_questions = exam.actual_question_count or exam.total_questions or 0
    time_per_question = (
        round((exam.actual_duration_minutes or 0) * 60 / total_questions, 1) if total_questions and exam.actual_duration_minutes else None
    )
    return {
        "exam": exam_payload(db, exam),
        "attempts_trend": [
            {
                "attempt_no": attempt.attempt_no,
                "date": common.jdate(attempt.date),
                "percentage": attempt.percentage,
                "duration_minutes": attempt.duration_minutes,
            }
            for attempt in attempts
        ],
        "score": exam.score,
        "percentage": exam.percentage,
        "accuracy": (
            round((exam.correct_count or 0) / ((exam.correct_count or 0) + (exam.wrong_count or 0)), 3)
            if (exam.correct_count or 0) + (exam.wrong_count or 0)
            else None
        ),
        "unanswered": {
            "count": total_unanswered,
            "rate": round(total_unanswered / total_questions, 3) if total_questions else None,
            "signal": (
                "نرخ نزده بالا می‌تواند نشانه کمبود زمان، اعتماد یا آمادگی باشد — نه بی‌سوادی."
                if total_questions and total_unanswered / total_questions > 0.2 else "نرخ نزده در محدوده معمول است."
            ),
        },
        "time": {
            "planned_minutes": exam.planned_duration_minutes,
            "actual_minutes": exam.actual_duration_minutes,
            "seconds_per_question": time_per_question,
        },
        "topic_breakdown": breakdown,
        "planned_vs_actual": marks["comparison"],
        "topics": marks,
        "prerequisite_flags": prerequisite_flags,
        "error_signals": [
            {
                "code": "unanswered_pressure",
                "text": "سؤالات نزده زیاد: تمرین زمان‌دار کوتاه می‌تواند کمک کند.",
                "evidence": {"unanswered_rate": round(total_unanswered / total_questions, 3) if total_questions else None},
            }
        ] if total_questions and total_unanswered / total_questions > 0.2 else [],
        "next_actions": _next_actions(db, user, exam, breakdown),
    }


def _next_actions(db: Session, user: models.User, exam: models.Exam, breakdown: list[dict]) -> list[dict]:
    actions = []
    weakest = [row for row in breakdown if (row["readiness"] or 0) < 0.6][:3]
    for row in weakest:
        topic = db.get(models.Topic, row["topic_id"])
        actions.append(
            {
                "topic_id": row["topic_id"],
                "topic_title": topic.title if topic else None,
                "suggested": "diagnostic" if not row["attempts"] else "practice_or_review",
                "why": (
                    "هیچ شاهدی از این مبحث نداریم." if not row["attempts"]
                    else f"آمادگی تخمینی {round((row['readiness'] or 0) * 100)}٪ است."
                ),
            }
        )
    if exam.keep_for_retake:
        actions.append(
            {
                "topic_id": None,
                "suggested": "retake",
                "why": "این آزمون برای تمرین مجدد علامت خورده است؛ تکرار، روند را قابل مقایسه می‌کند.",
            }
        )
    return actions


# ---------------------------------------------------------------------------
# Exam Center (V3.1 doc 03): past with results · upcoming with preparation
# ---------------------------------------------------------------------------


def _weak_topics_from_exam(db: Session, exam: models.Exam, limit: int = 3) -> list[dict]:
    """Which marked topics did this exam actually go badly on?"""
    actual = list(
        db.scalars(
            select(models.ExamTopic).where(
                models.ExamTopic.exam_id == exam.id, models.ExamTopic.mark_kind == "actual"
            )
        )
    )
    planned = list(db.scalars(select(models.ExamTopic).where(models.ExamTopic.exam_id == exam.id)))
    rows = actual or planned
    weak: list[dict] = []
    for row in rows[:12]:
        if not row.topic_id:
            continue
        state = db.scalars(
            select(models.LearningState).where(
                models.LearningState.user_id == exam.user_id, models.LearningState.topic_id == row.topic_id
            )
        ).first()
        topic = db.get(models.Topic, row.topic_id)
        accuracy = state.accuracy if state and state.accuracy is not None else None
        coverage = state.coverage if state else None
        if accuracy is None and coverage is None:
            continue
        weak.append(
            {
                "topic_id": row.topic_id,
                "topic_title": topic.title if topic else None,
                "accuracy": round(accuracy, 3) if accuracy is not None else None,
                "coverage": round(coverage, 3) if coverage is not None else None,
                "reason": "دقت پایین در همین مبحث" if (accuracy or 1) < 0.5 else "پوشش ناقص",
            }
        )
    weak.sort(key=lambda item: ((item["accuracy"] if item["accuracy"] is not None else 1.0), item["coverage"] or 0))
    return weak[:limit]


def exam_center(db: Session, user: models.User) -> dict:
    """One screen for «گذشته | آینده | تحلیل»: no new model, just honest views."""
    today = today_local()
    exams = list(
        db.scalars(select(models.Exam).where(models.Exam.user_id == user.id).order_by(models.Exam.exam_date))
    )
    past: list[dict] = []
    upcoming: list[dict] = []
    for exam in exams:
        payload = exam_payload(db, exam, detailed=True)
        attempts = payload.get("attempts") or []
        if exam.exam_date < today or exam.status in {ExamStatus.COMPLETED.value, ExamStatus.ARCHIVED.value}:
            payload["result"] = {
                "attempts": len(attempts),
                "best_percentage": max(
                    [attempt["percentage"] for attempt in attempts if attempt.get("percentage") is not None],
                    default=None,
                ),
                "last_percentage": exam.percentage,
                "per_subject": attempts[-1]["per_subject"] if attempts else {},
                "correct": exam.correct_count,
                "wrong": exam.wrong_count,
                "unanswered": exam.unanswered_count,
            }
            payload["weaknesses"] = _weak_topics_from_exam(db, exam)
            breakdown = [
                {
                    "topic_id": item["topic_id"],
                    "readiness": item["accuracy"] if item["accuracy"] is not None else item["coverage"],
                    "attempts": 1 if item["accuracy"] is not None else 0,
                }
                for item in payload["weaknesses"]
            ]
            payload["follow_up"] = _next_actions(db, user, exam, breakdown)
            payload["retake_available"] = bool(exam.keep_for_retake)
            payload["keep_for_retake"] = bool(exam.keep_for_retake)
            past.append(payload)
        else:
            payload["days_left"] = (exam.exam_date - today).days
            payload["prep"] = {
                "days_left": payload["days_left"],
                "topics_marked": len(payload["topics"]["planned"]),
                "readiness": _readiness(db, exam),
                "test_suggestions": prep_test_suggestions(db, exam, limit=3),
                "next_action": _next_prep_action(db, exam),
            }
            payload["short_prep"] = prep_plan(db, user, exam.id, days=7)
            upcoming.append(payload)
    past.sort(key=lambda item: item["date"], reverse=True)
    upcoming.sort(key=lambda item: item["days_left"])
    return {
        "today": common.jdate(today),
        "past": past,
        "upcoming": upcoming,
        "counts": {"past": len(past), "upcoming": len(upcoming)},
        "types": [
            {"value": value, "label": EXAM_TYPE_LABELS_FA[value], "hint": EXAM_TYPE_HINTS_FA.get(value)}
            for value in EXAM_TYPE_LABELS_FA
        ],
        "policy": "گذشته فقط برای تحلیل است و آینده فقط برای آماده‌سازی؛ هیچ نتیجه‌ای بازنویسی نمی‌شود.",
    }


def _readiness(db: Session, exam: models.Exam) -> dict:
    """Coverage+accuracy of the marked topics, with the sample size behind it."""
    rows = list(
        db.scalars(
            select(models.ExamTopic).where(models.ExamTopic.exam_id == exam.id, models.ExamTopic.checked.is_(True))
        )
    )
    topic_ids = [row.topic_id for row in rows if row.topic_id]
    if not topic_ids:
        return {"value": None, "topic_count": 0, "evidence": "هنوز مبحثی برای این امتحان علامت نخورده است."}
    states = list(
        db.scalars(
            select(models.LearningState).where(
                models.LearningState.user_id == exam.user_id, models.LearningState.topic_id.in_(topic_ids)
            )
        )
    )
    if not states:
        return {
            "value": 0.0,
            "topic_count": len(topic_ids),
            "evidence": "مبحث علامت خورده است ولی هنوز تمرینی ثبت نشده؛ پس آمادگی صفر شمرده می‌شود، نه «بد».",
        }
    coverage = sum((state.coverage or 0) for state in states) / len(topic_ids)
    accuracy = sum((state.accuracy or 0) for state in states) / len(topic_ids)
    value = round(0.6 * coverage + 0.4 * accuracy, 3)
    return {
        "value": value,
        "coverage": round(coverage, 3),
        "accuracy": round(accuracy, 3),
        "topic_count": len(topic_ids),
        "attempt_topic_count": len(states),
        "evidence": f"{len(states)} مبحث از {len(topic_ids)} مبحث علامت‌خورده داده دارد؛ بقیه بدون داده‌اند.",
    }


def prep_test_suggestions(db: Session, exam: models.Exam, limit: int = 3) -> list[dict]:
    """A quiet test suggestion from the bank of the *same* topics (never a new exam)."""
    rows = list(
        db.scalars(
            select(models.ExamTopic).where(models.ExamTopic.exam_id == exam.id, models.ExamTopic.checked.is_(True))
        )
    )
    suggestions: list[dict] = []
    for row in rows[:limit]:
        if not row.topic_id:
            continue
        topic = db.get(models.Topic, row.topic_id)
        counts = _topic_question_counts(db, row.topic_id)
        if counts["total"] == 0:
            continue  # a topic without a question bank never enters a timed suggestion
        suggestions.append(
            {
                "topic_id": row.topic_id,
                "topic_title": topic.title if topic else None,
                "available": counts["total"],
                "suggested_count": min(counts["total"], 10),
                "reason": "از بانک تست همان مبحث امتحان؛ کم‌حجم و بدون فشار.",
            }
        )
    return suggestions


def _topic_question_counts(db: Session, topic_id: int) -> dict:
    from . import curriculum

    ids = curriculum.descendant_ids(db, topic_id) or [topic_id]
    total = db.scalar(select(func.count(models.Question.id)).where(models.Question.primary_topic_id.in_(ids))) or 0
    with_key = (
        db.scalar(
            select(func.count(models.Question.id)).where(
                models.Question.primary_topic_id.in_(ids), models.Question.current_answer_key.isnot(None)
            )
        )
        or 0
    )
    return {"total": total, "with_answer_key": with_key}


def _next_prep_action(db: Session, exam: models.Exam) -> dict:
    suggestions = prep_test_suggestions(db, exam, limit=1)
    if suggestions:
        item = suggestions[0]
        return {
            "kind": "quiet_test",
            "text": f"یک تست آرام از «{item['topic_title']}» ({item['suggested_count']} سؤال).",
            "evidence": f"{item['available']} سؤال در بانک این مبحث هست.",
        }
    return {
        "kind": "mark_topics",
        "text": "اول مباحث این امتحان را علامت بزن تا برنامهٔ آماده‌سازی ساخته شود.",
        "evidence": "بدون مبحث علامت‌خورده، پیشنهاد زمان‌دار ساخته نمی‌شود.",
    }


def prep_plan(db: Session, user: models.User, exam_id: int, days: Optional[int] = None) -> dict:
    """Multi-day preparation plan for an upcoming exam.

    Each day gets the weakest marked topics that actually have a question bank; the
    last days stay lighter (no cramming, no dumping of missed work) and every number
    carries its evidence.
    """
    exam = _owned_exam(db, user, exam_id)
    today = today_local()
    horizon = max(1, (exam.exam_date - today).days)
    window = int(days or horizon)
    window = max(1, min(window, 21))
    marked = list(
        db.scalars(
            select(models.ExamTopic).where(models.ExamTopic.exam_id == exam.id, models.ExamTopic.checked.is_(True))
        )
    )
    planned: list[dict] = []
    for row in marked:
        if not row.topic_id:
            continue
        counts = _topic_question_counts(db, row.topic_id)
        topic = db.get(models.Topic, row.topic_id)
        if counts["total"] == 0:
            continue
        state = db.scalars(
            select(models.LearningState).where(
                models.LearningState.user_id == user.id, models.LearningState.topic_id == row.topic_id
            )
        ).first()
        planned.append(
            {
                "topic_id": row.topic_id,
                "topic_title": topic.title if topic else None,
                "coverage": round(state.coverage, 3) if state and state.coverage is not None else 0.0,
                "accuracy": round(state.accuracy, 3) if state and state.accuracy is not None else None,
                "available_questions": counts["total"],
            }
        )
    planned.sort(key=lambda item: ((item["accuracy"] if item["accuracy"] is not None else 1.0), item["coverage"]))
    days_payload = []
    cursor = 0
    for offset in range(window):
        day = today + _dt.timedelta(days=offset)
        is_last = offset == window - 1
        per_day = 1 if is_last else 2
        chunk = planned[cursor : cursor + per_day]
        cursor += per_day
        if not chunk and cursor >= len(planned):
            chunk = planned[:1]
        minutes = 45 if not is_last else 30
        days_payload.append(
            {
                "date": common.jdate(day),
                "date_long": common.jdate_long(day),
                "weekday": common.weekday_fa(day),
                "days_to_exam": (exam.exam_date - day).days,
                "topics": chunk,
                "suggested_minutes": minutes,
                "note": "روز آخر سبک‌تر است؛ مرور فهرست‌وار، نه یادگیری تازه." if is_last else "تمرکز روی همان مباحث امتحان.",
            }
        )
    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "exam_type": exam.exam_type,
        "type_label": exam_type_label(exam.exam_type),
        "date": common.jdate(exam.exam_date),
        "date_long": common.jdate_long(exam.exam_date),
        "days_left": horizon,
        "window_days": window,
        "days": days_payload,
        "topic_count": len(planned),
        "excluded_topic_count": len(marked) - len(planned),
        "readiness": _readiness(db, exam),
        "test_suggestions": prep_test_suggestions(db, exam, limit=3),
        "policy": "آماده‌سازی چندروزه، کم‌حجم و فقط از مباحث همین امتحان؛ مبحث بدون بانک تست وارد برنامهٔ زمان‌دار نمی‌شود.",
    }


def create_retake(db: Session, user: models.User, exam_id: int, payload: dict) -> models.Exam:
    original = db.get(models.Exam, exam_id)
    if not original or original.user_id != user.id:
        raise NotFoundError("امتحان پیدا نشد.")
    retake = create_exam(
        db,
        user,
        {
            "exam_type": original.exam_type,
            "title": payload.get("title") or f"{original.title} — تکرار {(original.attempt_no or 1) + 1}",
            "provider": original.provider,
            # a retake keeps the same content but needs its own day: the user may
            # pass a new date, otherwise the original date is reused (never silent +N days)
            "exam_date": payload.get("exam_date") or payload.get("date") or original.exam_date,
            "start_time": payload.get("start_time") or original.start_time,
            "subject_id": original.subject_id,
            "total_questions": original.total_questions,
            "planned_question_count": original.planned_question_count,
            "planned_duration_minutes": original.planned_duration_minutes,
            "keep_for_retake": original.keep_for_retake,
            "use_for_future_prep": original.use_for_future_prep,
            "retake_of_id": original.id,
            "files": original.files,
        },
    )
    # copy the actual topic layer so the retake targets the same content
    for row in db.scalars(
        select(models.ExamTopic).where(models.ExamTopic.exam_id == original.id, models.ExamTopic.mark_kind == "actual")
    ):
        db.add(
            models.ExamTopic(
                exam_id=retake.id,
                topic_id=row.topic_id,
                mark_kind="planned",
                checked=row.checked,
                subject_id=row.subject_id,
                question_from=row.question_from,
                question_to=row.question_to,
            )
        )
    db.flush()
    common.audit(db, "mock_retake_created", user_id=user.id, entity_type="exam", entity_id=retake.id, after={"retake_of": original.id})
    return retake


def upcoming_exams(db: Session, user: models.User, days: int = 30) -> list[dict]:
    horizon = today_local() + _dt.timedelta(days=days)
    rows = list(
        db.scalars(
            select(models.Exam)
            .where(
                models.Exam.user_id == user.id,
                models.Exam.status.in_(["planned", "in_progress"]),
                models.Exam.exam_date >= today_local(),
                models.Exam.exam_date <= horizon,
            )
            .order_by(models.Exam.exam_date)
        )
    )
    return [exam_payload(db, exam) for exam in rows]


def exam_calendar(db: Session, user: models.User, start: _dt.date, end: _dt.date) -> dict:
    rows = list(
        db.scalars(
            select(models.Exam).where(
                models.Exam.user_id == user.id, models.Exam.exam_date >= start, models.Exam.exam_date <= end
            ).order_by(models.Exam.exam_date)
        )
    )
    return {
        "from": common.jdate(start),
        "to": common.jdate(end),
        "exams": [
            {
                "id": exam.id,
                "title": exam.title,
                "exam_type": exam.exam_type,
                "date": common.jdate(exam.exam_date),
                "day_index": (exam.exam_date - start).days,
                "status": exam.status,
                "needs_retake": exam.keep_for_retake,
                "topics_marked": db.scalar(
                    select(func.count(models.ExamTopic.id)).where(
                        models.ExamTopic.exam_id == exam.id, models.ExamTopic.checked.is_(True)
                    )
                ) or 0,
            }
            for exam in rows
        ],
    }
