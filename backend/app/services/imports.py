"""Historical import — "I already solved these before the app".

The V2.2 UX contract, implemented literally:

1 the user picks only a **book**;
2 the system shows one big list of that book's questions grouped by chapter/topic;
3 for every row exactly one of: option 1..4, or an explicit **نزده (unanswered)**;
4 the final submit creates attempts for the rows the user touched.

Rules kept from V2: ``is_imported = true``, no coins, append-only attempts,
wrong/unanswered rows enter the review queue, results are computed against the
answer key when it exists — otherwise the row is honestly *pending correction*.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..core.timeutil import now_utc, today_local
from ..db import models
from ..domain.enums import AnswerState, SessionStatus, SessionType
from . import common, learning, review, sessions as sessions_service

MAX_ITEMS_PER_IMPORT = 600


def book_import_sheet(db: Session, user: models.User, book_id: int, *, topic_id: Optional[int] = None) -> dict:
    """The big list: book → chapter → topic, with each question's current state."""
    book = db.get(models.Book, book_id)
    if not book:
        raise NotFoundError("کتاب پیدا نشد.")
    stmt = select(models.Topic).where(models.Topic.book_id == book_id).order_by(models.Topic.path, models.Topic.order_index)
    topics = list(db.scalars(stmt))
    by_parent: dict[Optional[int], list[models.Topic]] = {}
    for topic in topics:
        by_parent.setdefault(topic.parent_id, []).append(topic)
    question_stmt = select(models.Question).where(models.Question.book_id == book_id, models.Question.active.is_(True))
    if topic_id:
        question_stmt = question_stmt.where(models.Question.primary_topic_id == topic_id)
    questions = list(db.scalars(question_stmt.order_by(models.Question.sequence_no)))
    per_topic: dict[int, list[models.Question]] = {}
    for question in questions:
        per_topic.setdefault(question.primary_topic_id or 0, []).append(question)

    # previous responses (so the sheet can show what is already known)
    existing = {
        row.question_id: row
        for row in db.scalars(
            select(models.AttemptResult).where(
                models.AttemptResult.user_id == user.id,
                models.AttemptResult.question_id.in_([q.id for q in questions] or [0]),
                models.AttemptResult.is_current.is_(True),
            )
        )
    }
    chapters = []
    for chapter in by_parent.get(None, []):
        chapter_children = _flatten(by_parent, chapter.id)
        chapter_questions = [
            question for topic in chapter_children for question in per_topic.get(topic.id, [])
        ]
        if not chapter_questions:
            continue
        chapters.append(
            {
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "groups": [
                    {
                        "topic_id": topic.id,
                        "topic_title": topic.title,
                        "node_type": topic.node_type,
                        "questions": [
                            {
                                "question_id": question.id,
                                "sequence_no": question.sequence_no,
                                "difficulty_level": question.difficulty_level,
                                "has_answer_key": bool(question.current_answer_key),
                                "previous_state": existing[question.id].state if question.id in existing else None,
                                "previous_choice": existing[question.id].selected_choice if question.id in existing else None,
                                "previous_result": existing[question.id].result if question.id in existing else None,
                            }
                            for question in per_topic.get(topic.id, [])
                        ],
                    }
                    for topic in chapter_children
                    if per_topic.get(topic.id)
                ],
                "question_count": len(chapter_questions),
            }
        )
    return {
        "book": {"id": book.id, "title": book.title, "publisher": book.publisher},
        "chapters": chapters,
        "total_questions": len(questions),
        "instructions": [
            "برای هر سؤال یکی از گزینه‌های ۱ تا ۴ یا «نزده» را انتخاب کن.",
            "ردیف‌هایی که دست نمی‌زنی «ثبت‌نشده» می‌مانند، نه غلط و نه درست.",
            "committed سکه ندارد، چون کار گذشته است.",
        ],
        "states": {
            "ANSWERED": "پاسخ داده‌شده",
            "UNANSWERED": "نزده (صریح)",
            "NOT_ENTERED": "ثبت‌نشده",
        },
    }


def _flatten(by_parent: dict, root_id: int) -> list[models.Topic]:
    result = []
    stack = [root_id]
    while stack:
        current = stack.pop()
        for child in by_parent.get(current, []):
            result.append(child)
            stack.append(child.id)
    return result


def import_attempts(
    db: Session,
    user: models.User,
    *,
    book_id: int,
    items: list[dict],
    date_value: Optional[_dt.date] = None,
    topic_id: Optional[int] = None,
    note: Optional[str] = None,
    import_key: Optional[str] = None,
) -> dict:
    if not items:
        raise ValidationError("هیچ ردیفی برای ثبت وجود ندارد.")
    if len(items) > MAX_ITEMS_PER_IMPORT:
        raise ValidationError(f"حداکثر {MAX_ITEMS_PER_IMPORT} ردیف در هر بار ثبت قابل قبول است.")
    book = db.get(models.Book, book_id)
    if not book:
        raise NotFoundError("کتاب پیدا نشد.")
    day = date_value or today_local()
    if import_key is None:
        # stable (not salted) digest so the same import can never be applied twice
        fingerprint = hashlib.md5(
            repr(sorted((common.to_int(i.get("question_id")), i.get("choice"), bool(i.get("unanswered"))) for i in items)).encode("utf-8")
        ).hexdigest()[:12]
        import_key = f"book:{book_id}:{day.isoformat()}:{fingerprint}"
    # sessions are stored per topic group (suffix `:topic:<id>`), so the duplicate
    # check must match the whole family of keys produced by this import
    duplicate = db.scalars(
        select(models.TestSession).where(models.TestSession.import_key.like(f"{import_key}:topic:%"))
    ).first()
    if duplicate:
        raise ConflictError(
            "این ورود قبلاً ثبت شده است؛ برای جلوگیری از دوباره‌شماری وارد نشد.",
            details={"session_id": duplicate.id, "import_key": import_key},
        )

    question_ids = [common.to_int(item.get("question_id")) for item in items]
    questions = {
        question.id: question
        for question in db.scalars(
            select(models.Question).where(models.Question.book_id == book_id, models.Question.id.in_(question_ids or [0]))
        )
    }
    if not questions:
        raise ValidationError("هیچ سؤال معتبری در این کتاب پیدا نشد.")
    # one imported session per topic group so the history stays readable
    grouped: dict[Optional[int], list[dict]] = {}
    for item in items:
        question = questions.get(common.to_int(item.get("question_id")))
        if question is None:
            continue
        grouped.setdefault(question.primary_topic_id, []).append({"item": item, "question": question})

    created_sessions = []
    created_attempts = 0
    answered = wrong = unanswered = not_evaluable = 0
    for topic_id_group, rows in grouped.items():
        session = models.TestSession(
            user_id=user.id,
            session_type=SessionType.IMPORTED.value,
            book_id=book_id,
            topic_id=topic_id_group,
            planned_date=day,
            status=SessionStatus.IN_PROGRESS.value,
            is_imported=True,
            import_key=f"{import_key}:topic:{topic_id_group}",
            source="historical_import",
            planned_question_count=len(rows),
            notes=note,
        )
        db.add(session)
        db.flush()
        sheet = models.ResponseSheet(
            session_id=session.id, user_id=user.id, status="open", entry_mode="historical_import"
        )
        db.add(sheet)
        db.flush()
        for order, row in enumerate(rows):
            question = row["question"]
            item = row["item"]
            db.add(
                models.SessionQuestion(
                    session_id=session.id, question_id=question.id, display_order=order,
                    selection_reason="ورود گذشته",
                )
            )
            choice = item.get("choice")
            is_unanswered = bool(item.get("unanswered"))
            if choice is not None and is_unanswered:
                raise ValidationError("هم گزینه و هم «نزده» برای یک سؤال مجاز نیست.")
            if is_unanswered:
                state, selected = AnswerState.UNANSWERED.value, None
                unanswered += 1
            elif choice in (None, "", "0"):
                state, selected = AnswerState.NOT_ENTERED.value, None
            else:
                selected = str(choice)
                state = AnswerState.ANSWERED.value
                answered += 1
                if question.current_answer_key and selected != str(question.current_answer_key):
                    wrong += 1
            db.add(
                models.ResponseEntry(
                    response_sheet_id=sheet.id,
                    question_id=question.id,
                    state=state,
                    selected_choice=selected,
                    entry_source="historical_import",
                    entered_at=now_utc(),
                    note=item.get("note"),
                )
            )
        db.flush()
        result = sessions_service.finish_session(db, user, session.id)
        not_evaluable += result.get("not_evaluable", 0)
        created_sessions.append(session.id)
        created_attempts += result.get("total", 0)
    db.flush()
    common.audit(
        db, "historical_import", user_id=user.id, entity_type="book", entity_id=book_id,
        after={
            "sessions": created_sessions,
            "attempts": created_attempts,
            "import_key": import_key,
            "coins": 0,
        },
    )
    common.observe(
        db, user.id, "historical_import",
        payload={"book_id": book_id, "questions": created_attempts, "sessions": created_sessions},
        source="user",
    )
    learning.rebuild_all(db, user)
    review_stats = review.queue_stats(db, user)
    return {
        "sessions": created_sessions,
        "attempts": created_attempts,
        "answered": answered,
        "wrong": wrong,
        "unanswered": unanswered,
        "not_evaluable": not_evaluable,
        "pending_correction": not_evaluable > 0,
        "coins": 0,
        "review_queue": review_stats,
        "note": "ورود گذشته سکه ندارد و attemptها append-only هستند؛ هیچ نتیجه‌ای overwrite نمی‌شود.",
    }


def import_summary(db: Session, user: models.User) -> dict:
    sessions = list(
        db.scalars(
            select(models.TestSession).where(
                models.TestSession.user_id == user.id, models.TestSession.is_imported.is_(True)
            )
        )
    )
    attempts = db.scalar(
        select(func.count(models.AttemptResult.id)).where(
            models.AttemptResult.user_id == user.id,
            models.AttemptResult.source == "historical_import",
            models.AttemptResult.is_current.is_(True),
        )
    ) or 0
    not_entered = db.scalar(
        select(func.count(models.AttemptResult.id)).where(
            models.AttemptResult.user_id == user.id,
            models.AttemptResult.state == AnswerState.NOT_ENTERED.value,
            models.AttemptResult.is_current.is_(True),
        )
    ) or 0
    return {
        "sessions": len(sessions),
        "attempts": attempts,
        "not_entered": not_entered,
        "last_import_dates": [
            common.jdate(session.planned_date)
            for session in sorted(sessions, key=lambda s: s.id, reverse=True)[:5]
        ],
        "note": "«ثبت‌نشده» با «نزده» یکی نیست؛ هر دو جدا شمرده می‌شوند.",
    }
