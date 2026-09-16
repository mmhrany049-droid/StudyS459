"""وابستگی‌های API — کاربر جاری (تک‌کاربره، auth ساده)."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


def get_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).order_by(User.id).first()
    if user is None:
        from app.seed import seed_all
        seed_all(db)
        user = db.query(User).order_by(User.id).first()
    return user
