"""سرویس‌های مشترک: کاربر جاری، درخت مبحث، آمار Coverage/Accuracy."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m


def current_user(db: Session) -> m.User:
    user = db.scalars(select(m.User).limit(1)).first()
    if not user:
        user = m.User(username="me", display_name="کاربر")
        db.add(user)
        db.flush()
        db.add(m.UserProfile(user_id=user.id, personality_json={}, preferences_json={}))
        db.commit()
    return user


def descendant_node_ids(db: Session, node_id: int) -> list[int]:
    """همه فرزندان یک node (شامل خودش)."""
    out = [node_id]
    frontier = [node_id]
    while frontier:
        rows = db.scalars(
            select(m.BookNode.id).where(m.BookNode.parent_id.in_(frontier))
        ).all()
        rows = [r for r in rows if r not in out]
        if not rows:
            break
        out.extend(rows)
        frontier = rows
    return out


def node_path(db: Session, node_id: int) -> list[m.BookNode]:
    path: list[m.BookNode] = []
    node = db.get(m.BookNode, node_id)
    while node:
        path.insert(0, node)
        node = db.get(m.BookNode, node.parent_id) if node.parent_id else None
    return path


def node_full_title(db: Session, node_id: int) -> str:
    return " ← ".join(n.title for n in node_path(db, node_id))


def questions_of_node(db: Session, node_id: int, include_archived: bool = False):
    """سوال‌های یک مبحث و همه زیرمبحث‌هایش (از طریق test_set یا topic map)."""
    ids = descendant_node_ids(db, node_id)
    q = (
        select(m.Question)
        .join(m.TestSet, m.Question.test_set_id == m.TestSet.id)
        .where(m.TestSet.node_id.in_(ids))
    )
    if not include_archived:
        q = q.where(m.Question.archived.is_(False))
    rows = list(db.scalars(q.order_by(m.Question.sequence_no)).all())
    mapped = db.scalars(
        select(m.Question)
        .join(m.QuestionTopicMap, m.QuestionTopicMap.question_id == m.Question.id)
        .where(m.QuestionTopicMap.node_id.in_(ids))
    ).all()
    seen = {r.id for r in rows}
    for r in mapped:
        if r.id not in seen and (include_archived or not r.archived):
            rows.append(r)
            seen.add(r.id)
    return rows


def node_stats(db: Session, user_id: int, node_id: int) -> dict:
    """Coverage / Accuracy / Volume برای یک مبحث — سند 07_ANALYTICS."""
    qs = questions_of_node(db, node_id)
    total = len(qs)
    with_key = sum(1 for q in qs if q.answer_key is not None)
    if total == 0:
        return {
            "total": 0, "with_answer_key": 0, "attempted": 0, "coverage": 0.0,
            "correct": 0, "wrong": 0, "unanswered": 0, "accuracy": 0.0,
            "volume": 0, "open_review": 0, "has_bank": False,
        }
    qids = [q.id for q in qs]
    rows = db.execute(
        select(m.QuestionAttempt.question_id, m.QuestionAttempt.result)
        .where(m.QuestionAttempt.user_id == user_id, m.QuestionAttempt.question_id.in_(qids))
    ).all()
    attempted_ids = {r[0] for r in rows}
    correct = sum(1 for r in rows if r[1] == "correct")
    wrong = sum(1 for r in rows if r[1] == "wrong")
    unanswered = sum(1 for r in rows if r[1] == "unanswered")
    answered = correct + wrong
    open_review = db.scalar(
        select(func.count(m.ReviewQueue.id)).where(
            m.ReviewQueue.user_id == user_id,
            m.ReviewQueue.question_id.in_(qids),
            m.ReviewQueue.status == "open",
        )
    ) or 0
    return {
        "total": total,
        "with_answer_key": with_key,
        "attempted": len(attempted_ids),
        "coverage": round(len(attempted_ids) / total, 4),
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "accuracy": round(correct / answered, 4) if answered else 0.0,
        "volume": len(rows),
        "open_review": open_review,
        "has_bank": total > 0,
    }


def log_behavior(db: Session, user_id: int, event_type: str, payload: dict | None = None,
                 source: str = "app") -> None:
    db.add(m.BehaviorEvent(
        user_id=user_id, event_type=event_type,
        payload_json=payload or {}, source=source, event_time=datetime.utcnow(),
    ))


def parse_compact_answer_key(text: str) -> dict[int, int | None]:
    """
    S1/سند 02: پشتیبانی از ورودی فشرده.
    فرمت‌های مجاز:  "1:2, 2:3, 3:1"  یا  "2 3 1 4"  (ترتیبی از شماره ۱)
    0 یا - یا x = نزده / بدون کلید
    """
    text = (text or "").strip()
    if not text:
        return {}
    out: dict[int, int | None] = {}
    tokens = [t for t in text.replace("\n", ",").replace("،", ",").replace(";", ",").split(",") if t.strip()]
    if any(":" in t for t in tokens):
        for t in tokens:
            if ":" not in t:
                continue
            k, v = t.split(":", 1)
            try:
                seq = int(k.strip())
            except ValueError:
                continue
            v = v.strip()
            out[seq] = int(v) if v.isdigit() and 1 <= int(v) <= 4 else None
        return out
    flat = text.replace(",", " ").replace("،", " ").split()
    for i, v in enumerate(flat, start=1):
        out[i] = int(v) if v.isdigit() and 1 <= int(v) <= 4 else None
    return out


def today() -> date:
    return date.today()
