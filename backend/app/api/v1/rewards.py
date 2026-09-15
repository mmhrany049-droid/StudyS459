"""Reward routes (spec 14). Routes only."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db import get_db
from app.schemas.rewards import BadgeOut, RewardEventOut, RewardsSummaryOut
from app.services import rewards as service

router = APIRouter(tags=["rewards"])


@router.get("/rewards/summary", response_model=RewardsSummaryOut)
def get_summary(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> RewardsSummaryOut:
    return service.summary(db, user_id=user_id)


@router.get("/rewards/events", response_model=list[RewardEventOut])
def list_events(
    limit: int = Query(default=50),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[RewardEventOut]:
    return service.list_events(db, user_id=user_id, limit=limit)


@router.get("/rewards/badges", response_model=list[BadgeOut])
def list_badges(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[BadgeOut]:
    return service.list_badges(db, user_id=user_id)
