"""Node tree routes (spec 14)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.books import BookTreeOut, NodeChildrenOut
from app.services import books as book_service

router = APIRouter(tags=["nodes"])


@router.get("/books/{book_id}/nodes", response_model=BookTreeOut)
def get_book_nodes(book_id: int, db: Session = Depends(get_db)) -> BookTreeOut:
    return book_service.get_book_tree(db, book_id=book_id)


@router.get("/nodes/{node_id}/children", response_model=NodeChildrenOut)
def get_node_children(node_id: int, db: Session = Depends(get_db)) -> NodeChildrenOut:
    return book_service.get_node_children(db, node_id=node_id)
