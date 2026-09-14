"""
Repository layer for books - separation of data access
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.book import Book, UserBookActivation
from ..models.book_node import BookNode

class BookRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_stable_id(self, stable_id: str) -> Optional[Book]:
        return self.db.query(Book).filter(Book.stable_id == stable_id).first()
    
    def get_by_id(self, book_id: int) -> Optional[Book]:
        return self.db.query(Book).filter(Book.id == book_id).first()
    
    def list(self, subject_id: Optional[int] = None, active_only: bool = False) -> List[Book]:
        q = self.db.query(Book)
        if subject_id:
            q = q.filter(Book.subject_id == subject_id)
        if active_only:
            q = q.filter(Book.is_active == True)
        return q.all()
    
    def get_nodes(self, book_id: int) -> List[BookNode]:
        return self.db.query(BookNode).filter(BookNode.book_id == book_id).order_by(BookNode.level, BookNode.order_index).all()
    
    def get_user_activations(self, user_id: int) -> List[UserBookActivation]:
        return self.db.query(UserBookActivation).filter(UserBookActivation.user_id == user_id).all()
