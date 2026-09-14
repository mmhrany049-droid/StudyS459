from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...schemas.book import BookOut, BookNodeOut, TestSetOut, QuestionOut, SubjectOut, UserBookActivationOut, BookImportRequest
from ...services import book_service
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/books", tags=["Books"])

@router.get("/subjects", response_model=List[SubjectOut])
def list_subjects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return book_service.get_subjects(db)

@router.get("/", response_model=List[BookOut])
def list_books(
    subject_id: Optional[int] = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return book_service.get_books(db, subject_id=subject_id, active_only=active_only)

@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    book = db.query(book_service.Book).filter(book_service.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.get("/{book_id}/nodes", response_model=List[BookNodeOut])
def list_book_nodes(book_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    nodes = book_service.get_book_nodes(db, book_id)
    # Build hierarchical response? For now flat, but we can build tree
    # Convert to tree structure for frontend
    tree = book_service.get_book_node_tree(db, book_id)
    # Flatten tree to nested structure - we need to convert our tree dict to BookNodeOut nested
    def convert_tree_node(item):
        node = item["node"]
        children = [convert_tree_node(child) for child in item["children"]]
        return BookNodeOut(
            id=node.id,
            book_id=node.book_id,
            stable_id=node.stable_id,
            parent_id=node.parent_id,
            node_type=node.node_type,
            title=node.title,
            title_fa=node.title_fa,
            order_index=node.order_index,
            level=node.level,
            children=children
        )
    return [convert_tree_node(r) for r in tree]

@router.get("/{book_id}/test-sets", response_model=List[TestSetOut])
def list_test_sets(book_id: int, node_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    test_sets = book_service.get_test_sets(db, book_id, node_id=node_id)
    result = []
    for ts in test_sets:
        q_count = db.query(book_service.Question).filter(book_service.Question.test_set_id == ts.id).count()
        result.append(TestSetOut(
            id=ts.id,
            book_id=ts.book_id,
            stable_id=ts.stable_id,
            node_id=ts.node_id,
            title=ts.title,
            title_fa=ts.title_fa,
            test_type=ts.test_type,
            difficulty_level=ts.difficulty_level,
            is_comprehensive=ts.is_comprehensive,
            question_count=q_count
        ))
    return result

@router.get("/{book_id}/questions", response_model=List[QuestionOut])
def list_questions(
    book_id: int,
    test_set_id: Optional[int] = None,
    node_id: Optional[int] = None,
    difficulty_level: Optional[int] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    questions = book_service.get_questions(db, book_id=book_id, test_set_id=test_set_id, node_id=node_id, difficulty_level=difficulty_level, limit=limit, offset=offset)
    result = []
    for q in questions:
        topic_ids = [m.book_node_id for m in q.topic_maps]
        result.append(QuestionOut(
            id=q.id,
            book_id=q.book_id,
            test_set_id=q.test_set_id,
            stable_id=q.stable_id,
            question_text=q.question_text,
            question_text_fa=q.question_text_fa,
            image_url=q.image_url,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            correct_option=q.correct_option,
            difficulty_level=q.difficulty_level,
            is_concours=q.is_concours,
            concours_year=q.concours_year,
            topic_node_ids=topic_ids
        ))
    return result

@router.post("/import", response_model=BookOut)
def import_book(import_req: BookImportRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    book = book_service.import_book_data(db, import_req.model_dump())
    return book

@router.get("/activations/me", response_model=List[UserBookActivationOut])
def my_activations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return book_service.get_user_book_activations(db, current_user.id)

@router.post("/{book_id}/activate", response_model=UserBookActivationOut)
def activate_book(book_id: int, is_active: bool = True, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return book_service.activate_book(db, current_user.id, book_id, is_active=is_active)

# Need to import Book for query
from ...models.book import Book
