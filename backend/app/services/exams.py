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
from ..domain.enums import ExamStatus, ExamType, TopicMarkKind
from . import common

MODEL_VERSION = config.MODEL_VERSION


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_exam(db: Session, user: models.User, payload: dict) -> models.Exam:
    exam_type = payload.get("exam_type", ExamType.SCHOOL.value)
    if exam_type not in {t.value for t in ExamType}:
        raise ValidationError("نوع امتحان باید school یا mock باشد.")
    exam_date = common.parse_date_if_string(payload.get("exam_date"))
    if not exam_date:
        raise ValidationError("تاریخ امتحان لازم است.")
    retake_of = common.to_int(payload.get("retake_of_id"))
    attempt_no = 1
    if retake_of:
        parent = db.get(models.Exam, retake_of)
        if parent and parent.user_id == user.id:
            attempt_no = (parent.attempt_no or 1) + 1
    exam = models.Exam(
        user_id=user.id,
        exam_type=exam_type,
        title=payload.get("title") or "امتحان",
        subject_id=common.to_int(payload.get("subject_id")),
        provider=payload.get("provider"),
        exam_date=exam_date,
        start_time=payload.get("start_time"),
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
    }
    for key, attribute in mapping.items():
        if key in changes:
            setattr(exam, attribute, changes[key])
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
        "provider": exam.provider,
        "subject_id": exam.subject_id,
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
    exam = db.get(models.Exam, exam_id)
    if not exam or exam.user_id != user.id:
        raise NotFoundError("امتحان پیدا نشد.")
    answers = payload.get("answers") or {}
    per_subject = payload.get("per_subject") or {}
    duration = common.to_int(payload.get("duration_minutes"))
    score = common.to_float(payload.get("score"))
    max_score = common.to_float(payload.get("max_score")) or exam.max_score
    total_questions = common.to_int(payload.get("total_questions")) or exam.total_questions or len(answers)
    correct = wrong = unanswered = 0
    key = payload.get("answer_key") or {}
    for sequence, value in answers.items():
        choice = value.get("choice") if isinstance(value, dict) else value
        if choice in (None, "", "0"):
            unanswered += 1
        elif key and str(key.get(str(sequence))) == str(choice):
            correct += 1
        elif key:
            wrong += 1
    if not key:
        correct = common.to_int(payload.get("correct_count")) or 0
        wrong = common.to_int(payload.get("wrong_count")) or 0
        unanswered = common.to_int(payload.get("unanswered_count")) or 0
    percentage = common.to_float(payload.get("percentage"))
    if percentage is None and total_questions and (correct or wrong):
        percentage = round(100 * correct / total_questions, 2)
    attempt_no = common.to_int(payload.get("attempt_no")) or (exam.attempt_no or 1)
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
        note=payload.get("note"),
    )
    db.add(attempt)
    exam.status = ExamStatus.COMPLETED.value
    exam.actual_question_count = total_questions
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
    return {"attempt_id": attempt.id, "attempt_no": attempt_no, "percentage": percentage, "duration_minutes": duration}


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
            "exam_date": payload.get("exam_date"),
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
