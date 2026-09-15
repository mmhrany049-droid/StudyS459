"""Reward events + badges persistence (spec 04 reward section)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Badge, RewardEvent, UserBadge


def add_event(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    points: int,
    description: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: int | None = None,
) -> RewardEvent:
    event = RewardEvent(
        user_id=user_id, event_type=event_type, points=points,
        description=description, related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    db.add(event)
    db.flush()
    return event


def total_points(db: Session, user_id: int) -> int:
    return int(
        db.execute(
            select(func.coalesce(func.sum(RewardEvent.points), 0)).where(
                RewardEvent.user_id == user_id)
        ).scalar() or 0
    )


def list_events(db: Session, user_id: int, *, limit: int) -> list[RewardEvent]:
    return list(
        db.execute(
            select(RewardEvent).where(RewardEvent.user_id == user_id)
            .order_by(RewardEvent.id.desc())
            .limit(limit)
        ).scalars().all()
    )


def has_event(
    db: Session, user_id: int, event_type: str, related_type: str, related_id: int
) -> bool:
    return (
        db.execute(
            select(RewardEvent.id).where(
                RewardEvent.user_id == user_id,
                RewardEvent.event_type == event_type,
                RewardEvent.related_entity_type == related_type,
                RewardEvent.related_entity_id == related_id,
            )
        ).first()
        is not None
    )


def get_badge_by_code(db: Session, code: str) -> Badge | None:
    return db.execute(select(Badge).where(Badge.code == code)).scalar_one_or_none()


def list_badges(db: Session) -> list[Badge]:
    return list(db.execute(select(Badge).order_by(Badge.id)).scalars().all())


def ensure_badge(
    db: Session, *, code: str, title: str, description: str,
    condition_type: str, condition_value: str,
) -> Badge:
    badge = get_badge_by_code(db, code)
    if badge is None:
        badge = Badge(
            code=code, title=title, description=description,
            condition_type=condition_type, condition_value=condition_value,
        )
        db.add(badge)
        db.flush()
    return badge


def has_badge(db: Session, user_id: int, badge_id: int) -> bool:
    return (
        db.execute(
            select(UserBadge.badge_id).where(
                UserBadge.user_id == user_id, UserBadge.badge_id == badge_id)
        ).first()
        is not None
    )


def grant_badge(db: Session, user_id: int, badge_id: int) -> bool:
    """Returns True if newly granted (idempotent)."""
    if has_badge(db, user_id, badge_id):
        return False
    db.add(UserBadge(user_id=user_id, badge_id=badge_id))
    db.flush()
    return True


def user_badges(db: Session, user_id: int) -> list[UserBadge]:
    return list(
        db.execute(
            select(UserBadge).where(UserBadge.user_id == user_id)
            .order_by(UserBadge.earned_at.desc())
        ).scalars().all()
    )
