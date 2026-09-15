"""User profile routes (Phase 8 settings). Routes only."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db import get_db
from app.schemas.users import UserOut, UserPatch
from app.services import users as service

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserOut)
def get_me(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> UserOut:
    return service.get_me(db, user_id=user_id)


@router.patch("/users/me", response_model=UserOut)
def update_me(
    payload: UserPatch,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> UserOut:
    return service.update_me(db, user_id=user_id, payload=payload)
