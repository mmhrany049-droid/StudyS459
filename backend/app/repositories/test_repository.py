from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.test_session import TestSession, TestSessionQuestion
from ..models.attempt import QuestionAttempt

class TestRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_session(self, session_id: int, user_id: int) -> Optional[TestSession]:
        return self.db.query(TestSession).filter(TestSession.id == session_id, TestSession.user_id == user_id).first()
    
    def list_sessions(self, user_id: int, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[TestSession]:
        q = self.db.query(TestSession).filter(TestSession.user_id == user_id)
        if status:
            q = q.filter(TestSession.status == status)
        return q.order_by(TestSession.started_at.desc()).offset(offset).limit(limit).all()
    
    def get_attempts(self, user_id: int, question_id: int) -> List[QuestionAttempt]:
        return self.db.query(QuestionAttempt).filter(QuestionAttempt.user_id == user_id, QuestionAttempt.question_id == question_id).order_by(QuestionAttempt.created_at.asc()).all()
