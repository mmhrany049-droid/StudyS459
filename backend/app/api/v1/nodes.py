"""Node tree + parity routes (spec 14)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db import get_db
from app.schemas.books import BookTreeOut, NodeChildrenOut
from app.schemas.tests import ParityStateOut
from app.services import books as book_service
from app.services import test_engine as engine

router = APIRouter(tags=["nodes"])


@router.get("/books/{book_id}/nodes", response_model=BookTreeOut)
def get_book_nodes(book_id: int, db: Session = Depends(get_db)) -> BookTreeOut:
    return book_service.get_book_tree(db, book_id=book_id)


@router.get("/nodes/{node_id}/children", response_model=NodeChildrenOut)
def get_node_children(node_id: int, db: Session = Depends(get_db)) -> NodeChildrenOut:
    return book_service.get_node_children(db, node_id=node_id)


@router.get("/nodes/{node_id}/parity-state", response_model=ParityStateOut)
def get_parity_state(
    node_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ParityStateOut:
    return engine.get_parity_state(db, user_id=user_id, node_id=node_id)
