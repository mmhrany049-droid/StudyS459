"""تحلیل — Coverage جدا از Accuracy جدا از Volume (07_ANALYTICS_V1)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (Book, BookNode, Question, QuestionAttempt, QuestionTopicMap,
                        Subject, TestSession, User)


def _stats_for_question_ids(db: Session, user_id: int, qids: list[int]) -> dict:
    if not qids:
        return {"total": 0, "attempted": 0, "correct": 0, "wrong": 0, "unanswered": 0,
                "coverage": 0.0, "accuracy": 0.0, "volume": 0}
    rows = db.execute(
        select(QuestionAttempt.result, func.count(QuestionAttempt.id))
        .where(QuestionAttempt.user_id == user_id,
               QuestionAttempt.question_id.in_(qids),
               QuestionAttempt.result.in_(("correct", "wrong")))
        .group_by(QuestionAttempt.result)).all()
    res = {r: c for r, c in rows}
    correct, wrong = res.get("correct", 0), res.get("wrong", 0)
    unans_rows = db.execute(
        select(func.count(func.distinct(QuestionAttempt.question_id))).where(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(qids),
            QuestionAttempt.result == "unanswered")).scalar() or 0
    attempted_q = db.scalar(
        select(func.count(func.distinct(QuestionAttempt.question_id))).where(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(qids))) or 0
    volume = correct + wrong + unans_rows  # حجم کل تلاشها تقریبی
    total_attempts = db.scalar(
        select(func.count(QuestionAttempt.id)).where(
            QuestionAttempt.user_id == user_id,
            QuestionAttempt.question_id.in_(qids))) or 0
    answered = correct + wrong
    return {
        "total": len(qids),
        "attempted": attempted_q,
        "correct": correct, "wrong": wrong, "unanswered": unans_rows,
        "coverage": round(attempted_q / len(qids), 4) if qids else 0.0,
        "accuracy": round(correct / answered, 4) if answered else 0.0,
        "volume": total_attempts,
    }


def node_question_ids(db: Session, node_id: int, include_children: bool = True) -> list[int]:
    ids = [node_id]
    if include_children:
        frontier = [node_id]
        while frontier:
            children = list(db.scalars(
                select(BookNode.id).where(BookNode.parent_id.in_(frontier))))
            ids.extend(children)
            frontier = children
    qids = db.scalars(
        select(QuestionTopicMap.question_id)
        .where(QuestionTopicMap.node_id.in_(ids))).all()
    return list(set(qids))


def overview(db: Session, user: User) -> dict:
    all_qids = list(db.scalars(select(Question.id)))
    stats = _stats_for_question_ids(db, user.id, all_qids)
    sessions = db.scalar(
        select(func.count(TestSession.id)).where(
            TestSession.user_id == user.id, TestSession.status == "completed")) or 0
    imported = db.scalar(
        select(func.count(TestSession.id)).where(
            TestSession.user_id == user.id, TestSession.is_imported == True)) or 0  # noqa: E712

    # روند روزانه (۱۴ روز اخیر)
    today = dt.datetime.now(dt.timezone.utc).date()
    trend = []
    for i in range(13, -1, -1):
        d = today - dt.timedelta(days=i)
        rows = db.execute(
            select(QuestionAttempt.result, func.count(QuestionAttempt.id))
            .where(QuestionAttempt.user_id == user.id,
                   func.date(QuestionAttempt.answered_at) == d)
            .group_by(QuestionAttempt.result)).all()
        r = {k: v for k, v in rows}
        trend.append({
            "date": d.isoformat(),
            "correct": r.get("correct", 0), "wrong": r.get("wrong", 0),
            "unanswered": r.get("unanswered", 0),
        })
    return {**stats, "sessions": sessions, "imported_sessions": imported, "trend": trend}


def book_progress(db: Session, user: User, book_id: int) -> dict:
    book = db.get(Book, book_id)
    if book is None:
        return {}
    qids = list(db.scalars(select(Question.id).where(Question.book_id == book_id)))
    stats = _stats_for_question_ids(db, user.id, qids)

    # جدول درخت فصل/بخش
    def node_row(n: BookNode) -> dict:
        qs = node_question_ids(db, n.id, include_children=True)
        s = _stats_for_question_ids(db, user.id, qs)
        return {
            "id": n.id, "title": n.title, "node_type": n.node_type,
            "code": n.code, "order": n.order_index,
            **s,
            "children": [node_row(c) for c in nodes_by_parent.get(n.id, [])],
        }

    nodes = list(db.scalars(select(BookNode).where(BookNode.book_id == book_id)
                            .order_by(BookNode.order_index)))
    nodes_by_parent: dict[int, list[BookNode]] = {}
    for n in nodes:
        nodes_by_parent.setdefault(n.parent_id if n.parent_id else 0, []).append(n)
    roots = nodes_by_parent.get(0, [])
    return {"book": {"id": book.id, "title": book.title, "publisher": book.publisher},
            "stats": stats, "tree": [node_row(r) for r in roots]}


def weaknesses(db: Session, user: User, limit: int = 10) -> list[dict]:
    """سیگنالهای ضعف: error rate + unanswered + حجم + recency."""
    out = []
    leaf_nodes = list(db.scalars(
        select(BookNode).where(BookNode.node_type.in_(("title", "section", "subsection", "leaf")))))
    for n in leaf_nodes:
        qs = node_question_ids(db, n.id, include_children=False)
        if not qs:
            continue
        s = _stats_for_question_ids(db, user.id, qs)
        if s["attempted"] < 3:
            continue
        error_rate = 1 - s["accuracy"]
        last = db.scalar(
            select(func.max(QuestionAttempt.answered_at)).where(
                QuestionAttempt.user_id == user.id,
                QuestionAttempt.question_id.in_(qs)))
        book = db.get(Book, n.book_id)
        subject = db.get(Subject, book.subject_id) if book else None
        score = error_rate * 2 + (s["unanswered"] / max(s["attempted"], 1))
        out.append({
            "node_id": n.id, "title": n.title, "book": book.title if book else "",
            "subject": subject.name if subject else "",
            "accuracy": s["accuracy"], "error_rate": round(error_rate, 3),
            "unanswered": s["unanswered"], "attempted": s["attempted"],
            "coverage": s["coverage"], "weakness_score": round(score, 3),
            "last_activity": last.isoformat() if last else None,
        })
    out.sort(key=lambda x: -x["weakness_score"])
    return out[:limit]
