from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...database import get_db
from ...services import analytics_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/progress", tags=["Progress"])

@router.get("/")
def progress(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return analytics_service.get_progress_detailed(db, current_user.id)

@router.get("/overview")
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return analytics_service.get_overall_analytics(db, current_user.id)
