"""Purposeful-questioning surfaces (V3.1 doc 07): channels, effects, transparency."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.timeutil import today_local
from ...db import models
from ...db.base import get_db
from ...services import common, questioning
from ..deps import current_user

router = APIRouter(tags=["questioning"])


@router.get("/questioning/channels")
def channels(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Every channel, its question budget and what its answers are allowed to move."""
    return questioning.payload(db, user)


@router.get("/questioning/daily")
def daily(
    date: Optional[str] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    """Today's 2–4 start/end questions plus the (bounded) effect of what was answered."""
    anchor = common.parse_date_if_string(date) if date else today_local()
    return questioning.daily_summary(db, user, day=anchor)


@router.get("/questioning/ordering")
def ordering(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Personality may only re-order near-equal suggestions, and only with evidence."""
    return questioning.ordering_bias(db, user)


@router.get("/questioning/weights")
def weights(
    date: Optional[str] = None, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    """The bounded weight nudges that came from this week's answers."""
    anchor = common.parse_date_if_string(date) if date else today_local()
    return questioning.planner_weight_report(db, user, day=anchor)
