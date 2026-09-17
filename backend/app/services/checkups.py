"""Checkup coverage ranges (V3.1 doc 03).

A chemistry checkup is **not** a single topic. The book's table of contents says it
explicitly («• آزمون چکاپ اول» between two segments), and V3.1 makes that the model:

    Checkup
    ├── coverage_range
    ├── start_after_topic / previous_checkup
    ├── end_before_topic / this_checkup
    └── included_topics[]   # از سگمنت قبلی تا قبل چکاپ فعلی

This module turns the parsed markers into :class:`models.CheckupCoverage` rows
(additively — an existing database only gains rows) and builds test sessions over
the whole segment instead of one topic.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..core.timeutil import today_local
from ..db import models
from ..domain.enums import SessionType
from . import common

CHEMISTRY_KEY = "chemistry2-mobtakeran"


def ensure_coverage_seeded(db: Session, book: Optional[models.Book] = None) -> dict:
    """Create the checkup coverage rows of a book from its TOC markers (idempotent)."""
    query = select(models.Book).where(models.Book.stable_key == CHEMISTRY_KEY)
    book = book or db.scalars(query).first()
    if book is None:
        return {"created": 0, "skipped": 0, "note": "کتاب شیمی در پایه داده وجود ندارد."}
    from ..db import seed_content

    parsed = seed_content.load_all()
    parsed_book = next((item for item in parsed if item.stable_key == CHEMISTRY_KEY), None)
    if parsed_book is None or not parsed_book.markers:
        return {"created": 0, "skipped": 0, "note": "نشانهٔ چکاپی در فهرست کتاب پیدا نشد."}

    topics = list(
        db.scalars(select(models.Topic).where(models.Topic.book_id == book.id).order_by(models.Topic.id))
    )
    by_title: dict[str, models.Topic] = {}
    for topic in topics:
        by_title.setdefault(topic.title.strip(), topic)

    created = skipped = 0
    previous_by_chapter: dict[str, models.CheckupCoverage] = {}
    for index, marker in enumerate(parsed_book.markers, start=1):
        exists = db.scalars(
            select(models.CheckupCoverage).where(
                models.CheckupCoverage.book_id == book.id, models.CheckupCoverage.order_index == index
            )
        ).first()
        if exists:
            skipped += 1
            previous_by_chapter[marker.chapter_title or ""] = exists
            continue
        included = [by_title[title.strip()] for title in marker.included_topics if title.strip() in by_title]
        chapter_topic = next(
            (
                topic
                for topic in topics
                if topic.node_type == "chapter"
                and marker.chapter_title
                and topic.title.strip() == marker.chapter_title.strip()
            ),
            None,
        )
        row = models.CheckupCoverage(
            user_id=None,
            book_id=book.id,
            chapter_topic_id=chapter_topic.id if chapter_topic else None,
            chapter_title=marker.chapter_title,
            kind=marker.kind,
            label=marker.label,
            order_index=index,
            scope=marker.scope,
            covered_from=marker.covered_from,
            covered_to=marker.covered_to,
            included_topic_ids=[topic.id for topic in included],
            included_topic_titles=[topic.title for topic in included],
            previous_checkup_id=(previous_by_chapter.get(marker.chapter_title or "") or None).id
            if previous_by_chapter.get(marker.chapter_title or "")
            else None,
            source_file=parsed_book.source_file,
        )
        db.add(row)
        db.flush()
        previous_by_chapter[marker.chapter_title or ""] = row
        created += 1
    db.flush()
    return {
        "created": created,
        "skipped": skipped,
        "book_id": book.id,
        "note": "چکاپ‌ها به‌صورت بازهٔ پوشش ذخیره می‌شوند؛ نه یک مبحث تکی.",
    }


def coverage_rows(db: Session, book_id: Optional[int] = None) -> list[models.CheckupCoverage]:
    stmt = select(models.CheckupCoverage)
    if book_id:
        stmt = stmt.where(models.CheckupCoverage.book_id == book_id)
    return list(db.scalars(stmt.order_by(models.CheckupCoverage.book_id, models.CheckupCoverage.order_index)))


def _topic_counts(db: Session, topic_ids: list[int]) -> dict:
    if not topic_ids:
        return {"questions": 0, "with_answer_key": 0}
    return {
        "questions": db.scalar(
            select(func.count(models.Question.id)).where(models.Question.primary_topic_id.in_(topic_ids))
        )
        or 0,
        "with_answer_key": db.scalar(
            select(func.count(models.Question.id)).where(
                models.Question.primary_topic_id.in_(topic_ids),
                models.Question.current_answer_key.isnot(None),
            )
        )
        or 0,
    }


def coverage_payload(db: Session, coverage: models.CheckupCoverage, user: Optional[models.User] = None) -> dict:
    topic_ids = [int(value) for value in (coverage.included_topic_ids or [])]
    topics = (
        list(db.scalars(select(models.Topic).where(models.Topic.id.in_(topic_ids)).order_by(models.Topic.id)))
        if topic_ids
        else []
    )
    counts = _topic_counts(db, topic_ids)
    states = []
    if user and topic_ids:
        states = list(
            db.scalars(
                select(models.LearningState).where(
                    models.LearningState.user_id == user.id, models.LearningState.topic_id.in_(topic_ids)
                )
            )
        )
    by_topic = {state.topic_id: state for state in states}
    coverage_ratio = (
        sum((state.coverage or 0) for state in states) / len(topic_ids) if topic_ids and states else 0.0
    )
    previous = db.get(models.CheckupCoverage, coverage.previous_checkup_id) if coverage.previous_checkup_id else None
    sessions = (
        list(
            db.scalars(
                select(models.TestSession).where(
                    models.TestSession.coverage_id == coverage.id,
                    *([models.TestSession.user_id == user.id] if user else []),
                )
            )
        )
        if True
        else []
    )
    return {
        "id": coverage.id,
        "book_id": coverage.book_id,
        "label": coverage.label,
        "kind": coverage.kind,
        "scope": coverage.scope,
        "order_index": coverage.order_index,
        "chapter_topic_id": coverage.chapter_topic_id,
        "chapter_title": coverage.chapter_title,
        "start_after_topic": previous.label if previous else coverage.covered_from,
        "end_before_topic": coverage.label,
        "previous_checkup_id": coverage.previous_checkup_id,
        "covered_from": coverage.covered_from,
        "covered_to": coverage.covered_to,
        "topic_count": len(topic_ids),
        "included_topic_ids": topic_ids,
        "included_topic_titles": coverage.included_topic_titles or [],
        "topics": [
            {
                "topic_id": topic.id,
                "title": topic.title,
                "coverage": round((by_topic[topic.id].coverage or 0), 3) if topic.id in by_topic else None,
                "accuracy": round((by_topic[topic.id].accuracy or 0), 3)
                if topic.id in by_topic and by_topic[topic.id].accuracy is not None
                else None,
                "evidence": "داده دارد" if topic.id in by_topic else "هنوز تمرینی ثبت نشده",
            }
            for topic in topics
        ],
        "question_bank": counts,
        "coverage_ratio": round(coverage_ratio, 3),
        "exam_id": coverage.exam_id,
        "sessions": len(sessions),
        "is_range": len(topic_ids) > 1,
        "note": "چکاپ یک بازهٔ پوشش است: از بعد از چکاپ قبلی تا قبل از این چکاپ.",
    }


def list_coverages(db: Session, user: models.User, book_id: Optional[int] = None) -> dict:
    ensure_coverage_seeded(db)
    rows = coverage_rows(db, book_id)
    payload = [coverage_payload(db, row, user) for row in rows]
    single = [item for item in payload if not item["is_range"]]
    return {
        "checkups": payload,
        "counts": {
            "total": len(payload),
            "ranges": len([item for item in payload if item["is_range"]]),
            "single_topic": len(single),
        },
        "single_topic_warning": (
            "چکاپ‌های تک‌مبحثی با مدل V3.1 سازگار نیستند؛ بازهٔ پوشش را بررسی کن."
            if single
            else None
        ),
        "note": "مدل چکاپ = بازهٔ پوشش چند مبحث؛ آزمون یک مبحث تکی چکاپ نیست.",
    }


def build_coverage_session(db: Session, user: models.User, coverage_id: int, payload: dict) -> dict:
    """Create one test session over the whole coverage segment (multiple topics).

    Questions are drawn per topic so the session really measures the segment; the
    session row carries ``coverage_id`` + ``coverage_topic_ids`` and the response
    sheet is materialised exactly like a live session (so UNANSWERED stays explicit).
    """
    from . import sessions as sessions_service

    coverage = db.get(models.CheckupCoverage, coverage_id)
    if coverage is None:
        raise NotFoundError("چکاپ پیدا نشد.")
    topic_ids = [int(value) for value in (coverage.included_topic_ids or [])]
    if not topic_ids:
        raise ValidationError("این چکاپ بازهٔ مبحثی ندارد؛ ابتدا فهرست کتاب را دوباره بخوان.")
    requested = common.to_int(payload.get("count")) or 20
    per_topic = max(1, requested // len(topic_ids))

    picked: list[models.Question] = []
    seen: set[int] = set()
    per_topic_counts: dict[int, int] = {}
    skipped_topics: list[dict] = []
    for topic_id in topic_ids:
        pool = sessions_service.candidate_pool(
            db, user, topic_id=topic_id, parity=payload.get("parity") or "any"
        )
        if not pool:
            # a segment topic whose bank is not built yet is reported, never faked:
            # the whole checkup is not cancelled because one topic is empty
            per_topic_counts[topic_id] = 0
            skipped_topics.append({"topic_id": topic_id, "why": "بدون سؤال در بانک"})
            continue
        take = min(per_topic, len(pool))
        chosen = sessions_service.select_questions(
            db, user, count=take, topic_id=topic_id, parity=payload.get("parity") or "any"
        )
        per_topic_counts[topic_id] = len(chosen)
        for question in chosen:
            if question.id not in seen:
                seen.add(question.id)
                picked.append(question)
    if not picked:
        raise ValidationError("برای مباحث این چکاپ هنوز سؤالی در بانک نیست؛ اول تست اضافه کن.")

    from . import duration as duration_service  # local import avoids a cycle

    estimate = duration_service.estimate_for_task(
        db,
        user,
        task_type=SessionType.CHECKUP.value,
        question_count=len(picked),
        book_id=coverage.book_id,
        topic_id=topic_ids[0],
        intervention="MIXED_PRACTICE",
    )
    session = models.TestSession(
        user_id=user.id,
        session_type=SessionType.CHECKUP.value,
        book_id=coverage.book_id,
        topic_id=topic_ids[0] if len(topic_ids) == 1 else None,
        coverage_id=coverage.id,
        coverage_topic_ids=topic_ids,
        intervention_type="MIXED_PRACTICE",
        planned_question_count=len(picked),
        planned_duration_low=estimate["low_minutes"],
        planned_duration_high=estimate["high_minutes"],
        planned_date=today_local(),
        status="planned",
        source="checkup_coverage",
        notes=f"چکاپ بازه‌ای: {coverage.label} ({len(topic_ids)} مبحث)",
    )
    db.add(session)
    db.flush()
    for order, question in enumerate(picked, start=1):
        db.add(
            models.SessionQuestion(
                session_id=session.id,
                question_id=question.id,
                display_order=order,
                selection_reason=f"checkup segment: {coverage.label}",
            )
        )
    sheet = models.ResponseSheet(session_id=session.id, user_id=user.id, status="open", entry_mode="live")
    db.add(sheet)
    db.flush()
    for question in picked:
        db.add(
            models.ResponseEntry(
                response_sheet_id=sheet.id,
                question_id=question.id,
                state="UNANSWERED",
                selected_choice=None,
                entry_source="live",
            )
        )
    db.flush()
    common.observe(
        db,
        user.id,
        "checkup_session_built",
        payload={"coverage_id": coverage.id, "topics": len(topic_ids), "questions": len(picked)},
        source="user",
    )
    return {
        "coverage_id": coverage.id,
        "label": coverage.label,
        "session_id": session.id,
        "topic_count": len(topic_ids),
        "topics_with_questions": len([value for value in per_topic_counts.values() if value]),
        "questions": len(picked),
        "per_topic": per_topic_counts,
        "skipped_topics": skipped_topics,
        "skipped_note": (
            "بعضی مباحث بازه هنوز بانک تست ندارند؛ پوشش همان‌ها در نتیجه لحاظ نمی‌شود."
            if skipped_topics
            else None
        ),
        "planned_duration_low": session.planned_duration_low,
        "planned_duration_high": session.planned_duration_high,
        "note": "این جلسه فقط یک مبحث را پوشش نمی‌دهد؛ بازهٔ کامل چکاپ را می‌سنجد.",
    }


def link_exam(db: Session, user: models.User, coverage_id: int, payload: dict) -> dict:
    """Create (or reuse) the checkup Exam of this coverage range and mark its topics."""
    from . import exams as exams_service

    coverage = db.get(models.CheckupCoverage, coverage_id)
    if coverage is None:
        raise NotFoundError("چکاپ پیدا نشد.")
    topic_ids = [int(value) for value in (coverage.included_topic_ids or [])]
    exam = None
    if coverage.exam_id:
        exam = db.get(models.Exam, coverage.exam_id)
    if exam is None:
        exam = exams_service.create_exam(
            db,
            user,
            {
                "title": payload.get("title") or coverage.label,
                "exam_type": "checkup",
                "date": payload.get("date"),
                "source": "چکاپ کتاب",
                "question_count": payload.get("question_count") or len(topic_ids) * 5,
                "coverage_range": {
                    "checkup_id": coverage.id,
                    "label": coverage.label,
                    "covered_from": coverage.covered_from,
                    "covered_to": coverage.covered_to,
                    "included_topic_ids": topic_ids,
                },
            },
        )
        coverage.exam_id = exam.id
    marked = []
    for topic_id in topic_ids:
        result = exams_service.set_topic_marks(
            db, user, exam.id, topic_id, mark_kind="planned", checked=True, cascade=False
        )
        marked.append(result.get("topic_id"))
    db.flush()
    return {
        "exam_id": exam.id,
        "coverage_id": coverage.id,
        "topics_marked": len(marked),
        "date": common.jdate(exam.exam_date),
        "note": "همهٔ مباحث بازهٔ چکاپ روی همین آزمون علامت خوردند.",
    }


def coverage_progress(db: Session, user: models.User, coverage_id: int) -> dict:
    coverage = db.get(models.CheckupCoverage, coverage_id)
    if coverage is None:
        raise NotFoundError("چکاپ پیدا نشد.")
    payload = coverage_payload(db, coverage, user)
    weak = [
        item
        for item in payload["topics"]
        if (item["coverage"] is None) or (item["coverage"] or 0) < 0.6
    ]
    payload["weak_in_range"] = [
        {"topic_id": item["topic_id"], "title": item["title"], "why": "پوشش کمتر از ۶۰٪ یا بدون داده"}
        for item in weak[:5]
    ]
    payload["next_step"] = (
        "یک جلسهٔ چکاپ روی همین بازه بساز."
        if payload["question_bank"]["questions"] >= len(coverage.included_topic_ids or [])
        else "برای مباحث این بازه اول بانک تست بساز؛ بدون سؤال، سنجش معنی ندارد."
    )
    return payload
