"""FastAPI dependencies and shared request helpers."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from ..db import models
from ..db.base import get_db
from ..services import common


def db_session() -> Session:  # pragma: no cover - thin wrapper for typing
    yield from get_db()


def current_user(
    user_id: Optional[int] = Query(None, description="شناسه کاربر (اختیاری؛ محصول تک‌کاربره است)"),
    db: Session = Depends(get_db),
) -> models.User:
    return common.resolve_user(db, user_id)


def parse_day(value: Optional[str]):
    """Accept Jalali (1405/06/24) or ISO strings from the UI."""
    if value in (None, "", "today"):
        return None
    return common.parse_date_if_string(value)
