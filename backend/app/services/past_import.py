"""
ورود تست‌های زده‌شده قبلی — سند 03_PAST_ATTEMPT_ENTRY.
فقط انتخاب کتاب → لیست بزرگ چهارگزینه‌ای + «نزده».
is_imported = true، بدون سکه، unanswered جدا از wrong.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from . import rewards
from .common import descendant_node_ids, log_behavior, node_full_title
from .test_engine import upsert_review


class ImportError_(Exception):
    pass


def book_answer_sheet(db: Session, user_id: int, book_id: int,
                      node_id: int | None = None,
                      only_unattempted: bool = False,
                      only_with_key: bool = True) -> dict:
    """لیست بزرگ سوال‌های کتاب، گروه‌بندی‌شده بر اساس فصل/مبحث."""
    book = db.get(m.Book, book_id)
    if not book:
        raise ImportError_("کتاب یافت نشد.")
    q = select(m.TestSet).where(m.TestSet.book_id == book_id)
    if node_id:
        q = q.where(m.TestSet.node_id.in_(descendant_node_ids(db, node_id)))
    sets = db.scalars(q).all()

    all_ids: list[int] = []
    groups = []
    for ts in sets:
        questions = db.scalars(
            select(m.Question)
            .where(m.Question.test_set_id == ts.id, m.Question.archived.is_(False))
            .order_by(m.Question.sequence_no)
        ).all()
        if only_with_key:
            questions = [x for x in questions if x.answer_key is not None]
        if not questions:
            continue
        all_ids.extend(x.id for x in questions)
        groups.append((ts, questions))

    attempted: dict[int, int] = {}
    if all_ids:
        for qid, in db.execute(
            select(m.QuestionAttempt.question_id).where(
                m.QuestionAttempt.user_id == user_id,
                m.QuestionAttempt.question_id.in_(all_ids))
        ).all():
            attempted[qid] = attempted.get(qid, 0) + 1

    out_groups = []
    total = 0
    for ts, questions in groups:
        items = []
        for x in questions:
            count = attempted.get(x.id, 0)
            if only_unattempted and count:
                continue
            items.append({
                "id": x.id, "sequence_no": x.sequence_no,
                "answer_key": x.answer_key, "difficulty_level": x.difficulty_level,
                "attempt_count": count,
            })
        if not items:
            continue
        total += len(items)
        out_groups.append({
            "test_set_id": ts.id,
            "node_id": ts.node_id,
            "title": node_full_title(db, ts.node_id) if ts.node_id else ts.title,
            "short_title": (db.get(m.BookNode, ts.node_id).title
                            if ts.node_id else ts.title),
            "questions": items,
        })
    return {
        "book": {"id": book.id, "title": book.title, "publisher": book.publisher},
        "total_questions": total,
        "groups": out_groups,
    }


def _resolve_refs(db: Session, book_id: int, answers: list[dict]) -> list[dict]:
    """
    سند ۰۹: { sequence_ref یا question_id, choice }.
    sequence_ref را به question_id واقعی همان کتاب ترجمه می‌کند.
    اگر node_id داده شود دقیق‌تر است؛ وگرنه شماره در کل کتاب باید یکتا باشد.
    """
    out: list[dict] = []
    cache: dict[tuple[int | None, int], int | None] = {}
    for a in answers:
        qid = a.get("question_id")
        if not qid:
            seq = a.get("sequence_ref")
            if seq is None:
                continue
            node_id = a.get("node_id")
            key = (node_id, int(seq))
            if key not in cache:
                stmt = (
                    select(m.Question.id)
                    .join(m.TestSet, m.TestSet.id == m.Question.test_set_id)
                    .join(m.BookNode, m.BookNode.id == m.TestSet.node_id)
                    .where(m.BookNode.book_id == book_id,
                           m.Question.sequence_no == int(seq),
                           m.Question.archived.is_(False))
                )
                if node_id:
                    ids = descendant_node_ids(db, int(node_id))
                    stmt = stmt.where(m.BookNode.id.in_(ids))
                found = db.scalars(stmt).all()
                # فقط وقتی یکتا باشد قابل اعتماد است
                cache[key] = found[0] if len(found) == 1 else None
            qid = cache[key]
            if not qid:
                continue
        out.append({**a, "question_id": int(qid)})
    return out


def import_by_book(db: Session, user: m.User, book_id: int, answers: list[dict],
                   session_date: date | None = None, notes: str = "") -> dict:
    book = db.get(m.Book, book_id)
    if not book:
        raise ImportError_("کتاب یافت نشد.")
    # سند ۰۹: پاسخ می‌تواند با question_id یا با sequence_ref (+node_id) بیاید.
    answers = _resolve_refs(db, book_id, answers)
    if not answers:
        raise ImportError_("هیچ پاسخی برای ثبت وجود ندارد.")

    session = m.TestSession(
        user_id=user.id, book_id=book_id, session_kind="import",
        status="completed", is_imported=True, parity="any",
        session_date=session_date or date.today(),
        started_at=datetime.utcnow(), ended_at=datetime.utcnow(),
    )
    db.add(session)
    db.flush()

    correct = wrong = unanswered = skipped = 0
    for pos, a in enumerate(answers):
        q = db.get(m.Question, int(a["question_id"]))
        if not q:
            skipped += 1
            continue
        choice = a.get("choice")
        if choice is None:
            result = "unanswered"
            unanswered += 1
        elif q.answer_key is None:
            skipped += 1     # بدون کلید نمی‌توان تصحیح کرد
            continue
        elif int(choice) == q.answer_key:
            result = "correct"
            correct += 1
        else:
            result = "wrong"
            wrong += 1
        db.add(m.TestSessionQuestion(session_id=session.id, question_id=q.id,
                                     display_order=pos))
        db.add(m.QuestionAttempt(
            session_id=session.id, question_id=q.id, user_id=user.id,
            answer=int(choice) if choice is not None else None,
            result=result, is_imported=True,
            uncertain=bool(a.get("uncertain")), answered_at=datetime.utcnow(),
        ))
        if result in ("wrong", "unanswered"):
            upsert_review(db, user.id, q.id, result)

    answered = correct + wrong
    log_behavior(db, user.id, "past_import", {
        "session_id": session.id, "book_id": book_id,
        "correct": correct, "wrong": wrong, "unanswered": unanswered,
    })
    rewards.check_badges(db, user)
    return {
        "session_id": session.id,
        "imported": correct + wrong + unanswered,
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "skipped_without_key": skipped,
        "accuracy": round(correct / answered, 4) if answered else 0.0,
        "coins_awarded": 0,
        "message": "ورود تست‌های گذشته ثبت شد. سکه‌ای تعلق نمی‌گیرد (کار گذشته است).",
    }
