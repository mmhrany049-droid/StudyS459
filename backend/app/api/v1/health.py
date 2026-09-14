"""Health endpoints (foundation only)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.config import Settings, get_settings
from app.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": __version__,
        "env": settings.ENV,
        "timezone": settings.TIMEZONE,
    }


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
