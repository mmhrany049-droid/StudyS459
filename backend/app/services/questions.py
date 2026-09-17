"""Question bank: definitions, ranges, bulk four-choice answer keys, versioning.

The V2.2 documents describe the UX that used to be implemented badly, so the
service contract here is explicit:

* a topic owns one default ``TestSet`` per difficulty level;
* "افزودن بازه" creates question definitions with an *empty* answer key;
* the big four-choice list writes answer keys in one bulk call;
* correcting an answer key creates a new :class:`AnswerKeyVersion` and asks the
  recalculation engine to re-evaluate the affected attempts (never silent).
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Iterable, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..core.timeutil import now_utc
from ..db import models
from . import common

VALID_CHOICES = {"1", "2", "3", "4", ""}


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_questions(
    db: Session,
    *,
    book_id: int,
    topic_id: Optional[int] = None,
    level: Optional[int] = None,
    include_disabled: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
) -> dict:
    stmt = select(models.Question).where(models.Question.book_id == book_id)
    if topic_id:
        stmt = stmt.where(models.Question.primary_topic_id == topic_id)
    if level:
        stmt = stmt.where(models.Question.difficulty_level == level)
    if not include_disabled:
        stmt = stmt.where(models.Question.active.is_(True))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(models.Question.sequence_no).offset(offset)
    if limit:
        stmt = stmt.limit(limit)
    questions = list(db.scalars(stmt))
    question_ids = [q.id for q in questions]
    attempt_stats: dict[int, dict] = {}
    if question_ids:
        count_case = lambda value: func.sum(  # noqa: E731
            case((models.AttemptResult.result == value, 1), else_=0)
        )
        rows = db.execute(
            select(
                models.AttemptResult.question_id,
                func.count(models.AttemptResult.id),
                count_case("CORRECT"),
                count_case("WRONG"),
                count_case("UNANSWERED"),
            )
            .where(
                models.AttemptResult.question_id.in_(question_ids),
                models.AttemptResult.is_current.is_(True),
            )
            .group_by(models.AttemptResult.question_id)
        ).all()
        for question_id, attempts, correct, wrong, unanswered in rows:
            attempt_stats[question_id] = {
                "attempts": attempts or 0,
                "correct": correct or 0,
                "wrong": wrong or 0,
                "unanswered": unanswered or 0,
            }
    payload = [
        {
            "id": q.id,
            "sequence_no": q.sequence_no,
            "stable_key": q.stable_key,
            "topic_id": q.primary_topic_id,
            "test_set_id": q.test_set_id,
            "difficulty_level": q.difficulty_level,
            "answer_key": q.current_answer_key,
            "answer_key_version": q.current_answer_key_version,
            "has_answer_key": q.current_answer_key is not None,
            "active": q.active,
            "stats": attempt_stats.get(q.id, {"attempts": 0, "correct": 0, "wrong": 0, "unanswered": 0}),
        }
        for q in questions
    ]
    without_key = sum(1 for item in payload if not item["has_answer_key"])
    return {
        "total": total,
        "items": payload,
        "summary": {
            "total": total,
            "with_answer_key": total - without_key,
            "without_answer_key": without_key,
        },
    }


def question_history(db: Session, question_id: int) -> dict:
    question = db.get(models.Question, question_id)
    if not question:
        raise NotFoundError("سؤال پیدا نشد.")
    attempts = list(
        db.scalars(
            select(models.AttemptResult)
            .where(models.AttemptResult.question_id == question_id)
            .order_by(models.AttemptResult.evaluated_at.desc())
        )
    )
    versions = list(
        db.scalars(
            select(models.AnswerKeyVersion)
            .where(models.AnswerKeyVersion.question_id == question_id)
            .order_by(models.AnswerKeyVersion.version_no.desc())
        )
    )
    return {
        "question_id": question_id,
        "sequence_no": question.sequence_no,
        "current_answer_key": question.current_answer_key,
        "attempts": [
            {
                "id": a.id,
                "session_id": a.session_id,
                "state": a.state,
                "selected_choice": a.selected_choice,
                "answer_key": a.answer_key_value,
                "result": a.result,
                "is_current": a.is_current,
                "date": common.jdatetime(a.evaluated_at),
                "attempted_on": common.jdate(a.attempted_on),
                "source": a.source,
            }
            for a in attempts
        ],
        "answer_key_history": [
            {
                "version_no": v.version_no,
                "answer_key": v.answer_key,
                "reason": v.reason,
                "changed_by": v.changed_by,
                "created_at": common.jdatetime(v.created_at),
                "superseded_at": common.jdatetime(v.superseded_at),
            }
            for v in versions
        ],
    }


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _test_set_for(db: Session, book_id: int, topic_id: int, level: Optional[int]) -> models.TestSet:
    stmt = select(models.TestSet).where(
        models.TestSet.book_id == book_id, models.TestSet.topic_id == topic_id
    )
    if level is None:
        stmt = stmt.where(models.TestSet.difficulty_level.is_(None))
    else:
        stmt = stmt.where(models.TestSet.difficulty_level == level)
    test_set = db.scalars(stmt).first()
    if test_set:
        return test_set
    topic = db.get(models.Topic, topic_id)
    if not topic:
        raise NotFoundError("مبحث پیدا نشد.")
    test_set = models.TestSet(
        book_id=book_id,
        topic_id=topic_id,
        title=f"بانک تست — {topic.title}" + (f" (سطح {level})" if level else ""),
        test_type="normal",
        difficulty_level=level,
    )
    db.add(test_set)
    db.flush()
    return test_set


def add_question_range(
    db: Session,
    user: models.User,
    *,
    book_id: int,
    topic_id: int,
    seq_from: int,
    seq_to: int,
    level: Optional[int] = None,
    book_stable_prefix: Optional[str] = None,
) -> dict:
    if seq_from < 1 or seq_to < seq_from:
        raise ValidationError("بازه نامعتبر است. «از» باید کوچک‌تر یا مساوی «تا» باشد.")
    if seq_to - seq_from > 500:
        raise ValidationError("حداکثر ۵۰۰ شماره در هر بار قابل افزودن است.")
    topic = db.get(models.Topic, topic_id)
    if not topic or topic.book_id != book_id:
        raise NotFoundError("مبحث در این کتاب پیدا نشد.")
    book = db.get(models.Book, book_id)
    test_set = _test_set_for(db, book_id, topic_id, level)
    prefix = book_stable_prefix or book.stable_key
    existing_seq = {
        row for row in db.scalars(
            select(models.Question.sequence_no).where(models.Question.test_set_id == test_set.id)
        )
    }
    created = 0
    skipped = 0
    for sequence in range(seq_from, seq_to + 1):
        if sequence in existing_seq:
            skipped += 1
            continue
        stable_key = f"{prefix}:{topic_id}:L{level or 0}:{sequence}"
        db.add(
            models.Question(
                book_id=book_id,
                test_set_id=test_set.id,
                primary_topic_id=topic_id,
                stable_key=stable_key,
                sequence_no=sequence,
                difficulty_level=level,
                answer_type="four_choice",
                source="range",
            )
        )
        created += 1
    db.flush()
    common.audit(
        db,
        "question_range_added",
        user_id=user.id,
        entity_type="topic",
        entity_id=topic_id,
        after={"from": seq_from, "to": seq_to, "level": level, "created": created, "skipped": skipped},
    )
    common.observe(db, user.id, "question_range_added", payload={"topic_id": topic_id, "created": created}, source="user")
    return {"created": created, "skipped": skipped, "test_set_id": test_set.id, "from": seq_from, "to": seq_to}


def parse_compact_keys(text: str) -> dict[int, str]:
    """Accept '1:2,2:3,3:1' or the digit-by-digit form '23140' (0 = no answer)."""
    from ..core.jalali import normalize_digits

    normalized = normalize_digits(str(text or "").strip())
    if not normalized:
        return {}
    result: dict[int, str] = {}
    if ":" in normalized:
        for part in re.split(r"[,\s;]+", normalized):
            if not part:
                continue
            if ":" not in part:
                raise ValidationError(f"قطعه نامعتبر در پاسخ‌نامه: {part}")
            left, right = part.split(":", 1)
            try:
                sequence = int(left)
            except ValueError as exc:  # pragma: no cover - defensive
                raise ValidationError(f"شماره سؤال نامعتبر: {left}") from exc
            value = right.strip()
            if value in {"0", "-", "_", "x", "X", "بدون", "n"}:
                value = ""
            if value not in VALID_CHOICES:
                raise ValidationError(f"گزینه نامعتبر برای سؤال {sequence}: {right}")
            result[sequence] = value
        return result
    digits = re.sub(r"[^0-9]", "", normalized)
    for index, char in enumerate(digits, start=1):
        result[index] = "" if char == "0" else char
    return result


def set_answer_keys_bulk(
    db: Session,
    user: models.User,
    *,
    book_id: int,
    topic_id: int,
    items: Iterable[dict],
    reason: str = "bulk entry",
    level: Optional[int] = None,
) -> dict:
    """Bulk write of the four-choice answer key list (the mandatory V2.2 UX)."""
    topic = db.get(models.Topic, topic_id)
    if not topic or topic.book_id != book_id:
        raise NotFoundError("مبحث در این کتاب پیدا نشد.")
    by_sequence = {item["sequence_no"]: item.get("answer_key") for item in items if "sequence_no" in item}
    if not by_sequence:
        return {"updated": 0, "cleared": 0, "unchanged": 0, "recalc_required": []}
    stmt = select(models.Question).where(
        models.Question.book_id == book_id, models.Question.primary_topic_id == topic_id
    )
    if level:
        stmt = stmt.where(models.Question.difficulty_level == level)
    questions = {q.sequence_no: q for q in db.scalars(stmt)}
    updated = cleared = unchanged = 0
    recalc: list[int] = []
    for sequence, raw_value in by_sequence.items():
        question = questions.get(sequence)
        if question is None:
            continue
        value = "" if raw_value in (None, "", "0") else str(raw_value)
        if value and value not in VALID_CHOICES:
            raise ValidationError(f"گزینه {value} برای سؤال {sequence} مجاز نیست.")
        if value == (question.current_answer_key or ""):
            unchanged += 1
            continue
        if value:
            _apply_new_answer_key(db, question, value, reason=reason)
            updated += 1
        else:
            _apply_new_answer_key(db, question, None, reason="cleared")
            cleared += 1
        recalc.append(question.id)
    db.flush()
    common.observe(
        db, user.id, "answer_key_bulk_saved",
        payload={"topic_id": topic_id, "updated": updated, "cleared": cleared}, source="user",
    )
    return {"updated": updated, "cleared": cleared, "unchanged": unchanged, "recalc_required": recalc}


def set_answer_key(
    db: Session, user: models.User, question_id: int, answer_key: Optional[str], reason: str = "manual correction"
) -> dict:
    question = db.get(models.Question, question_id)
    if not question:
        raise NotFoundError("سؤال پیدا نشد.")
    value = None if answer_key in (None, "", "0") else str(answer_key)
    if value and value not in VALID_CHOICES:
        raise ValidationError("پاسخ صحیح باید یکی از گزینه‌های ۱ تا ۴ باشد.")
    before = question.current_answer_key
    if before == value:
        return {"question_id": question_id, "answer_key": value, "changed": False, "recalc_required": []}
    _apply_new_answer_key(db, question, value, reason=reason)
    db.flush()
    return {
        "question_id": question_id,
        "answer_key": value,
        "changed": True,
        "previous": before,
        "recalc_required": [question_id],
    }


def _apply_new_answer_key(
    db: Session, question: models.Question, value: Optional[str], *, reason: str, changed_by: str = "user"
) -> models.AnswerKeyVersion:
    """Append a new answer-key version, keep the old one for audit."""
    now = now_utc()
    previous = db.scalars(
        select(models.AnswerKeyVersion)
        .where(models.AnswerKeyVersion.question_id == question.id)
        .order_by(models.AnswerKeyVersion.version_no.desc())
    ).first()
    if previous and previous.superseded_at is None:
        previous.superseded_at = now
    version_no = (previous.version_no + 1) if previous else 1
    version = models.AnswerKeyVersion(
        question_id=question.id,
        version_no=version_no,
        answer_key=value if value is not None else "",
        reason=reason,
        changed_by=changed_by,
    )
    db.add(version)
    question.current_answer_key = value
    question.current_answer_key_version = version_no
    db.flush()
    common.audit(
        db,
        "answer_key_changed",
        entity_type="question",
        entity_id=question.id,
        reason=reason,
        before={"answer_key": previous.answer_key if previous else None, "version": version_no - 1},
        after={"answer_key": value, "version": version_no},
    )
    return version


def disable_question(db: Session, user: models.User, question_id: int, reason: Optional[str] = None) -> dict:
    """Soft delete: hard delete is forbidden once a question has history."""
    question = db.get(models.Question, question_id)
    if not question:
        raise NotFoundError("سؤال پیدا نشد.")
    has_history = db.scalar(
        select(func.count(models.AttemptResult.id)).where(models.AttemptResult.question_id == question_id)
    ) or 0
    question.active = False
    question.disabled_reason = reason or ("حذف نرم به دلیل وجود تاریخچه" if has_history else "غیرفعال شد")
    db.flush()
    common.audit(
        db, "question_disabled", user_id=user.id, entity_type="question", entity_id=question_id,
        after={"active": False, "had_history": bool(has_history)},
    )
    return {"question_id": question_id, "active": False, "had_history": bool(has_history)}


def enable_question(db: Session, question_id: int) -> dict:
    question = db.get(models.Question, question_id)
    if not question:
        raise NotFoundError("سؤال پیدا نشد.")
    question.active = True
    question.disabled_reason = None
    db.flush()
    return {"question_id": question_id, "active": True}


def coverage_of_topic(db: Session, user: models.User, topic_id: int) -> dict:
    """Coverage ≠ accuracy ≠ volume (V1 analytics rule, kept in V3)."""
    total = db.scalar(
        select(func.count(models.Question.id)).where(
            models.Question.primary_topic_id == topic_id, models.Question.active.is_(True)
        )
    ) or 0
    attempted = db.scalar(
        select(func.count(func.distinct(models.AttemptResult.question_id))).where(
            models.AttemptResult.user_id == user.id,
            models.AttemptResult.topic_id == topic_id,
            models.AttemptResult.is_current.is_(True),
        )
    ) or 0
    answered = db.scalar(
        select(func.count(models.AttemptResult.id)).where(
            models.AttemptResult.user_id == user.id,
            models.AttemptResult.topic_id == topic_id,
            models.AttemptResult.is_current.is_(True),
            models.AttemptResult.state == "ANSWERED",
        )
    ) or 0
    correct = db.scalar(
        select(func.count(models.AttemptResult.id)).where(
            models.AttemptResult.user_id == user.id,
            models.AttemptResult.topic_id == topic_id,
            models.AttemptResult.is_current.is_(True),
            models.AttemptResult.result == "CORRECT",
        )
    ) or 0
    return {
        "topic_id": topic_id,
        "target_question_count": total,
        "attempted_question_count": attempted,
        "coverage": (attempted / total) if total else None,
        "answered": answered,
        "correct": correct,
        "accuracy": (correct / answered) if answered else None,
    }
