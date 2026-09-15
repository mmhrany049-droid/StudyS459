"""v1 routers aggregated WITHOUT a URL prefix (contract paths served as-is)."""

from fastapi import APIRouter

from app.api.v1.academic import exams_router, router as academic_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.books import router as books_router
from app.api.v1.goals import router as goals_router
from app.api.v1.health import router as health_router
from app.api.v1.nodes import router as nodes_router
from app.api.v1.planner import router as planner_router
from app.api.v1.rewards import router as rewards_router
from app.api.v1.test_sessions import router as tests_router

v1_router = APIRouter()
v1_router.include_router(health_router)
v1_router.include_router(academic_router)
v1_router.include_router(exams_router)
v1_router.include_router(books_router)
v1_router.include_router(goals_router)
v1_router.include_router(nodes_router)
v1_router.include_router(planner_router)
v1_router.include_router(rewards_router)
v1_router.include_router(tests_router)
v1_router.include_router(analytics_router)

__all__ = ["v1_router"]
