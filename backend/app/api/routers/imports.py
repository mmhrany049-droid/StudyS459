"""Historical import router (book → big list → 1..4 or نزده → submit)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db import models
from ...db.base import get_db
from ...services import common, imports
from ..deps import current_user, parse_day

router = APIRouter(tags=["historical-import"])


class ImportItem(BaseModel):
    question_id: int
    choice: Optional[str] = None
    unanswered: bool = False
    note: Optional[str] = None


class ImportPayload(BaseModel):
    book_id: int
    items: list[ImportItem]
    date: Optional[str] = None
    topic_id: Optional[int] = None
    note: Optional[str] = None
    import_key: Optional[str] = None


@router.get("/attempts/import-sheet")
def import_sheet(
    book_id: int,
    topic_id: Optional[int] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    return imports.book_import_sheet(db, user, book_id, topic_id=topic_id)


@router.post("/attempts/import-by-book")
def import_by_book(
    payload: ImportPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = imports.import_attempts(
        db,
        user,
        book_id=payload.book_id,
        items=[item.model_dump() for item in payload.items],
        date_value=parse_day(payload.date),
        topic_id=payload.topic_id,
        note=payload.note,
        import_key=payload.import_key,
    )
    db.commit()
    return result


@router.get("/attempts/import-summary")
def import_summary(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return imports.import_summary(db, user)
