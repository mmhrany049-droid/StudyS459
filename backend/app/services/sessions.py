"""Test engine: selection, response sheets, attempts, results.

Lifecycle (V1/V2 in full, V3 semantics on top):
    Task → Start Session → Select → Answer → Finish → Correct → Persist →
    Analyze → Review → Complete Task → Reward

V3 semantics implemented here:

* a question, its answer key and a response sheet are three different entities;
* ``ANSWERED`` / ``UNANSWERED`` / ``NOT_ENTERED`` stay distinct forever;
* attempts are append-only: repeating a question adds a new attempt;
* finishing is idempotent and never duplicates attempts;
* a missing answer key yields ``NOT_EVALUABLE`` + ``pending_correction`` instead
  of pretending the automatic correction happened.
"""

from __future__ import annotations

import datetime as _dt
import random
from typing import Iterable, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.errors import ConflictError, InsufficientPoolError, NotFoundError, ValidationError
from ..core.timeutil import now_utc, today_local
from ..db import models
from ..domain.enums import (
    AnswerState,
    AttemptResultValue,
    SessionStatus,
    SessionType,
)
from . import common

# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def candidate_pool(
    db: Session,
    user: models.User,
    *,
    book_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    include_descendants: bool = False,
    seq_from: Optional[int] = None,
    seq_to: Optional[int] = None,
    parity: str = "any",
    difficulty: Optional[int] = None,
    exclude_question_ids: Optional[Iterable[int]] = None,
) -> list[models.Question]:
    stmt = select(models.Question).where(models.Question.active.is_(True))
    if book_id:
        stmt = stmt.where(models.Question.book_id == book_id)
    if topic_id:
        if include_descendants:
            topic = db.get(models.Topic, topic_id)
            if not topic:
                raise NotFoundError("مبحث پیدا نشد.")
            descendants = {
                row for row in db.scalars(select(models.Topic.id).where(models.Topic.path.like(f"{topic.path}{topic.id}/%")))
            }
            descendants.add(topic_id)
            stmt = stmt.where(models.Question.primary_topic_id.in_(descendants))
        else:
            stmt = stmt.where(models.Question.primary_topic_id == topic_id)
    if seq_from is not None:
        stmt = stmt.where(models.Question.sequence_no >= seq_from)
    if seq_to is not None:
        stmt = stmt.where(models.Question.sequence_no <= seq_to)
    if parity == "odd":
        stmt = stmt.where(models.Question.sequence_no % 2 == 1)
    elif parity == "even":
        stmt = stmt.where(models.Question.sequence_no % 2 == 0)
    if difficulty:
        stmt = stmt.where(models.Question.difficulty_level == difficulty)
    questions = list(db.scalars(stmt.order_by(models.Question.sequence_no)))
    if exclude_question_ids:
        excluded = set(exclude_question_ids)
        questions = [q for q in questions if q.id not in excluded]
    return questions


def available_count(db: Session, user: models.User, **criteria) -> int:
    return len(candidate_pool(db, user, **criteria))


def select_questions(
    db: Session,
    user: models.User,
    *,
    count: int,
    seed: Optional[int] = None,
    **criteria,
) -> list[models.Question]:
    if count <= 0:
        raise ValidationError("تعداد سؤال باید بزرگ‌تر از صفر باشد.")
    pool = candidate_pool(db, user, **criteria)
    if len(pool) < count:
        raise InsufficientPoolError(
            f"فقط {len(pool)} سؤال با این شرایط وجود دارد.",
            details={
                "available": len(pool),
                "requested": count,
                "hint": "بازه، زوج/فرد یا تعداد را تغییر بده.",
            },
        )
    rng = random.Random(seed)
    return rng.sample(pool, count)


def preview_selection(db: Session, user: models.User, **criteria) -> dict:
    pool = candidate_pool(db, user, **criteria)
    with_key = [q for q in pool if q.current_answer_key]
    return {
        "available": len(pool),
        "without_answer_key": len(pool) - len(with_key),
        "sequence_min": min((q.sequence_no for q in pool), default=None),
        "sequence_max": max((q.sequence_no for q in pool), default=None),
    }


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


def create_session(db: Session, user: models.User, payload: dict) -> models.TestSession:
    count = common.to_int(payload.get("count"), 0) or 0
    book_id = payload.get("book_id")
    topic_id = payload.get("topic_id")
    if not book_id and topic_id:
        topic = db.get(models.Topic, topic_id)
        book_id = topic.book_id if topic else None
    if not book_id:
        raise ValidationError("کتاب مشخص نشده است.")

    session_type = payload.get("session_type") or SessionType.PRACTICE.value
    parity = payload.get("parity", "any")
    if parity not in {"odd", "even", "any"}:
        raise ValidationError("parity باید odd، even یا any باشد.")
    seq_from = common.to_int(payload.get("sequence_from"))
    seq_to = common.to_int(payload.get("sequence_to"))
    difficulty = common.to_int(payload.get("difficulty_level"))
    include_descendants = bool(payload.get("include_descendants"))

    selected = select_questions(
        db,
        user,
        count=count,
        seed=common.to_int(payload.get("seed")),
        book_id=book_id,
        topic_id=topic_id,
        include_descendants=include_descendants,
        seq_from=seq_from,
        seq_to=seq_to,
        parity=parity,
        difficulty=difficulty,
        exclude_question_ids=payload.get("exclude_question_ids"),
    )

    from . import duration as duration_service  # local import avoids a cycle

    estimate = duration_service.estimate_for_task(
        db,
        user,
        task_type=SessionType(session_type).value,
        question_count=count,
        topic_id=topic_id,
        book_id=book_id,
        intervention=payload.get("intervention_type"),
    )

    timed = bool(payload.get("timed"))
    time_limit_seconds = common.to_int(payload.get("time_limit_seconds"))
    if timed and not time_limit_seconds:
        time_limit_seconds = int(estimate["point_minutes"] * 60)

    session = models.TestSession(
        user_id=user.id,
        session_type=session_type,
        book_id=book_id,
        topic_id=topic_id,
        task_id=common.to_int(payload.get("task_id")),
        exam_id=common.to_int(payload.get("exam_id")),
        recommendation_id=common.to_int(payload.get("recommendation_id")),
        intervention_type=payload.get("intervention_type"),
        timed=timed,
        time_limit_seconds=time_limit_seconds,
        sequence_from=seq_from,
        sequence_to=seq_to,
        parity=parity,
        planned_question_count=count,
        planned_duration_low=estimate["low_minutes"],
        planned_duration_high=estimate["high_minutes"],
        planned_date=coerce_date(payload.get("planned_date")) or today_local(),
        status=SessionStatus.IN_PROGRESS.value if payload.get("start_now") else SessionStatus.PLANNED.value,
        started_at=now_utc() if payload.get("start_now") else None,
        source=payload.get("source", "manual"),
    )
    db.add(session)
    db.flush()
    for order, question in enumerate(selected):
        db.add(
            models.SessionQuestion(
                session_id=session.id,
                question_id=question.id,
                display_order=order,
                selection_reason=payload.get("selection_reason"),
            )
        )
    sheet = models.ResponseSheet(
        session_id=session.id,
        user_id=user.id,
        status="open",
        entry_mode="historical_import" if session_type == SessionType.IMPORTED.value else "live",
    )
    db.add(sheet)
    db.flush()
    if not session.is_imported and session_type != SessionType.IMPORTED.value:
        # live sessions always materialise every row so UNANSWERED stays explicit
        for question in selected:
            db.add(
                models.ResponseEntry(
                    response_sheet_id=sheet.id,
                    question_id=question.id,
                    state=AnswerState.UNANSWERED.value,
                    selected_choice=None,
                    entry_source="live",
                )
            )
    _touch_parity_state(db, user, topic_id, parity)
    common.observe(
        db, user.id, "test_session_created",
        payload={"session_id": session.id, "count": count, "parity": parity, "topic_id": topic_id},
        session_id=session.id,
    )
    db.flush()
    return session


def coerce_date(value) -> Optional[_dt.date]:
    """Accept a date, a datetime or a Jalali/ISO string (the UI always sends Jalali)."""
    if not value:
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    try:
        return common.parse_date_if_string(str(value))
    except Exception:
        raise ValidationError(f"تاریخ نامعتبر: {value}")


def _touch_parity_state(db: Session, user: models.User, topic_id: Optional[int], parity: str) -> None:
    """Keep the V1 parity memory: used later only as a small selection signal."""
    if not topic_id or parity not in {"odd", "even"}:
        return
    row = db.scalars(
        select(models.NodeParityState).where(
            models.NodeParityState.user_id == user.id, models.NodeParityState.topic_id == topic_id
        )
    ).first()
    if row is None:
        db.add(
            models.NodeParityState(
                user_id=user.id, topic_id=topic_id, last_parity=parity, last_used_at=now_utc()
            )
        )
    else:
        row.last_parity = parity
        row.last_used_at = now_utc()
    db.flush()


def suggested_parity(db: Session, user: models.User, topic_id: int) -> str:
    row = db.scalars(
        select(models.NodeParityState).where(
            models.NodeParityState.user_id == user.id, models.NodeParityState.topic_id == topic_id
        )
    ).first()
    default = config.value("selection.default_first_parity")
    if not row or not row.last_parity:
        return default
    return "even" if row.last_parity == "odd" else "odd"


def session_payload(db: Session, session_id: int) -> dict:
    session = db.get(models.TestSession, session_id)
    if not session:
        raise NotFoundError("جلسه تست پیدا نشد.")
    rows = list(
        db.execute(
            select(models.SessionQuestion, models.Question)
            .join(models.Question, models.Question.id == models.SessionQuestion.question_id)
            .where(models.SessionQuestion.session_id == session_id)
            .order_by(models.SessionQuestion.display_order)
        ).all()
    )
    sheet = db.scalars(select(models.ResponseSheet).where(models.ResponseSheet.session_id == session_id)).first()
    entries: dict[int, models.ResponseEntry] = {}
    if sheet:
        entries = {
            row.question_id: row
            for row in db.scalars(select(models.ResponseEntry).where(models.ResponseEntry.response_sheet_id == sheet.id))
        }
    questions = []
    for link, question in rows:
        entry = entries.get(question.id)
        questions.append(
            {
                "question_id": question.id,
                "sequence_no": question.sequence_no,
                "display_order": link.display_order,
                "difficulty_level": question.difficulty_level,
                "topic_id": question.primary_topic_id,
                "answer_key": question.current_answer_key if session.status in {
                    SessionStatus.COMPLETED.value, SessionStatus.PENDING_CORRECTION.value
                } else None,
                "state": entry.state if entry else AnswerState.NOT_ENTERED.value,
                "selected_choice": entry.selected_choice if entry else None,
                "response_time_seconds": entry.response_time_seconds if entry else None,
            }
        )
    return {
        "id": session.id,
        "session_type": session.session_type,
        "status": session.status,
        "timed": session.timed,
        "time_limit_seconds": session.time_limit_seconds,
        "parity": session.parity,
        "sequence_from": session.sequence_from,
        "sequence_to": session.sequence_to,
        "planned_question_count": session.planned_question_count,
        "planned_duration_low": session.planned_duration_low,
        "planned_duration_high": session.planned_duration_high,
        "planned_duration_label": duration_label(session.planned_duration_low, session.planned_duration_high),
        "actual_duration_minutes": session.actual_duration_minutes,
        "is_imported": session.is_imported,
        "planned_date": common.jdate(session.planned_date),
        "started_at": common.jdatetime(session.started_at),
        "ended_at": common.jdatetime(session.ended_at),
        "topic_id": session.topic_id,
        "book_id": session.book_id,
        "intervention_type": session.intervention_type,
        "response_sheet_id": sheet.id if sheet else None,
        "questions": questions,
        "states_summary": state_summary(questions),
    }


def duration_label(low: Optional[int], high: Optional[int]) -> Optional[str]:
    if low is None and high is None:
        return None
    if low and high and low != high:
        return f"{low} تا {high} دقیقه"
    return f"{low or high} دقیقه"


def state_summary(questions: list[dict]) -> dict:
    summary = {AnswerState.ANSWERED.value: 0, AnswerState.UNANSWERED.value: 0, AnswerState.NOT_ENTERED.value: 0}
    for item in questions:
        summary[item["state"]] = summary.get(item["state"], 0) + 1
    return summary


def start_session(db: Session, session_id: int) -> dict:
    session = db.get(models.TestSession, session_id)
    if not session:
        raise NotFoundError("جلسه تست پیدا نشد.")
    if session.status == SessionStatus.COMPLETED.value:
        raise ConflictError("این جلسه قبلاً تمام شده است.")
    session.status = SessionStatus.IN_PROGRESS.value
    session.started_at = session.started_at or now_utc()
    db.flush()
    return {"session_id": session_id, "status": session.status, "started_at": common.jdatetime(session.started_at)}


def save_entries(
    db: Session,
    user: models.User,
    session_id: int,
    entries: Iterable[dict],
    *,
    finalize: bool = False,
    actual_duration_minutes: Optional[int] = None,
) -> dict:
    """Write response entries. A row can be ANSWERED, explicitly UNANSWERED, or
    NOT_ENTERED (imported sessions keep untouched rows un-entered)."""
    session = db.get(models.TestSession, session_id)
    if not session:
        raise NotFoundError("جلسه تست پیدا نشد.")
    if session.status == SessionStatus.COMPLETED.value:
        raise ConflictError("جلسه بسته شده است؛ برای اصلاح از مسیر بازبینی استفاده کن.")
    sheet = db.scalars(select(models.ResponseSheet).where(models.ResponseSheet.session_id == session_id)).first()
    if not sheet:
        sheet = models.ResponseSheet(session_id=session_id, user_id=user.id, entry_mode="live")
        db.add(sheet)
        db.flush()
    existing = {
        row.question_id: row
        for row in db.scalars(select(models.ResponseEntry).where(models.ResponseEntry.response_sheet_id == sheet.id))
    }
    session_question_ids = {
        row for row in db.scalars(select(models.SessionQuestion.question_id).where(models.SessionQuestion.session_id == session_id))
    }
    saved = 0
    for payload in entries:
        question_id = common.to_int(payload.get("question_id"))
        if not question_id:
            continue
        if question_id not in session_question_ids:
            raise ValidationError(f"سؤال {question_id} عضو این جلسه نیست.")
        state = payload.get("state")
        if state is None:
            if payload.get("unanswered") is True:
                state = AnswerState.UNANSWERED.value
            elif payload.get("not_entered") is True:
                state = AnswerState.NOT_ENTERED.value
            elif payload.get("selected_choice") in (None, "", 0, "0"):
                state = AnswerState.UNANSWERED.value
            else:
                state = AnswerState.ANSWERED.value
        if state not in {s.value for s in AnswerState}:
            raise ValidationError(f"وضعیت پاسخ نامعتبر است: {state}")
        choice = payload.get("selected_choice")
        choice = None if choice in (None, "", 0, "0") else str(choice)
        if state == AnswerState.ANSWERED.value and choice is None:
            raise ValidationError("برای پاسخ داده‌شده باید گزینه ثبت شود.")
        if state != AnswerState.ANSWERED.value:
            choice = None
        row = existing.get(question_id)
        if row is None:
            row = models.ResponseEntry(response_sheet_id=sheet.id, question_id=question_id, entry_source=sheet.entry_mode)
            db.add(row)
            existing[question_id] = row
        row.state = state
        row.selected_choice = choice
        row.response_time_seconds = common.to_int(payload.get("response_time_seconds"))
        row.entered_at = now_utc()
        saved += 1
    db.flush()
    if finalize:
        return finish_session(db, user, session_id, actual_duration_minutes=actual_duration_minutes)
    return {"session_id": session_id, "saved": saved, "status": session.status}


def finish_session(
    db: Session,
    user: models.User,
    session_id: int,
    *,
    actual_duration_minutes: Optional[int] = None,
    auto_finish: bool = False,
) -> dict:
    """Idempotent finish: evaluates response entries against the *applicable*
    answer-key version and materialises attempt results exactly once."""
    session = db.get(models.TestSession, session_id)
    if not session:
        raise NotFoundError("جلسه تست پیدا نشد.")

    already = list(
        db.scalars(
            select(models.AttemptResult).where(
                models.AttemptResult.session_id == session_id, models.AttemptResult.is_current.is_(True)
            )
        )
    )
    if session.status == SessionStatus.COMPLETED.value and already:
        # A retry must get the same shape back, without re-awarding anything.
        from . import rewards as rewards_service

        payload = session_result(db, session_id, idempotent=True)
        missing = sum(
            1
            for row in already
            if row.result == AttemptResultValue.NOT_EVALUABLE.value
            and row.state != AnswerState.NOT_ENTERED.value
        )
        payload["rewards"] = rewards_service.session_summary(db, user, session)
        payload["pending_correction"] = missing > 0
        payload["missing_answer_keys"] = missing
        payload["auto_finish"] = auto_finish
        return payload

    sheet = db.scalars(select(models.ResponseSheet).where(models.ResponseSheet.session_id == session_id)).first()
    if sheet is None:
        raise ValidationError("پاسخ‌نامه‌ای برای این جلسه وجود ندارد.")
    entries = {
        row.question_id: row
        for row in db.scalars(select(models.ResponseEntry).where(models.ResponseEntry.response_sheet_id == sheet.id))
    }
    questions = {
        row.id: row
        for row in db.scalars(
            select(models.Question).where(
                models.Question.id.in_(
                    select(models.SessionQuestion.question_id).where(models.SessionQuestion.session_id == session_id)
                )
            )
        )
    }
    imported = session.session_type == SessionType.IMPORTED.value or session.is_imported
    evaluated: list[models.AttemptResult] = []
    missing_keys = 0
    for question_id, question in questions.items():
        entry = entries.get(question_id)
        if entry is None:
            if imported:
                # historical row the user never touched -> honest NOT_ENTERED
                result = _persist_attempt(
                    db, user, session, question, None, AnswerState.NOT_ENTERED.value, None
                )
                evaluated.append(result)
                continue
            state = AnswerState.UNANSWERED.value
            selected = None
        else:
            state = entry.state
            selected = entry.selected_choice
        result = _persist_attempt(db, user, session, question, entry, state, selected)
        if result.result == AttemptResultValue.NOT_EVALUABLE.value:
            # only a genuinely absent answer key counts; NOT_ENTERED has its own value
            missing_keys += 1
        evaluated.append(result)

    session.ended_at = session.ended_at or now_utc()
    if actual_duration_minutes:
        session.actual_duration_minutes = int(actual_duration_minutes)
    elif session.started_at and not session.is_imported:
        session.actual_duration_minutes = max(1, int((session.ended_at - session.started_at).total_seconds() // 60))
    session.status = (
        SessionStatus.PENDING_CORRECTION.value if missing_keys else SessionStatus.COMPLETED.value
    )
    sheet.status = "finalized"
    sheet.finalized_at = now_utc()
    db.flush()

    from . import learning, rewards, review  # local imports: avoid cycles

    affected_topics = {q.primary_topic_id for q in questions.values() if q.primary_topic_id}
    learning.refresh_topics(db, user, affected_topics)
    review.sync_from_session(db, user, session)
    learning.refresh_retention_for_session(db, user, session)
    rewards.apply_session_rewards(db, user, session)  # awards once (dedupe keys per session/question)
    # report the reconstructed view so a first submit and a later retry agree
    reward_summary = rewards.session_summary(db, user, session)
    if session.actual_duration_minutes:
        from . import duration as duration_service

        duration_service.record_observation(
            db,
            user,
            actual_minutes=int(session.actual_duration_minutes),
            task_type=session.session_type,
            question_count=len(questions),
            topic_id=session.topic_id,
            book_id=session.book_id,
            session_id=session.id,
            source="user",
        )
    common.observe(
        db, user.id, "test_session_finished",
        payload={"session_id": session.id, "status": session.status, "correct": sum(
            1 for r in evaluated if r.result == AttemptResultValue.CORRECT.value
        )},
        session_id=session.id,
    )
    db.flush()
    payload = session_result(db, session_id)
    payload["rewards"] = reward_summary
    payload["pending_correction"] = missing_keys > 0
    payload["missing_answer_keys"] = missing_keys
    payload["idempotent"] = bool(already)
    payload["auto_finish"] = auto_finish
    return payload


def _persist_attempt(
    db: Session,
    user: models.User,
    session: models.TestSession,
    question: models.Question,
    entry: Optional[models.ResponseEntry],
    state: str,
    selected_choice: Optional[str],
) -> models.AttemptResult:
    """Create the (current) attempt result and supersede the previous one for
    the same response entry - raw history is preserved, never overwritten."""
    answer_key = question.current_answer_key
    if state == AnswerState.NOT_ENTERED.value:
        # "not entered" is its own outcome: it is neither unanswered nor a
        # missing answer key, so it must never trigger pending_correction
        result = AttemptResultValue.NOT_ENTERED.value
    elif not answer_key:
        result = AttemptResultValue.NOT_EVALUABLE.value
    elif state == AnswerState.UNANSWERED.value:
        result = AttemptResultValue.UNANSWERED.value
    elif str(selected_choice) == str(answer_key):
        result = AttemptResultValue.CORRECT.value
    else:
        result = AttemptResultValue.WRONG.value

    previous = None
    if entry is not None:
        previous = db.scalars(
            select(models.AttemptResult).where(
                models.AttemptResult.response_entry_id == entry.id, models.AttemptResult.is_current.is_(True)
            )
        ).first()
    attempt = models.AttemptResult(
        user_id=user.id,
        session_id=session.id,
        response_entry_id=entry.id if entry else None,
        question_id=question.id,
        topic_id=question.primary_topic_id,
        answer_key_value=answer_key,
        selected_choice=selected_choice,
        state=state,
        result=result,
        difficulty_level=question.difficulty_level,
        duration_seconds=entry.response_time_seconds if entry else None,
        attempted_on=session.planned_date or today_local(),
        is_current=True,
        source="historical_import" if session.is_imported or session.session_type == SessionType.IMPORTED.value else "live",
    )
    if previous is not None:
        previous.is_current = False
        db.add(attempt)
        db.flush()
        previous.superseded_by_id = attempt.id
    else:
        db.add(attempt)
    db.flush()
    return attempt


def reevaluate_question(db: Session, user: models.User, question_id: int, reason: str = "answer key corrected") -> dict:
    """Recalculation entry point used when an answer key or topic mapping changes."""
    attempts = list(
        db.scalars(
            select(models.AttemptResult).where(
                models.AttemptResult.question_id == question_id, models.AttemptResult.is_current.is_(True)
            )
        )
    )
    question = db.get(models.Question, question_id)
    if not question:
        raise NotFoundError("سؤال پیدا نشد.")
    changed = 0
    touched_topics: set[int] = set()
    for attempt in attempts:
        if attempt.state == AnswerState.ANSWERED.value:
            new_result = (
                AttemptResultValue.CORRECT.value
                if str(attempt.selected_choice) == str(question.current_answer_key)
                else AttemptResultValue.WRONG.value
            )
        elif attempt.state == AnswerState.UNANSWERED.value:
            new_result = AttemptResultValue.UNANSWERED.value if question.current_answer_key else AttemptResultValue.NOT_EVALUABLE.value
        else:
            new_result = AttemptResultValue.NOT_EVALUABLE.value
        new_key = question.current_answer_key
        if new_result != attempt.result or new_key != attempt.answer_key_value or attempt.topic_id != question.primary_topic_id:
            attempt.is_current = False
            replacement = models.AttemptResult(
                user_id=attempt.user_id,
                session_id=attempt.session_id,
                response_entry_id=attempt.response_entry_id,
                question_id=question_id,
                topic_id=question.primary_topic_id,
                answer_key_value=new_key,
                selected_choice=attempt.selected_choice,
                state=attempt.state,
                result=new_result,
                difficulty_level=question.difficulty_level,
                duration_seconds=attempt.duration_seconds,
                attempted_on=attempt.attempted_on,
                is_current=True,
                source=attempt.source,
            )
            db.add(replacement)
            db.flush()
            attempt.superseded_by_id = replacement.id
            changed += 1
        touched_topics.add(attempt.topic_id)
    db.flush()
    from . import learning, review

    learning.refresh_topics(db, user, touched_topics)
    review.rebuild_for_questions(db, user, {question_id})
    common.audit(
        db, "attempts_reevaluated", user_id=user.id, entity_type="question", entity_id=question_id,
        reason=reason, after={"changed": changed},
    )
    return {"question_id": question_id, "reevaluated": len(attempts), "changed": changed}


def session_result(db: Session, session_id: int, idempotent: bool = False) -> dict:
    session = db.get(models.TestSession, session_id)
    if not session:
        raise NotFoundError("جلسه تست پیدا نشد.")
    attempts = list(
        db.scalars(
            select(models.AttemptResult).where(
                models.AttemptResult.session_id == session_id, models.AttemptResult.is_current.is_(True)
            )
        )
    )
    total = len(attempts)
    correct = sum(1 for a in attempts if a.result == AttemptResultValue.CORRECT.value)
    wrong = sum(1 for a in attempts if a.result == AttemptResultValue.WRONG.value)
    unanswered = sum(1 for a in attempts if a.result == AttemptResultValue.UNANSWERED.value)
    not_evaluable = sum(1 for a in attempts if a.result == AttemptResultValue.NOT_EVALUABLE.value)
    not_entered = sum(1 for a in attempts if a.state == AnswerState.NOT_ENTERED.value)
    answered = correct + wrong
    topic_ids = {a.topic_id for a in attempts if a.topic_id}
    topics = {}
    if topic_ids:
        topics = {t.id: t for t in db.scalars(select(models.Topic).where(models.Topic.id.in_(topic_ids)))}
    breakdown: dict[int, dict] = {}
    for attempt in attempts:
        key = attempt.topic_id
        entry = breakdown.setdefault(
            key,
            {
                "topic_id": key,
                "topic_title": topics[key].title if key in topics else None,
                "total": 0, "correct": 0, "wrong": 0, "unanswered": 0,
                "not_evaluable": 0, "not_entered": 0,
            },
        )
        entry["total"] += 1
        bucket = attempt.result.lower()
        if attempt.result == AttemptResultValue.NOT_EVALUABLE.value and attempt.state == AnswerState.NOT_ENTERED.value:
            bucket = "not_entered"
        elif attempt.result == AttemptResultValue.NOT_EVALUABLE.value:
            bucket = "not_evaluable"
        if bucket not in entry:
            bucket = "not_evaluable"
        entry[bucket] += 1
    difficulty_breakdown: dict[str, dict] = {}
    for attempt in attempts:
        key = str(attempt.difficulty_level or "unset")
        entry = difficulty_breakdown.setdefault(key, {"total": 0, "correct": 0})
        entry["total"] += 1
        entry["correct"] += 1 if attempt.result == AttemptResultValue.CORRECT.value else 0
    return {
        "session_id": session_id,
        "status": session.status,
        "session_type": session.session_type,
        "timed": session.timed,
        "parity": session.parity,
        "sequence_from": session.sequence_from,
        "sequence_to": session.sequence_to,
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "not_evaluable": not_evaluable,
        "not_entered": not_entered,
        "answered": answered,
        # accuracy is undefined without answered questions - never a fake zero
        "accuracy": (correct / answered) if answered else None,
        "duration_minutes": session.actual_duration_minutes,
        "planned_duration_low": session.planned_duration_low,
        "planned_duration_high": session.planned_duration_high,
        "average_seconds_per_question": (
            round(sum(a.duration_seconds or 0 for a in attempts) / total, 1) if total else None
        ),
        "topic_breakdown": list(breakdown.values()),
        "difficulty_breakdown": difficulty_breakdown,
        "date": common.jdate(session.planned_date),
        "date_long": common.jdate_long(session.planned_date),
        "idempotent": idempotent,
        # correct + wrong + unanswered + not_entered + not_evaluable == total
        "invariant_ok": (correct + wrong + unanswered + not_entered + not_evaluable) == total,
    }


def session_history(db: Session, user: models.User, limit: int = 50, offset: int = 0) -> list[dict]:
    sessions = list(
        db.scalars(
            select(models.TestSession)
            .where(models.TestSession.user_id == user.id)
            .order_by(
                models.TestSession.planned_date.is_(None),
                models.TestSession.planned_date.desc(),
                models.TestSession.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )
    if not sessions:
        return []
    ids = [s.id for s in sessions]
    counts = dict(
        db.execute(
            select(models.AttemptResult.session_id, func.count(models.AttemptResult.id))
            .where(models.AttemptResult.session_id.in_(ids), models.AttemptResult.is_current.is_(True))
            .group_by(models.AttemptResult.session_id)
        ).all()
    )
    correct_counts = dict(
        db.execute(
            select(models.AttemptResult.session_id, func.sum(case((models.AttemptResult.result == "CORRECT", 1), else_=0)))
            .where(models.AttemptResult.session_id.in_(ids), models.AttemptResult.is_current.is_(True))
            .group_by(models.AttemptResult.session_id)
        ).all()
    )
    return [
        {
            "id": s.id,
            "session_type": s.session_type,
            "status": s.status,
            "date": common.jdate(s.planned_date),
            "date_long": common.jdate_long(s.planned_date),
            "total": counts.get(s.id, 0),
            "correct": int(correct_counts.get(s.id) or 0),
            "is_imported": s.is_imported,
            "duration_minutes": s.actual_duration_minutes,
            "timed": s.timed,
        }
        for s in sessions
    ]
