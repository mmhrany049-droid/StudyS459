"""Minimal user service (single-user MVP)."""

from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import User
from app.schemas.users import UserOut, UserPatch


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


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, username=user.username, display_name=user.display_name,
        grade=user.grade, track=user.track, timezone=user.timezone,
    )


def get_me(db: Session, *, user_id: int) -> UserOut:
    return _user_out(get_or_create_single_user(db, user_id))


def update_me(db: Session, *, user_id: int, payload: UserPatch) -> UserOut:
    user = get_or_create_single_user(db, user_id)
    if payload.timezone is not None:
        try:
            ZoneInfo(payload.timezone)
        except Exception:
            raise AppError(
                "invalid_timezone",
                f"منطقه زمانی «{payload.timezone}» معتبر نیست.",
                status_code=422,
            )
        user.timezone = payload.timezone
    if payload.display_name is not None:
        user.display_name = payload.display_name
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _user_out(user)
