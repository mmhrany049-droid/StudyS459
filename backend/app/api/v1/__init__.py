"""v1 routers aggregated WITHOUT a URL prefix (contract paths served as-is)."""

from fastapi import APIRouter

from app.api.v1.books import router as books_router
from app.api.v1.health import router as health_router
from app.api.v1.nodes import router as nodes_router

v1_router = APIRouter()
v1_router.include_router(health_router)
v1_router.include_router(books_router)
v1_router.include_router(nodes_router)

__all__ = ["v1_router"]
