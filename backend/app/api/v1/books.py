"""Book Engine routes (spec 14). Routes only — logic lives in services."""

from fastapi import APIRouter, Body, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db import get_db
from app.schemas.books import ActivationOut, BookDetailOut, BookOut, ImportOut
from app.services import books as book_service
from app.services.book_importer import import_book_config

router = APIRouter(tags=["books"])


@router.get("/books", response_model=list[BookOut])
def list_books(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[BookOut]:
    return book_service.list_books(db, user_id=user_id)


@router.get("/books/{book_id}", response_model=BookDetailOut)
def get_book(
    book_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> BookDetailOut:
    return book_service.get_book_detail(db, user_id=user_id, book_id=book_id)


@router.post("/books/import")
def import_book(
    response: Response,
    config: dict = Body(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ImportOut:
    result = import_book_config(db, user_id=user_id, config=config)
    response.status_code = 201 if result.status == "imported" else 200
    return result


@router.post("/users/me/books/{book_id}/activate", response_model=ActivationOut)
def activate_book(
    book_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ActivationOut:
    return book_service.set_book_active(db, user_id=user_id, book_id=book_id, active=True)


@router.delete("/users/me/books/{book_id}/activate", response_model=ActivationOut)
def deactivate_book(
    book_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ActivationOut:
    return book_service.set_book_active(db, user_id=user_id, book_id=book_id, active=False)
