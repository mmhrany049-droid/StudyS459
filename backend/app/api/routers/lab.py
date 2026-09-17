"""Lab router: personal experiments, research registry, recalculation, audit."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db.base import get_db
from ...db import models
from ...services import common, experiments as experiment_service, recalculation
from ..deps import current_user

router = APIRouter(tags=["lab"])


class ExperimentPayload(BaseModel):
    title: Optional[str] = None
    hypothesis: Optional[str] = None
    template_key: Optional[str] = None
    intervention: dict = {}
    control: dict = {}
    metric: Optional[str] = None
    metric_direction: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None
    start_now: bool = True


class ObservationPayload(BaseModel):
    phase: str
    metrics: dict = {}
    note: Optional[str] = None


class ResearchPayload(BaseModel):
    source: Optional[str] = None
    title: str
    authors: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None
    finding: Optional[str] = None
    limitations: Optional[str] = None
    product_implication: Optional[str] = None
    evidence_level: str = "HEURISTIC"
    review_date: Optional[str] = None
    linked_params: list[str] = []


class RecalcPayload(BaseModel):
    scope: str = "user"
    scope_id: Optional[int] = None
    trigger: str = "manual"
    incremental: bool = True


@router.get("/experiments")
def list_experiments(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {
        "experiments": experiment_service.list_experiments(db, user),
        "templates": experiment_service.templates(),
        "policy": "یک جلسه موفق اثبات نیست؛ نتیجه با تعداد مشاهده، اندازه اثر و اطمینان گزارش می‌شود.",
    }


@router.post("/experiments")
def create_experiment(
    payload: ExperimentPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    experiment = experiment_service.create_experiment(db, user, payload.model_dump())
    db.commit()
    return {
        "id": experiment.id,
        "title": experiment.title,
        "hypothesis": experiment.hypothesis,
        "metric": experiment.metric,
        "status": experiment.status,
    }


@router.post("/experiments/{experiment_id}/observations")
def log_observation(
    experiment_id: int, payload: ObservationPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    observation = experiment_service.log_observation(
        db, user, experiment_id, phase=payload.phase, metrics=payload.metrics, note=payload.note
    )
    db.commit()
    return {"id": observation.id, "phase": observation.phase, "metrics": observation.metrics}


@router.get("/experiments/{experiment_id}/analysis")
def analyse(experiment_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = experiment_service.analyse(db, user, experiment_id)
    db.commit()
    return result


@router.get("/research")
def research(db: Session = Depends(get_db)) -> dict:
    return {
        "entries": experiment_service.research_registry(db),
        "policy": {
            "levels": ["EMPIRICAL", "RESEARCH_SUPPORTED", "HEURISTIC", "USER_SPECIFIC", "EXPERIMENTAL"],
            "rule": "مقاله مستقیم به قاعده هارد‌کد تبدیل نمی‌شود: پژوهش → ارزیابی → فرضیه → پیاده‌سازی قابل تنظیم → سنجش شخصی.",
        },
    }


@router.post("/research")
def add_research(payload: ResearchPayload, db: Session = Depends(get_db)) -> dict:
    entry = experiment_service.add_research(db, payload.model_dump())
    db.commit()
    return {"id": entry.id, "title": entry.title, "evidence_level": entry.evidence_level}


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------


@router.post("/recalculations")
def recalculate(payload: RecalcPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = recalculation.recalculate(
        db, user, scope=payload.scope, scope_id=payload.scope_id, trigger=payload.trigger, incremental=payload.incremental
    )
    db.commit()
    return result


@router.get("/recalculations/jobs")
def jobs(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {"jobs": recalculation.jobs(db, user)}


@router.get("/integrity/report")
def integrity(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return recalculation.integrity_report(db, user)


@router.get("/audit")
def audit(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
) -> dict:
    return {"events": recalculation.audit_trail(db, entity_type, entity_id, limit)}


@router.get("/model-versions")
def model_versions(db: Session = Depends(get_db)) -> dict:
    rows = db.query(models.ModelVersion).order_by(models.ModelVersion.id.desc()).limit(50)
    return {
        "versions": [
            {"model_name": row.model_name, "version": row.version, "params": row.params, "notes": row.notes}
            for row in rows
        ],
        "note": "هر مقدار مشتق‌شده نسخه مدل خود را حمل می‌کند تا بازسازی قابل ردیابی باشد.",
    }


# ---------------------------------------------------------------------------
# Optional, non-blocking integrations
# ---------------------------------------------------------------------------


@router.get("/integrations/telegram")
def telegram_status(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.query(models.TelegramConnection).filter(models.TelegramConnection.user_id == user.id).first()
    return {
        "enabled": bool(row and row.enabled),
        "chat_id": row.chat_id if row else None,
        "optional": True,
        "message": "تلگرام افزونه اختیاری است؛ خاموش بودن آن هیچ‌کدام از قابلیت‌های اصلی را محدود نمی‌کند.",
    }


@router.post("/integrations/telegram/connect")
def telegram_connect(chat_id: str, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.query(models.TelegramConnection).filter(models.TelegramConnection.user_id == user.id).first()
    if row is None:
        row = models.TelegramConnection(user_id=user.id, chat_id=chat_id, enabled=True)
        db.add(row)
    else:
        row.chat_id = chat_id
        row.enabled = True
    db.commit()
    return {"enabled": True, "chat_id": chat_id, "note": "بدون توکن، هیچ پیامی ارسال نمی‌شود؛ شکست آن اپ را نمی‌شکند."}
