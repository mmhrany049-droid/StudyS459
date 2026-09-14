"""Minimal user service (single-user MVP)."""

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User


def get_or_create_single_user(db: Session, user_id: int | None = None) -> User:
    """Return the single user, creating the default row if missing.

    Keeps fresh databases (dev/test) usable without manual seeding.
    """
    uid = user_id if user_id is not None else get_settings().SINGLE_USER_ID
    user = db.get(User, uid)
    if user is not None:
        return user
    user = User(
        id=uid,
        username="student",
        display_name="دانش‌آموز",
        grade=11,
        track="mathematics",
        timezone="Asia/Tehran",
    )
    db.add(user)
    db.flush()
    return user
