"""System router: health, bootstrapping, parameter registry, dashboard, rewards."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import config
from ...core.errors import DomainError
from ...core.timeutil import today_local, week_label_fa
from ...db import models
from ...db.base import get_db
from ...db.seed import seed_all
from ...services import analytics, common, curriculum, rewards
from ..deps import current_user

router = APIRouter(tags=["system"])


class BootstrapPayload(BaseModel):
    display_name: str = "دانش‌آموز"
    username: str = "me"
    seed_content: bool = True


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": config.AppSettings().app_name, "model_version": config.MODEL_VERSION}


@router.post("/bootstrap")
def bootstrap(payload: BootstrapPayload | None = None, db: Session = Depends(get_db)) -> dict:
    """Create the user (single-user product), load book content and seed defaults."""
    payload = payload or BootstrapPayload()
    user = db.scalars(select(models.User).where(models.User.username == payload.username)).first()
    created = False
    if user is None:
        user = common.create_user(db, payload.display_name, payload.username)
        created = True
    seed_result = seed_all(db, user) if payload.seed_content else {}
    db.commit()
    return {
        "user": {"id": user.id, "display_name": user.display_name, "username": user.username},
        "created": created,
        "seed": seed_result,
        "week_label": week_label_fa(today_local()),
        "note": "هیچ دادهی ساختگی ساخته نمی‌شود؛ فقط محتوای کتاب‌های موجود در مخزن و پیش‌فرض‌های مستندشده بارگذاری می‌شود.",
    }


@router.get("/me")
def me(user: models.User = Depends(current_user)) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "grade": user.grade,
        "track": user.track,
        "timezone": user.timezone,
        "quiet_mode": user.quiet_mode,
        "auto_time_adjust": user.auto_time_adjust,
        "onboarding_completed": user.onboarding_completed,
        "coins": user.total_coins,
        "streak": user.current_streak,
        "today": common.jdate(today_local()),
        "today_long": common.jdate_long(today_local()),
        "week_label": week_label_fa(today_local()),
    }


@router.patch("/me")
def update_me(changes: dict, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    for key in ["display_name", "grade", "track", "timezone", "quiet_mode", "auto_time_adjust", "season_mode"]:
        if key in changes:
            setattr(user, key, changes[key])
    db.commit()
    return {"updated": True, "user": {"display_name": user.display_name, "quiet_mode": user.quiet_mode}}


@router.get("/config/params")
def params_registry() -> dict:
    """Every number used by the engines, with provenance and evidence level."""
    return {
        "model_version": config.MODEL_VERSION,
        "params": config.snapshot(),
        "policy": {
            "no_magic_numbers": "هیچ عددی در کد هارد‌کد نیست؛ همه از این رجیستری می‌آیند.",
            "v3_priority_weights": "وزن‌های اولویت نسخه ۳ مقادیر پیش‌فرض قابل‌تنظیم و برچسب HEURISTIC دارند تا با شواهد اشتباه گرفته نشوند.",
            "v2_numbers": "اعداد نسخه ۲ (سکه، مرور، ظرفیت) دست‌نخورده حفظ شده‌اند.",
        },
    }


@router.get("/dashboard")
def dashboard(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    payload = analytics.dashboard(db, user)
    db.commit()
    return payload


@router.get("/rewards/summary")
def rewards_summary(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return rewards.summary(db, user)


@router.post("/rewards/wake-up")
def record_wake_up(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = rewards.record_wake_up(db, user)
    db.commit()
    return result


@router.post("/seed")
def reseed(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = seed_all(db, user)
    db.commit()
    return result


@router.get("/styles/catalog")
def style_catalog(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Everything the UI needs for its pickers (kept out of the presentation layer)."""
    from ...domain import enums

    return {
        "subjects": [
            {"id": subject.id, "name": subject.name, "slug": subject.slug, "color": subject.color}
            for subject in db.scalars(select(models.Subject).order_by(models.Subject.order_index))
        ],
        "books": curriculum.list_books(db, user),
        "node_types": enums.NODE_TYPE_LABELS_FA,
        "interventions": [
            {"value": key.value, "label": enums.INTERVENTION_LABELS_FA[key]} for key in enums.InterventionType
        ],
        "task_types": [{"value": key.value, "label": enums.TASK_TYPE_LABELS_FA[key]} for key in enums.TaskType],
        "task_statuses": [status.value for status in enums.TaskStatus],
        "activity_categories": [
            {"value": key.value, "label": enums.ACTIVITY_LABELS_FA[key]} for key in enums.ActivityCategory
        ],
        "error_categories": [
            {"value": key.value, "label": enums.ERROR_CATEGORY_LABELS_FA[key]} for key in enums.ErrorCategory
        ],
        "answer_states": [state.value for state in enums.AnswerState],
    }


def register_error_handlers(app) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error_handler(_request, exc: DomainError):  # pragma: no cover - wired in main
        raise HTTPException(status_code=exc.http_status, detail=exc.as_dict())
