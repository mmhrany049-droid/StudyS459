"""Question bank router — the mandatory per-topic bank UX lives here."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db.base import get_db
from ...db import models
from ...services import common, questions, recalculation, selection
from ..deps import current_user

router = APIRouter(tags=["question-bank"])


class RangePayload(BaseModel):
    from_sequence: int | None = None
    to_sequence: int | None = None
    level: int | None = None
    # tolerate the terse names used by the UI / the Grok compact formats
    from_: int | None = None
    to: int | None = None
    seq_from: int | None = None
    seq_to: int | None = None


class AnswerKeyItem(BaseModel):
    sequence_no: int
    answer_key: str | None = None


class BulkAnswerKeyPayload(BaseModel):
    items: list[AnswerKeyItem] = []
    reason: str = "ورود گروهی پاسخ‌نامه"
    level: int | None = None


class CompactPayload(BaseModel):
    text: str
    level: int | None = None
    apply: bool = True


class AnswerKeySinglePayload(BaseModel):
    answer_key: str | None = None
    reason: str = "اصلاح دستی پاسخ‌نامه"


@router.get("/books/{book_id}/nodes/{topic_id}/questions")
def list_questions(
    book_id: int,
    topic_id: int,
    level: int | None = None,
    limit: int | None = Query(None, le=2000),
    offset: int = 0,
    include_disabled: bool = False,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    return questions.list_questions(
        db, book_id=book_id, topic_id=topic_id, level=level, limit=limit, offset=offset, include_disabled=include_disabled
    )


@router.post("/books/{book_id}/nodes/{topic_id}/questions/range")
def add_range(
    book_id: int,
    topic_id: int,
    payload: RangePayload,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    start = payload.from_sequence or payload.from_ or payload.seq_from
    end = payload.to_sequence or payload.to or payload.seq_to
    result = questions.add_question_range(
        db, user, book_id=book_id, topic_id=topic_id, seq_from=int(start or 0), seq_to=int(end or 0), level=payload.level
    )
    db.commit()
    return result


@router.put("/books/{book_id}/nodes/{topic_id}/answer-key")
def bulk_answer_key(
    book_id: int,
    topic_id: int,
    payload: BulkAnswerKeyPayload,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = questions.set_answer_keys_bulk(
        db,
        user,
        book_id=book_id,
        topic_id=topic_id,
        items=[item.model_dump() for item in payload.items],
        reason=payload.reason,
        level=payload.level,
    )
    recalc = []
    for question_id in result.get("recalc_required", [])[:200]:
        recalc.append(question_id)
    if recalc:
        recalculation.recalculate(db, user, scope="topic", scope_id=topic_id, trigger="answer_key_bulk", incremental=True)
    db.commit()
    return {**result, "recalculated_questions": len(recalc)}


@router.post("/books/{book_id}/nodes/{topic_id}/answer-key/compact")
def compact_answer_key(
    book_id: int,
    topic_id: int,
    payload: CompactPayload,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    parsed = questions.parse_compact_keys(payload.text)
    if not payload.apply:
        return {"parsed": len(parsed), "preview": {str(k): v for k, v in list(parsed.items())[:40]}, "applied": False}
    result = questions.set_answer_keys_bulk(
        db,
        user,
        book_id=book_id,
        topic_id=topic_id,
        items=[{"sequence_no": sequence, "answer_key": value} for sequence, value in parsed.items()],
        reason="چسباندن پاسخ‌نامه فشرده",
        level=payload.level,
    )
    db.commit()
    return {**result, "parsed": len(parsed)}


@router.get("/questions/{question_id}")
def question_detail(question_id: int, db: Session = Depends(get_db)) -> dict:
    return questions.question_history(db, question_id)


@router.put("/questions/{question_id}/answer-key")
def set_answer_key(
    question_id: int,
    payload: AnswerKeySinglePayload,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = questions.set_answer_key(db, user, question_id, payload.answer_key, reason=payload.reason)
    if result.get("recalc_required"):
        recalculation.recalculate(db, user, scope="question", scope_id=question_id, trigger="answer_key_correction")
    db.commit()
    return result


@router.post("/questions/{question_id}/disable")
def disable_question(
    question_id: int,
    reason: str | None = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = questions.disable_question(db, user, question_id, reason)
    db.commit()
    return result


@router.post("/questions/{question_id}/enable")
def enable_question(question_id: int, db: Session = Depends(get_db)) -> dict:
    result = questions.enable_question(db, question_id)
    db.commit()
    return result


@router.put("/questions/{question_id}/topics")
def map_question(
    question_id: int,
    payload: dict = Body(...),
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = curriculum_update_mapping(db, question_id, payload)
    if result.get("recalc_required"):
        recalculation.recalculate(db, user, scope="question", scope_id=question_id, trigger="topic_mapping_corrected")
    db.commit()
    return result


def curriculum_update_mapping(db: Session, question_id: int, payload: dict) -> dict:
    from ...services import curriculum

    return curriculum.update_question_mapping(
        db, question_id, payload.get("topic_ids") or [], relation=payload.get("relation", "related"), reason=payload.get("reason")
    )


@router.get("/topics/{topic_id}/selection-stats")
def selection_stats(topic_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return selection.selection_stats(db, user, topic_id)


@router.get("/topics/{topic_id}/coverage")
def coverage(topic_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return questions.coverage_of_topic(db, user, topic_id)


@router.get("/topics/{topic_id}/recommendation")
def topic_recommendation(
    topic_id: int,
    persist: bool = False,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """What to do about this topic, with the intervention chosen before questions."""
    from ...services import recommendation

    if persist:
        row = recommendation.build_recommendation(db, user, topic_id=topic_id, scope="topic")
        db.commit()
        return recommendation.explanation(db, row.id)
    decision = recommendation.choose_intervention(db, user, topic_id)
    preview = selection.select_for_intervention(
        db,
        user,
        topic_id=topic_id,
        intervention=decision["intervention"],
        count=recommendation.question_count_for(decision["intervention"]),
    )
    from ...domain.enums import INTERVENTION_LABELS_FA, InterventionType

    return {
        "topic_id": topic_id,
        "intervention": decision["intervention"],
        "intervention_label": INTERVENTION_LABELS_FA.get(InterventionType(decision["intervention"]), ""),
        "why": decision["reasons"],
        "confidence": decision["confidence"],
        "selection_preview": {**preview, "question_ids": preview["question_ids"][:20]},
        "what_can_i_change": [
            "نوع مداخله را می‌توانی عوض کنی (مثلاً از تمرین دشوار به مرور).",
            "تعداد سؤال قابل تغییر است و به‌عنوان تصمیم دستی ثبت می‌شود.",
        ],
    }
