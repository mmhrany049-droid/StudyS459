"""کتاب‌ها، درخت مبحث، بانک تست (V2.2 — سند 02)، و ورود گذشته (سند 03)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..schemas import BulkAnswerKey, ImportByBook, QuestionPatch, RangeCreate
from ..services import past_import, question_bank
from ..services.common import current_user, node_stats

router = APIRouter(prefix="/api", tags=["books"])


@router.get("/books")
def list_books(db: Session = Depends(get_db)):
    user = current_user(db)
    out = []
    for b in db.scalars(select(m.Book).order_by(m.Book.id)).all():
        roots = db.scalars(select(m.BookNode).where(
            m.BookNode.book_id == b.id, m.BookNode.parent_id.is_(None))).all()
        total_q = db.scalar(select(m.Question.id).where(m.Question.book_id == b.id))
        stats = [node_stats(db, user.id, r.id) for r in roots]
        total = sum(s["total"] for s in stats)
        attempted = sum(s["attempted"] for s in stats)
        correct = sum(s["correct"] for s in stats)
        wrong = sum(s["wrong"] for s in stats)
        out.append({
            "id": b.id, "title": b.title, "publisher": b.publisher,
            "subject": b.subject.name, "subject_id": b.subject_id,
            "color": b.subject.color, "active": b.active,
            "has_difficulty_levels": b.has_difficulty_levels,
            "chapters": len(roots),
            "has_questions": total_q is not None,
            "total_questions": total,
            "coverage": round(attempted / total, 3) if total else 0.0,
            "accuracy": round(correct / (correct + wrong), 3) if (correct + wrong) else 0.0,
        })
    return out


@router.patch("/books/{book_id}/activate")
def toggle_book(book_id: int, active: bool = True, db: Session = Depends(get_db)):
    book = db.get(m.Book, book_id)
    if not book:
        raise HTTPException(404, "کتاب یافت نشد.")
    book.active = active
    db.commit()
    return {"id": book.id, "active": book.active}


@router.get("/books/{book_id}/nodes")
def book_tree(book_id: int, with_stats: bool = True, db: Session = Depends(get_db)):
    user = current_user(db)
    book = db.get(m.Book, book_id)
    if not book:
        raise HTTPException(404, "کتاب یافت نشد.")
    nodes = db.scalars(select(m.BookNode).where(m.BookNode.book_id == book_id)
                       .order_by(m.BookNode.parent_id, m.BookNode.order_index)).all()
    sets = {ts.node_id: ts for ts in db.scalars(select(m.TestSet).where(
        m.TestSet.book_id == book_id)).all()}

    by_parent: dict[int | None, list[m.BookNode]] = {}
    for n in nodes:
        by_parent.setdefault(n.parent_id, []).append(n)

    def build(parent_id):
        out = []
        for n in by_parent.get(parent_id, []):
            item = {
                "id": n.id, "title": n.title, "node_type": n.node_type,
                "order_index": n.order_index,
                "has_test_set": n.id in sets,
                "test_set_id": sets[n.id].id if n.id in sets else None,
                "children": build(n.id),
            }
            if with_stats:
                s = node_stats(db, user.id, n.id)
                item["stats"] = {
                    "total": s["total"], "with_answer_key": s["with_answer_key"],
                    "attempted": s["attempted"], "coverage": s["coverage"],
                    "accuracy": s["accuracy"], "open_review": s["open_review"],
                }
            out.append(item)
        return out

    return {"book": {"id": book.id, "title": book.title, "publisher": book.publisher,
                     "subject": book.subject.name,
                     "has_difficulty_levels": book.has_difficulty_levels},
            "nodes": build(None)}


# ------------------------------------------------------------------ بانک تست
# مسیرهای رسمی سند ۰۹ نسخه ۲.۲ زیر /books/{book_id}/nodes/{node_id}/... هستند.
# مسیرهای کوتاه /nodes/{node_id}/... هم به‌عنوان نام مستعار حفظ می‌شوند.
@router.get("/books/{book_id}/nodes/{node_id}/questions")
@router.get("/nodes/{node_id}/questions")
def node_questions(node_id: int,
                   book_id: int | None = None,
                   only_missing_key: bool = Query(False),
                   only_unattempted: bool = Query(False),
                   include_archived: bool = Query(False),
                   db: Session = Depends(get_db)):
    user = current_user(db)
    try:
        return question_bank.list_questions(db, user.id, node_id, only_missing_key,
                                            only_unattempted, include_archived)
    except question_bank.BankError as e:
        raise HTTPException(404 if "یافت نشد" in str(e) else 400, str(e))


@router.post("/books/{book_id}/nodes/{node_id}/questions/range")
@router.post("/nodes/{node_id}/questions/range")
def create_range(node_id: int, body: RangeCreate, book_id: int | None = None,
                 db: Session = Depends(get_db)):
    try:
        res = question_bank.create_range(db, node_id, body.from_no, body.to_no,
                                         body.difficulty_level, body.question_tag)
        db.commit()
        return res
    except question_bank.BankError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.put("/books/{book_id}/nodes/{node_id}/questions/bulk")
@router.put("/nodes/{node_id}/questions/bulk")
def bulk_answer_key(node_id: int, body: BulkAnswerKey, book_id: int | None = None,
                    db: Session = Depends(get_db)):
    user = current_user(db)
    try:
        res = question_bank.save_answer_keys(
            db, node_id, [i.model_dump() for i in body.items], body.compact)
        from ..services.rewards import check_badges
        check_badges(db, user)
        db.commit()
        return res
    except question_bank.BankError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.patch("/questions/{question_id}")
def patch_question(question_id: int, body: QuestionPatch, db: Session = Depends(get_db)):
    try:
        res = question_bank.patch_question(
            db, question_id, body.model_dump(exclude_unset=True))
        db.commit()
        return res
    except question_bank.BankError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)):
    try:
        res = question_bank.delete_question(db, question_id)
        db.commit()
        return res
    except question_bank.BankError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("/books/{book_id}/export")
def export_bank(book_id: int, node_id: int | None = None, db: Session = Depends(get_db)):
    try:
        data = question_bank.export_bank(db, book_id, node_id)
    except question_bank.BankError as e:
        raise HTTPException(400, str(e))
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="bank_book_{book_id}.json"'},
    )


# ------------------------------------------------------------------ ورود گذشته
@router.get("/books/{book_id}/answer-sheet")
def answer_sheet(book_id: int, node_id: int | None = None,
                 only_unattempted: bool = False,
                 only_with_key: bool = True,
                 db: Session = Depends(get_db)):
    user = current_user(db)
    try:
        return past_import.book_answer_sheet(db, user.id, book_id, node_id,
                                             only_unattempted, only_with_key)
    except past_import.ImportError_ as e:
        raise HTTPException(400, str(e))


@router.post("/attempts/import-by-book")
def import_by_book(body: ImportByBook, db: Session = Depends(get_db)):
    user = current_user(db)
    try:
        res = past_import.import_by_book(
            db, user, body.book_id,
            [a.model_dump() for a in body.answers], body.session_date, body.notes)
        db.commit()
        return res
    except past_import.ImportError_ as e:
        db.rollback()
        raise HTTPException(400, str(e))
