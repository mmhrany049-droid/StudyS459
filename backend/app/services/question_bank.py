"""
بانک تست داخل برنامه — سند 02_QUESTION_BANK_UI.
- افزودن بازه سریع (from..to)
- پاسخ‌نامه چهارگزینه‌ای (لیست یا فشرده)
- حذف نرم برای سوال دارای history (S9)
- فیلتر «بدون جواب» / «بدون attempt» (S4)
- خلاصه مبحث قبل از ورود پاسخ (S3)
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from .common import node_full_title, node_stats, parse_compact_answer_key


class BankError(Exception):
    pass


def get_or_create_test_set(db: Session, node_id: int) -> m.TestSet:
    node = db.get(m.BookNode, node_id)
    if not node:
        raise BankError("مبحث یافت نشد.")
    ts = db.scalar(select(m.TestSet).where(m.TestSet.node_id == node_id))
    if not ts:
        ts = m.TestSet(book_id=node.book_id, node_id=node_id, title=node.title,
                       test_type=node.metadata_json.get("test_type", "normal")
                       if isinstance(node.metadata_json, dict) else "normal")
        db.add(ts)
        db.flush()
    return ts


def create_range(db: Session, node_id: int, from_no: int, to_no: int,
                 difficulty_level: int | None = None,
                 question_tag: str | None = None) -> dict:
    if to_no < from_no:
        raise BankError("شماره پایان باید بزرگ‌تر یا مساوی شماره شروع باشد.")
    if to_no - from_no > 999:
        raise BankError("حداکثر ۱۰۰۰ سوال در یک بازه.")
    ts = get_or_create_test_set(db, node_id)
    existing = {
        q.sequence_no: q
        for q in db.scalars(select(m.Question).where(m.Question.test_set_id == ts.id)).all()
    }
    created = restored = 0
    for seq in range(from_no, to_no + 1):
        if seq in existing:
            q = existing[seq]
            if q.archived:
                q.archived = False
                restored += 1
            continue
        db.add(m.Question(
            book_id=ts.book_id, test_set_id=ts.id,
            stable_key=f"ts{ts.id}-q{seq}", sequence_no=seq,
            difficulty_level=difficulty_level, question_tag=question_tag,
            answer_type="four_choice", answer_key=None,
        ))
        created += 1
    db.flush()
    return {"created": created, "restored": restored, "test_set_id": ts.id,
            "skipped": (to_no - from_no + 1) - created - restored}


def save_answer_keys(db: Session, node_id: int, items: list[dict],
                     compact: str | None = None) -> dict:
    ts = get_or_create_test_set(db, node_id)
    by_seq = {
        q.sequence_no: q
        for q in db.scalars(select(m.Question).where(m.Question.test_set_id == ts.id)).all()
    }
    payload: dict[int, dict] = {}
    for it in items:
        payload[int(it["sequence_no"])] = it
    if compact:
        for seq, key in parse_compact_answer_key(compact).items():
            payload.setdefault(seq, {"sequence_no": seq})["answer_key"] = key

    updated = created = 0
    for seq in sorted(payload):
        it = payload[seq]
        key = it.get("answer_key")
        if key is not None and int(key) not in (1, 2, 3, 4):
            raise BankError(f"گزینه نامعتبر برای سوال {seq}: باید ۱ تا ۴ باشد.")
        q = by_seq.get(seq)
        if not q:
            q = m.Question(book_id=ts.book_id, test_set_id=ts.id,
                           stable_key=f"ts{ts.id}-q{seq}", sequence_no=seq,
                           answer_type="four_choice")
            db.add(q)
            db.flush()
            by_seq[seq] = q
            created += 1
        q.answer_key = int(key) if key is not None else None
        if it.get("difficulty_level") is not None:
            q.difficulty_level = it["difficulty_level"]
        if it.get("question_tag") is not None:
            q.question_tag = it["question_tag"]
        updated += 1
    db.flush()
    return {"updated": updated, "created": created}


def list_questions(db: Session, user_id: int, node_id: int,
                   only_missing_key: bool = False,
                   only_unattempted: bool = False,
                   include_archived: bool = False) -> dict:
    if not db.get(m.BookNode, node_id):
        raise BankError("مبحث یافت نشد.")
    ts = db.scalar(select(m.TestSet).where(m.TestSet.node_id == node_id))
    rows: list[m.Question] = []
    if ts:
        q = select(m.Question).where(m.Question.test_set_id == ts.id)
        if not include_archived:
            q = q.where(m.Question.archived.is_(False))
        rows = list(db.scalars(q.order_by(m.Question.sequence_no)).all())

    qids = [q.id for q in rows]
    attempts: dict[int, list[str]] = {}
    if qids:
        for qid, result in db.execute(
            select(m.QuestionAttempt.question_id, m.QuestionAttempt.result).where(
                m.QuestionAttempt.user_id == user_id, m.QuestionAttempt.question_id.in_(qids))
        ).all():
            attempts.setdefault(qid, []).append(result)

    items = []
    for q in rows:
        hist = attempts.get(q.id, [])
        if only_missing_key and q.answer_key is not None:
            continue
        if only_unattempted and hist:
            continue
        items.append({
            "id": q.id,
            "sequence_no": q.sequence_no,
            "answer_key": q.answer_key,
            "difficulty_level": q.difficulty_level,
            "question_tag": q.question_tag,
            "archived": q.archived,
            "attempt_count": len(hist),
            "last_result": hist[-1] if hist else None,
            "wrong_count": sum(1 for r in hist if r == "wrong"),
            "unanswered_count": sum(1 for r in hist if r == "unanswered"),
        })

    stats = node_stats(db, user_id, node_id)
    return {
        "node_id": node_id,
        "node_title": node_full_title(db, node_id),
        "test_set_id": ts.id if ts else None,
        "summary": {  # S3
            "total": stats["total"],
            "with_answer_key": stats["with_answer_key"],
            "missing_answer_key": stats["total"] - stats["with_answer_key"],
            "attempted": stats["attempted"],
            "coverage": stats["coverage"],
            "accuracy": stats["accuracy"],
            "open_review": stats["open_review"],
        },
        "questions": items,
    }


def patch_question(db: Session, question_id: int, data: dict) -> dict:
    q = db.get(m.Question, question_id)
    if not q:
        raise BankError("سوال یافت نشد.")
    if "answer_key" in data and data["answer_key"] is not None:
        if int(data["answer_key"]) not in (1, 2, 3, 4):
            raise BankError("گزینه باید بین ۱ تا ۴ باشد.")
        q.answer_key = int(data["answer_key"])
    elif "answer_key" in data:
        q.answer_key = None
    for field in ("difficulty_level", "question_tag", "archived"):
        if data.get(field) is not None:
            setattr(q, field, data[field])
    db.flush()
    return {"id": q.id, "answer_key": q.answer_key, "archived": q.archived}


def delete_question(db: Session, question_id: int) -> dict:
    """S9 — اگر attempt دارد فقط آرشیو نرم."""
    q = db.get(m.Question, question_id)
    if not q:
        raise BankError("سوال یافت نشد.")
    has_history = (db.scalar(select(func.count(m.QuestionAttempt.id)).where(
        m.QuestionAttempt.question_id == question_id)) or 0) > 0
    if has_history:
        q.archived = True
        db.flush()
        return {"soft_deleted": True,
                "message": "این سوال سابقه پاسخ دارد؛ به‌جای حذف، آرشیو شد."}
    db.execute(m.QuestionTopicMap.__table__.delete().where(
        m.QuestionTopicMap.question_id == question_id))
    db.delete(q)
    db.flush()
    return {"soft_deleted": False, "message": "سوال حذف شد."}


def export_bank(db: Session, book_id: int, node_id: int | None = None) -> dict:
    """S11 — خروجی JSON بانک."""
    book = db.get(m.Book, book_id)
    if not book:
        raise BankError("کتاب یافت نشد.")
    q = select(m.TestSet).where(m.TestSet.book_id == book_id)
    if node_id:
        from .common import descendant_node_ids
        q = q.where(m.TestSet.node_id.in_(descendant_node_ids(db, node_id)))
    sets = db.scalars(q).all()
    out = []
    for ts in sets:
        questions = db.scalars(select(m.Question).where(
            m.Question.test_set_id == ts.id).order_by(m.Question.sequence_no)).all()
        out.append({
            "test_set_id": ts.id,
            "node_id": ts.node_id,
            "node_title": node_full_title(db, ts.node_id) if ts.node_id else ts.title,
            "test_type": ts.test_type,
            "questions": [
                {"sequence_no": x.sequence_no, "answer_key": x.answer_key,
                 "difficulty_level": x.difficulty_level, "tag": x.question_tag,
                 "archived": x.archived}
                for x in questions
            ],
        })
    return {
        "book": {"id": book.id, "stable_key": book.stable_key, "title": book.title,
                 "publisher": book.publisher},
        "exported_sets": out,
        "format_version": "ss459-bank-1.0",
    }
