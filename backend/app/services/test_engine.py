"""
موتور تست — Range + parity (سند 06_TEST_ENGINE) و مرور خوشه‌ای V2 (سند 06_REVIEW_ALGORITHM_V2).
unanswered همیشه از wrong جداست.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config as cfg
from .. import models as m
from . import rewards
from .common import descendant_node_ids, log_behavior, questions_of_node


class SelectionError(Exception):
    pass


def pick_questions(db: Session, node_id: int, count: int, sequence_from: int | None,
                   sequence_to: int | None, parity: str) -> list[m.Question]:
    pool = [q for q in questions_of_node(db, node_id) if q.answer_key is not None]
    if sequence_from is not None:
        pool = [q for q in pool if q.sequence_no >= sequence_from]
    if sequence_to is not None:
        pool = [q for q in pool if q.sequence_no <= sequence_to]
    if parity == "odd":
        pool = [q for q in pool if q.sequence_no % 2 == 1]
    elif parity == "even":
        pool = [q for q in pool if q.sequence_no % 2 == 0]
    if len(pool) < count:
        raise SelectionError(f"فقط {len(pool)} سوال با این شرایط وجود دارد.")
    # انتخاب تصادفی، ولی ارائه به ترتیب صعودی شماره سوال (مطابق ترتیب کتاب)
    return sorted(random.sample(pool, count), key=lambda q: q.sequence_no)


def suggest_parity(db: Session, user_id: int, node_id: int) -> str:
    st = db.scalar(select(m.NodeParityState).where(
        m.NodeParityState.user_id == user_id, m.NodeParityState.node_id == node_id))
    if not st:
        return cfg.DEFAULT_FIRST_PARITY
    return "even" if st.last_parity == "odd" else "odd"


def _remember_parity(db: Session, user_id: int, node_id: int, parity: str) -> None:
    if parity not in ("odd", "even"):
        return
    st = db.scalar(select(m.NodeParityState).where(
        m.NodeParityState.user_id == user_id, m.NodeParityState.node_id == node_id))
    if st:
        st.last_parity = parity
        st.last_used_at = datetime.utcnow()
    else:
        db.add(m.NodeParityState(user_id=user_id, node_id=node_id, last_parity=parity))


def create_session(db: Session, user: m.User, node_id: int, count: int,
                   sequence_from: int | None, sequence_to: int | None, parity: str,
                   timed: bool, time_limit_seconds: int | None,
                   task_id: int | None = None) -> m.TestSession:
    node = db.get(m.BookNode, node_id)
    if not node:
        raise SelectionError("مبحث یافت نشد.")
    qs = pick_questions(db, node_id, count, sequence_from, sequence_to, parity)
    session = m.TestSession(
        user_id=user.id, node_id=node_id, book_id=node.book_id, task_id=task_id,
        timed=timed, time_limit_seconds=time_limit_seconds if timed else None,
        sequence_from=sequence_from, sequence_to=sequence_to, parity=parity,
        status="in_progress", session_kind="normal", session_date=date.today(),
    )
    db.add(session)
    db.flush()
    # ترتیب نمایش = ترتیب صعودی شماره سوال در کتاب (qs از قبل مرتب است)
    for pos, q in enumerate(qs):
        db.add(m.TestSessionQuestion(session_id=session.id, question_id=q.id, display_order=pos))
    _remember_parity(db, user.id, node_id, parity)
    log_behavior(db, user.id, "test_session_started",
                 {"session_id": session.id, "node_id": node_id, "count": count, "parity": parity})
    return session


def create_review_session(db: Session, user: m.User, limit: int | None = None) -> m.TestSession:
    """مرور: خوشه موضوعی نزدیک + ترتیب تصادفی + سقف ۲۵."""
    limit = min(limit or cfg.REVIEW_MAX_QUESTIONS_PER_SESSION,
                cfg.REVIEW_MAX_QUESTIONS_PER_SESSION)
    items = db.scalars(
        select(m.ReviewQueue)
        .where(m.ReviewQueue.user_id == user.id, m.ReviewQueue.status == "open")
        .order_by(m.ReviewQueue.priority.desc(), m.ReviewQueue.scheduled_for)
    ).all()
    if not items:
        raise SelectionError("صف مرور خالی است.")

    # خوشه موضوعی: nodeی که بیشترین مورد مرور را دارد + مباحث نزدیک (والد مشترک تا عمق ۲)
    qid_to_node: dict[int, int | None] = {}
    for it in items:
        q = db.get(m.Question, it.question_id)
        ts = db.get(m.TestSet, q.test_set_id) if q else None
        qid_to_node[it.question_id] = ts.node_id if ts else None

    buckets: dict[int | None, list[m.ReviewQueue]] = {}
    for it in items:
        buckets.setdefault(qid_to_node[it.question_id], []).append(it)
    main_node = max(buckets, key=lambda k: len(buckets[k]))
    cluster = list(buckets[main_node])

    if len(cluster) < cfg.REVIEW_MIN_CLUSTER_SIZE and main_node:
        near = set(_near_nodes(db, main_node))
        for node_id, group in buckets.items():
            if node_id in near and node_id != main_node:
                cluster.extend(group)
            if len(cluster) >= cfg.REVIEW_MIN_CLUSTER_SIZE:
                break
    if len(cluster) < cfg.REVIEW_MIN_CLUSTER_SIZE:
        for it in items:
            if it not in cluster:
                cluster.append(it)
            if len(cluster) >= cfg.REVIEW_MIN_CLUSTER_SIZE:
                break

    cluster = cluster[:limit]
    random.shuffle(cluster)

    session = m.TestSession(user_id=user.id, session_kind="review", parity="any",
                            status="in_progress", session_date=date.today())
    db.add(session)
    db.flush()
    for pos, it in enumerate(cluster):
        db.add(m.TestSessionQuestion(session_id=session.id, question_id=it.question_id,
                                     display_order=pos))
    log_behavior(db, user.id, "review_session_started",
                 {"session_id": session.id, "count": len(cluster)})
    return session


def _near_nodes(db: Session, node_id: int) -> list[int]:
    """نزدیک = والد مشترک تا عمق ۲."""
    node = db.get(m.BookNode, node_id)
    if not node:
        return []
    anc = node
    for _ in range(2):
        if anc.parent_id:
            anc = db.get(m.BookNode, anc.parent_id)
    return descendant_node_ids(db, anc.id)


def upsert_review(db: Session, user_id: int, question_id: int, result: str) -> None:
    if result not in ("wrong", "unanswered"):
        return
    item = db.scalar(select(m.ReviewQueue).where(
        m.ReviewQueue.user_id == user_id, m.ReviewQueue.question_id == question_id))
    if not item:
        item = m.ReviewQueue(user_id=user_id, question_id=question_id, reason=result,
                             priority=1, status="open", scheduled_for=date.today(),
                             wrong_count=0, unanswered_count=0)
        db.add(item)
    item.status = "open"
    item.reason = result
    if result == "wrong":
        item.wrong_count += 1
    else:
        item.unanswered_count += 1
    critical = item.wrong_count >= cfg.REVIEW_CRITICAL_WRONG_COUNT
    item.priority = 3 if critical else (2 if result == "wrong" else 1)
    days = cfg.REVIEW_CRITICAL_MAX_DAYS if critical else cfg.REVIEW_NORMAL_MAX_DAYS
    item.scheduled_for = date.today() + timedelta(days=days)


def resolve_review(db: Session, user_id: int, question_id: int) -> bool:
    item = db.scalar(select(m.ReviewQueue).where(
        m.ReviewQueue.user_id == user_id, m.ReviewQueue.question_id == question_id,
        m.ReviewQueue.status == "open"))
    if not item:
        return False
    item.status = "resolved"
    return True


def finish_session(db: Session, user: m.User, session: m.TestSession,
                   answers: list[dict], actual_duration_minutes: int | None) -> dict:
    """idempotent — اگر قبلاً completed باشد نتیجه موجود برمی‌گردد."""
    if session.status == "completed":
        return session_result(db, user, session)

    answer_map = {a["question_id"]: a for a in answers}
    sq = db.scalars(select(m.TestSessionQuestion).where(
        m.TestSessionQuestion.session_id == session.id)).all()

    points = 0
    correct = wrong = unanswered = 0
    for item in sq:
        q = db.get(m.Question, item.question_id)
        given = answer_map.get(item.question_id, {})
        choice = given.get("answer")
        if choice is None:
            result = "unanswered"
            unanswered += 1
        elif q.answer_key is not None and int(choice) == q.answer_key:
            result = "correct"
            correct += 1
        else:
            result = "wrong"
            wrong += 1
        db.add(m.QuestionAttempt(
            session_id=session.id, question_id=q.id, user_id=user.id,
            answer=choice, result=result, is_imported=False,
            response_time_seconds=given.get("response_time_seconds"),
        ))
        if result == "correct":
            if session.session_kind == "review":
                resolve_review(db, user.id, q.id)
                points += rewards.award(db, user, "review_success", cfg.POINTS_SUCCESSFUL_REVIEW,
                                        "مرور موفق", "question", q.id)
            else:
                points += rewards.award(db, user, "correct_answer", cfg.POINTS_CORRECT_ANSWER,
                                        "پاسخ درست", "question", q.id)
        else:
            upsert_review(db, user.id, q.id, result)

    session.status = "completed"
    session.ended_at = datetime.utcnow()
    session.actual_duration_minutes = actual_duration_minutes
    session.points_awarded = points

    if session.task_id:
        task = db.get(m.Task, session.task_id)
        if task and task.status != "completed":
            task.status = "completed"
            task.completed_at = datetime.utcnow()

    rewards.touch_streak(db, user)
    rewards.check_badges(db, user)
    log_behavior(db, user.id, "test_session_completed", {
        "session_id": session.id, "correct": correct, "wrong": wrong,
        "unanswered": unanswered, "duration": actual_duration_minutes,
    })
    _maybe_adjust_time_limit(db, user, session)
    return session_result(db, user, session)


def _maybe_adjust_time_limit(db: Session, user: m.User, session: m.TestSession) -> None:
    """V2: کاهش تدریجی time limit در Timed — ≥۲۰ attempt و accuracy ≥۷۵٪."""
    if not (session.timed and user.auto_time_adjust and session.node_id):
        return
    qs = [q.id for q in questions_of_node(db, session.node_id)]
    if not qs:
        return
    rows = db.execute(select(m.QuestionAttempt.result).where(
        m.QuestionAttempt.user_id == user.id, m.QuestionAttempt.question_id.in_(qs))).all()
    answered = [r[0] for r in rows if r[0] in ("correct", "wrong")]
    if len(rows) >= 20 and answered and (sum(1 for r in answered if r == "correct") / len(answered)) >= 0.75:
        session.auto_time_adjust_applied = True


def session_result(db: Session, user: m.User, session: m.TestSession) -> dict:
    rows = db.scalars(select(m.QuestionAttempt).where(
        m.QuestionAttempt.session_id == session.id)).all()
    correct = sum(1 for r in rows if r.result == "correct")
    wrong = sum(1 for r in rows if r.result == "wrong")
    unanswered = sum(1 for r in rows if r.result == "unanswered")
    answered = correct + wrong
    return {
        "session_id": session.id,
        "kind": session.session_kind,
        "total": len(rows),
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "accuracy": round(correct / answered, 4) if answered else 0.0,
        "parity": session.parity,
        "range": [session.sequence_from, session.sequence_to],
        "duration_minutes": session.actual_duration_minutes,
        "points_awarded": session.points_awarded,
        "auto_time_adjust_applied": session.auto_time_adjust_applied,
        "items": [
            {
                "question_id": r.question_id,
                "sequence_no": (db.get(m.Question, r.question_id).sequence_no
                                if db.get(m.Question, r.question_id) else None),
                "answer": r.answer,
                "result": r.result,
                "answer_key": (db.get(m.Question, r.question_id).answer_key
                               if db.get(m.Question, r.question_id) else None),
            }
            for r in rows
        ],
    }
