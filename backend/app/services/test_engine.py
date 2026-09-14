"""Test Engine orchestration: sessions, answers, finish, corrections (spec 06).

Data flow per answer: validate -> append attempt row (never update).
Data flow per finish: latest attempts -> score -> fill verdicts -> result.
"""

import random
from datetime import datetime

from sqlalchemy.orm import Session

from app.analytics.review_queue import populate_for_correction, populate_for_session
from app.db import utcnow
from app.domain.test_selection import (
    EVEN,
    ODD,
    InsufficientQuestions,
    PoolQuestion,
    count_by_parity,
    deadline,
    filter_pool,
    is_expired,
    score_session,
    select_question_ids,
    suggest_parity,
)
from app.errors import AppError
from app.logging_config import get_logger
from app.models import TestSession
from app.repositories import books as book_repo
from app.repositories import tests as repo
from app.schemas.tests import (
    AnswerItem,
    AnswersOut,
    CorrectionItem,
    CorrectionOut,
    DifficultyBreakdown,
    ParityStateOut,
    RecordedAttempt,
    ResultOut,
    SessionOut,
    SessionQuestionOut,
    SessionView,
    TopicBreakdown,
    TopicRef,
)
from app.services.users import get_or_create_single_user

logger = get_logger(__name__)


def _owned_session(db: Session, *, user_id: int, session_id: int) -> TestSession:
    session = repo.get_session(db, session_id)
    if session is None or session.user_id != user_id:
        raise AppError("session_not_found", "نشست تست یافت نشد.", status_code=404)
    return session


def _remaining_seconds(session: TestSession, now: datetime) -> int | None:
    if not session.timed or session.status != "in_progress":
        return None
    assert session.time_limit_seconds is not None
    return max(0, int((deadline(session.started_at, session.time_limit_seconds) - now).total_seconds()))


def _is_session_expired(session: TestSession, now: datetime) -> bool:
    return (
        session.timed
        and session.status == "in_progress"
        and session.time_limit_seconds is not None
        and is_expired(session.started_at, session.time_limit_seconds, now)
    )


def _complete_session(db: Session, session: TestSession, *, ended_at: datetime):
    """Score latest attempts, fill verdicts, flip status. Returns the score."""
    question_ids = repo.get_session_question_ids(db, session.id)
    detail = repo.get_session_questions_detail(db, session.id)
    keys = {q.id: q.answer_key for _, q, _ in detail}
    latest = repo.latest_attempts_by_question(db, session.id)
    answers = {qid: a.answer for qid, a in latest.items()}
    stored = {qid: a.result for qid, a in latest.items()}
    score = score_session(question_ids, keys, answers, stored)
    for qid, verdict in score.verdicts.items():
        if verdict is not None and latest[qid].result is None:
            latest[qid].result = verdict  # fill blank (NULL -> value); evidence untouched
    session.ended_at = ended_at
    session.status = "pending_correction" if score.totals.pending else "completed"
    if session.task_id is not None:
        # Phase 5: finishing the linked session completes its test task.
        from app.repositories import planner as planner_repo

        planner_repo.complete_task_if_open(db, session.task_id, completed_at=ended_at)
    db.flush()
    return score


def _build_view(db: Session, session: TestSession, *, now: datetime) -> SessionView:
    detail = repo.get_session_questions_detail(db, session.id)
    question_ids = [sq.question_id for sq, _, _ in detail]
    topics = repo.topics_for_questions(db, question_ids)
    latest = repo.latest_attempts_by_question(db, session.id)

    questions = [
        SessionQuestionOut(
            question_id=q.id,
            display_order=sq.display_order,
            sequence_no=q.sequence_no,
            test_set_id=q.test_set_id,
            test_set_title=ts_title,
            difficulty=q.difficulty_level,
            topics=[TopicRef(node_id=nid, title=title) for nid, title in topics.get(q.id, [])],
            answer=latest[q.id].answer if q.id in latest else None,
            result=latest[q.id].result if q.id in latest else None,
            response_time_seconds=latest[q.id].response_time_seconds if q.id in latest else None,
            has_answer_key=q.answer_key is not None,
        )
        for sq, q, ts_title in detail
    ]

    result: ResultOut | None = None
    if session.status != "in_progress":
        keys = {q.id: q.answer_key for _, q, _ in detail}
        answers = {qid: a.answer for qid, a in latest.items()}
        stored = {qid: a.result for qid, a in latest.items()}
        score = score_session(question_ids, keys, answers, stored)
        t = score.totals
        bucket = score.buckets  # stored verdicts (incl. manual corrections) win
        topic_agg: dict[int, dict] = {}
        for qid in question_ids:
            for nid, title in topics.get(qid, []):
                cell = topic_agg.setdefault(
                    nid, {"title": title, "total": 0, "correct": 0, "wrong": 0, "unanswered": 0, "pending": 0}
                )
                cell["total"] += 1
                cell[bucket[qid]] += 1
        diff_agg: dict[str | None, dict] = {}
        for _, q, _ in detail:
            cell = diff_agg.setdefault(
                q.difficulty_level, {"total": 0, "correct": 0, "wrong": 0, "unanswered": 0, "pending": 0}
            )
            cell["total"] += 1
            cell[bucket[q.id]] += 1
        response_times = [
            latest[qid].response_time_seconds
            for qid in question_ids
            if qid in latest and latest[qid].response_time_seconds is not None
        ]
        result = ResultOut(
            status=session.status,
            total=len(question_ids),
            correct=t.correct,
            wrong=t.wrong,
            unanswered=t.unanswered,
            pending=t.pending,
            accuracy=score.accuracy,
            duration_seconds=(
                int((session.ended_at - session.started_at).total_seconds())
                if session.ended_at
                else None
            ),
            average_response_time_seconds=(
                sum(response_times) / len(response_times) if response_times else None
            ),
            topic_breakdown=[
                TopicBreakdown(node_id=nid, title=cell["title"], **{k: cell[k] for k in ("total", "correct", "wrong", "unanswered", "pending")})
                for nid, cell in sorted(topic_agg.items())
            ],
            difficulty_breakdown=[
                DifficultyBreakdown(difficulty=level, **{k: cell[k] for k in ("total", "correct", "wrong", "unanswered", "pending")})
                for level, cell in sorted(diff_agg.items(), key=lambda kv: (kv[0] is None, kv[0]))
            ],
            parity=session.parity,
            sequence_from=session.sequence_from,
            sequence_to=session.sequence_to,
            timed=session.timed,
            time_limit_seconds=session.time_limit_seconds,
            started_at=session.started_at,
            ended_at=session.ended_at,
        )

    expired = _is_session_expired(session, now)
    return SessionView(
        session=SessionOut(
            id=session.id,
            user_id=session.user_id,
            task_id=session.task_id,
            timed=session.timed,
            time_limit_seconds=session.time_limit_seconds,
            sequence_from=session.sequence_from,
            sequence_to=session.sequence_to,
            parity=session.parity,
            status=session.status,
            started_at=session.started_at,
            ended_at=session.ended_at,
            remaining_seconds=_remaining_seconds(session, now),
            expired=expired,
        ),
        questions=questions,
        result=result,
    )


# -- create ------------------------------------------------------------
def create_session(
    db: Session,
    *,
    user_id: int,
    node_id: int,
    count: int,
    sequence_from: int | None,
    sequence_to: int | None,
    parity: str,
    timed: bool,
    time_limit_seconds: int | None,
    task_id: int | None,
    rng: random.Random | None = None,
) -> SessionView:
    get_or_create_single_user(db, user_id)
    node = book_repo.get_node(db, node_id)
    if node is None:
        raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
    activation = book_repo.get_activation(db, user_id, node.book_id)
    if activation is None or not activation.active:
        raise AppError(
            "book_inactive",
            "این کتاب غیرفعال است؛ برای ساخت تست ابتدا آن را فعال کنید.",
            status_code=409,
            details={"book_id": node.book_id},
        )
    if sequence_from is not None and sequence_to is not None and sequence_from > sequence_to:
        raise AppError("invalid_range", "ابتدای بازه نمی‌تواند از انتهای آن بزرگ‌تر باشد.", status_code=422)
    if timed and not time_limit_seconds:
        raise AppError(
            "invalid_timed_config",
            "برای حالت زمان‌دار باید time_limit_seconds بزرگ‌تر از صفر باشد.",
            status_code=422,
        )
    if not timed and time_limit_seconds is not None:
        raise AppError(
            "invalid_timed_config",
            "در حالت بدون‌زمان نباید time_limit_seconds ارسال شود.",
            status_code=422,
        )

    subtree = repo.node_subtree_ids(db, node_id)
    raw_pool = repo.pool_questions(
        db, book_id=node.book_id, node_ids=subtree,
        sequence_from=sequence_from, sequence_to=sequence_to,
    )
    range_pool = [PoolQuestion(id=qid, sequence_no=seq) for qid, seq in raw_pool]
    range_counts = count_by_parity(range_pool)  # before parity filter (for suggestions)
    pool = filter_pool(range_pool, parity=parity)
    try:
        selected = select_question_ids(pool, count, rng=rng)
    except InsufficientQuestions as exc:
        if sequence_from is not None and sequence_to is not None:
            treatments = f"بازه {sequence_from} تا {sequence_to}"
        elif sequence_from is not None:
            treatments = f"از سؤال {sequence_from} به بعد"
        elif sequence_to is not None:
            treatments = f"تا سؤال {sequence_to}"
        else:
            treatments = "این مبحث"
        parity_word = {"odd": "فرد", "even": "زوج"}.get(parity, "")
        noun = f"سؤال {parity_word} " if parity_word else "سؤال "
        raise AppError(
            "insufficient_questions",
            f"فقط {exc.available} {noun}در {treatments} وجود دارد؛ {exc.requested} سؤال درخواست شده است. "
            "بازه، زوج/فرد یا تعداد را تغییر دهید.",
            status_code=422,
            details={
                "requested": exc.requested,
                "available": exc.available,
                # Range-level counts (ignoring the parity filter) so the UI
                # can suggest switching parity instead of just failing.
                "available_odd": range_counts["odd"],
                "available_even": range_counts["even"],
                "node_id": node_id,
                "sequence_from": sequence_from,
                "sequence_to": sequence_to,
                "parity": parity,
            },
        ) from exc

    try:
        session = repo.create_session(
            db,
            user_id=user_id,
            task_id=task_id,
            timed=timed,
            time_limit_seconds=time_limit_seconds,
            sequence_from=sequence_from,
            sequence_to=sequence_to,
            parity=parity,
        )
        repo.add_session_questions(db, session_id=session.id, question_ids=selected)
        # Only a concrete parity counts as "used" (spec 06); "any" keeps history.
        if parity in (ODD, EVEN):
            repo.update_parity_state(db, user_id=user_id, node_id=node_id, parity=parity)
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("session created: id=%s node=%s count=%s parity=%s", session.id, node_id, count, parity)
    return _build_view(db, session, now=utcnow())


def get_session_view(db: Session, *, user_id: int, session_id: int) -> SessionView:
    session = _owned_session(db, user_id=user_id, session_id=session_id)
    return _build_view(db, session, now=utcnow())  # read-only: never auto-completes


# -- answers -----------------------------------------------------------
def submit_answers(
    db: Session, *, user_id: int, session_id: int, answers: list[AnswerItem]
) -> AnswersOut:
    session = _owned_session(db, user_id=user_id, session_id=session_id)
    now = utcnow()
    if session.status != "in_progress":
        raise AppError(
            "session_not_in_progress",
            "این نشست قبلاً به پایان رسیده است.",
            status_code=409,
            details={"status": session.status},
        )
    if _is_session_expired(session, now):
        assert session.time_limit_seconds is not None
        try:
            score = _complete_session(db, session, ended_at=deadline(session.started_at, session.time_limit_seconds))
            populate_for_session(db, user_id=user_id, buckets=score.buckets)
            db.commit()
        except Exception:
            db.rollback()
            raise
        raise AppError(
            "session_expired",
            "زمان نشست به پایان رسید؛ نشست به‌صورت خودکار بسته شد.",
            status_code=409,
            details={"session_id": session.id, "status": session.status},
        )

    member_ids = set(repo.get_session_question_ids(db, session.id))
    recorded: list[RecordedAttempt] = []
    try:
        for item in answers:
            if item.question_id not in member_ids:
                raise AppError(
                    "question_not_in_session",
                    "این سؤال متعلق به این نشست نیست.",
                    status_code=422,
                    details={"question_id": item.question_id},
                )
            existing = repo.get_attempt_by_client_id(db, str(item.client_attempt_id))
            if existing is not None:  # double-submit: no duplicate row (spec 13)
                recorded.append(
                    RecordedAttempt(question_id=existing.question_id, attempt_id=existing.id, duplicate=True)
                )
                continue
            attempt = repo.create_attempt(
                db,
                session_id=session.id,
                question_id=item.question_id,
                user_id=user_id,
                answer=item.answer,  # None = retract to unanswered (append-only)
                response_time_seconds=item.response_time_seconds,
                client_attempt_id=str(item.client_attempt_id),
            )
            recorded.append(
                RecordedAttempt(question_id=item.question_id, attempt_id=attempt.id, duplicate=False)
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return AnswersOut(attempts=recorded)


# -- finish ------------------------------------------------------------
def finish_session(db: Session, *, user_id: int, session_id: int) -> SessionView:
    session = _owned_session(db, user_id=user_id, session_id=session_id)
    now = utcnow()
    if session.status != "in_progress":
        return _build_view(db, session, now=now)  # idempotent: same view, zero writes
    if _is_session_expired(session, now):
        assert session.time_limit_seconds is not None
        ended = deadline(session.started_at, session.time_limit_seconds)  # deterministic
    else:
        ended = now
    try:
        score = _complete_session(db, session, ended_at=ended)
        populate_for_session(db, user_id=user_id, buckets=score.buckets)
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("session finished: id=%s status=%s", session.id, session.status)
    return _build_view(db, session, now=utcnow())


# -- corrections (pending only) ----------------------------------------
def submit_corrections(
    db: Session, *, user_id: int, session_id: int, corrections: list[CorrectionItem]
) -> CorrectionOut:
    session = _owned_session(db, user_id=user_id, session_id=session_id)
    if session.status == "in_progress":
        raise AppError(
            "session_in_progress",
            "ابتدا نشست را به پایان برسانید، سپس تصحیح کنید.",
            status_code=409,
            details={"status": session.status},
        )
    if session.status == "completed":
        raise AppError(
            "session_completed",
            "این نشست قبلاً کامل تصحیح شده است.",
            status_code=409,
            details={"status": session.status},
        )
    latest = repo.latest_attempts_by_question(db, session.id)
    try:
        for item in corrections:
            attempt = latest.get(item.question_id)
            if attempt is None or attempt.answer is None or attempt.result is not None:
                raise AppError(
                    "correction_not_pending",
                    "این سؤال در انتظار تصحیح نیست.",
                    status_code=422,
                    details={"question_id": item.question_id},
                )
            attempt.result = item.result
            populate_for_correction(
                db, user_id=user_id, question_id=item.question_id, result=item.result
            )
        db.flush()
        remaining = sum(
            1 for a in repo.latest_attempts_by_question(db, session.id).values()
            if a.answer is not None and a.result is None
        )
        if remaining == 0:
            session.status = "completed"
        db.commit()
    except Exception:
        db.rollback()
        raise
    return CorrectionOut(session_id=session.id, status=session.status, pending_remaining=remaining)


# -- parity state ------------------------------------------------------
def get_parity_state(db: Session, *, user_id: int, node_id: int) -> ParityStateOut:
    node = book_repo.get_node(db, node_id)
    if node is None:
        raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
    row = repo.get_parity_state(db, user_id, node_id)
    last = row.last_parity if row else None
    return ParityStateOut(
        node_id=node_id,
        last_parity=last,
        last_used_at=row.last_used_at if row else None,
        suggested_parity=suggest_parity(last),
    )


# Re-export for tests/consumers that only need the counting helper.
__all__ = [
    "create_session",
    "finish_session",
    "get_parity_state",
    "get_session_view",
    "submit_answers",
    "submit_corrections",
    "count_by_parity",
]
