from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...database import get_db
from ...services.student_state_service import get_student_state
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/student-state", tags=["Student State"])

@router.get("/")
def student_state(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_student_state(db, current_user.id)
