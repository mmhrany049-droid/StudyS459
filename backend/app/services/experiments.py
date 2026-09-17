"""Personal experiments + research registry.

V3: support hypotheses such as "starting a difficult session with 10 easy
questions improves completion". One successful session is **not** proof, so the
analysis reports effect size, sample size and an explicit confidence, and can
conclude "inconclusive".
"""

from __future__ import annotations

import datetime as _dt
import statistics
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.errors import NotFoundError, ValidationError
from ..core.timeutil import clamp, now_utc, today_local
from ..db import models
from . import common

MODEL_VERSION = config.MODEL_VERSION

TEMPLATES = [
    {
        "key": "warmup_easy_before_hard",
        "title": "شروع کار دشوار با ۱۰ تست آسان",
        "hypothesis": "شروع یک جلسه سخت با ۱۰ تست آسان، نرخ تکمیل کارهای دشوار را بالا می‌برد.",
        "metric": "task_completion_rate",
        "metric_direction": "higher",
        "intervention": {"warmup_questions": 10, "difficulty": "easy"},
        "control": {"warmup_questions": 0},
        "linked_params": ["behavior.warmup_question_count"],
    },
    {
        "key": "review_before_new",
        "title": "مرور کوتاه قبل از تمرین جدید",
        "hypothesis": "۵ دقیقه یادآوری فعال قبل از تمرین جدید، دقت همان جلسه را بالا می‌برد.",
        "metric": "session_accuracy",
        "metric_direction": "higher",
        "intervention": {"pre_session_recall_minutes": 5},
        "control": {"pre_session_recall_minutes": 0},
        "linked_params": [],
    },
    {
        "key": "smaller_bundles",
        "title": "وعده‌های کوتاه‌تر",
        "hypothesis": "شکستن وعده‌های ۹۰ دقیقه‌ای به دو وعده ۴۵ دقیقه‌ای، تعداد کار انجام‌شده در روز را زیاد می‌کند.",
        "metric": "daily_completed_tasks",
        "metric_direction": "higher",
        "intervention": {"bundle_minutes": 45},
        "control": {"bundle_minutes": 90},
        "linked_params": ["session.bundle_max_minutes"],
    },
]


def create_experiment(db: Session, user: models.User, payload: dict) -> models.Experiment:
    template_key = payload.get("template_key")
    template = next((item for item in TEMPLATES if item["key"] == template_key), None)
    hypothesis = payload.get("hypothesis") or (template["hypothesis"] if template else None)
    if not hypothesis:
        raise ValidationError("فرضیه آزمایش لازم است.")
    start = common.parse_date_if_string(payload.get("start_date")) or today_local()
    experiment = models.Experiment(
        user_id=user.id,
        title=payload.get("title") or (template["title"] if template else "آزمایش شخصی"),
        hypothesis=hypothesis,
        intervention=payload.get("intervention") or (template["intervention"] if template else {}),
        control=payload.get("control") or (template["control"] if template else {}),
        metric=payload.get("metric") or (template["metric"] if template else "task_completion_rate"),
        metric_direction=payload.get("metric_direction") or (template["metric_direction"] if template else "higher"),
        start_date=start,
        end_date=common.parse_date_if_string(payload.get("end_date")),
        status="running" if payload.get("start_now") else "planned",
        notes=payload.get("notes"),
    )
    db.add(experiment)
    db.flush()
    common.audit(
        db, "experiment_created", user_id=user.id, entity_type="experiment", entity_id=experiment.id,
        after={"hypothesis": hypothesis, "metric": experiment.metric},
    )
    return experiment


def log_observation(
    db: Session, user: models.User, experiment_id: int, *, phase: str, metrics: dict, note: Optional[str] = None
) -> models.ExperimentObservation:
    experiment = db.get(models.Experiment, experiment_id)
    if not experiment or experiment.user_id != user.id:
        raise NotFoundError("آزمایش پیدا نشد.")
    if phase not in {"intervention", "control"}:
        raise ValidationError("فاز باید intervention یا control باشد.")
    observation = models.ExperimentObservation(
        experiment_id=experiment_id,
        user_id=user.id,
        phase=phase,
        observed_at=now_utc(),
        day=today_local(),
        metrics=metrics,
        note=note,
    )
    db.add(observation)
    db.flush()
    return observation


def analyse(db: Session, user: models.User, experiment_id: int) -> dict:
    experiment = db.get(models.Experiment, experiment_id)
    if not experiment or experiment.user_id != user.id:
        raise NotFoundError("آزمایش پیدا نشد.")
    observations = list(
        db.scalars(select(models.ExperimentObservation).where(models.ExperimentObservation.experiment_id == experiment_id))
    )
    intervention = [obs.metrics.get(experiment.metric) for obs in observations if obs.phase == "intervention"]
    control = [obs.metrics.get(experiment.metric) for obs in observations if obs.phase == "control"]
    intervention = [value for value in intervention if value is not None]
    control = [value for value in control if value is not None]
    min_n = config.value("experiment.min_observations_per_arm")
    result = {
        "experiment_id": experiment_id,
        "metric": experiment.metric,
        "n_intervention": len(intervention),
        "n_control": len(control),
        "min_required": min_n,
    }
    if len(intervention) < min_n or len(control) < min_n:
        result.update(
            {
                "conclusion": "inconclusive",
                "confidence": 0.0,
                "interpretation": f"برای نتیجه‌گیری حداقل {min_n} مشاهده در هر بازو لازم است "
                                  f"({len(intervention)} در برابر {len(control)}).",
            }
        )
        return result
    mean_intervention = statistics.fmean(intervention)
    mean_control = statistics.fmean(control)
    pooled_stdev = statistics.pstdev(intervention + control) or 1e-9
    effect = (mean_intervention - mean_control) / pooled_stdev
    if experiment.metric_direction == "lower":
        effect = -effect
    threshold = config.value("experiment.min_effect_for_signal")
    if abs(effect) < threshold:
        conclusion = "inconclusive"
    elif effect > 0:
        conclusion = "supports"
    else:
        conclusion = "contradicts"
    confidence = common.confidence_from_evidence(min(len(intervention), len(control)))
    interpretation = (
        f"میانگین «{experiment.metric}» در فاز مداخله {round(mean_intervention, 3)} و در فاز کنترل "
        f"{round(mean_control, 3)} بود (اندازه اثر {round(effect, 3)}). "
        f"با {len(intervention)} و {len(control)} مشاهده، اطمینان {common.confidence_band(confidence)} است."
    )
    row = models.ExperimentResult(
        experiment_id=experiment_id,
        metric=experiment.metric,
        intervention_value=round(mean_intervention, 4),
        control_value=round(mean_control, 4),
        n_intervention=len(intervention),
        n_control=len(control),
        effect_size=round(effect, 4),
        conclusion=conclusion,
        confidence=confidence,
        interpretation=interpretation,
        model_version=MODEL_VERSION,
    )
    db.add(row)
    experiment.result = {
        "conclusion": conclusion,
        "effect_size": round(effect, 4),
        "intervention_value": round(mean_intervention, 4),
        "control_value": round(mean_control, 4),
        "n_intervention": len(intervention),
        "n_control": len(control),
        "analysed_at": common.jdatetime(now_utc()),
    }
    experiment.confidence = confidence
    if experiment.status == "running":
        experiment.status = "completed"
    db.flush()
    result.update(
        {
            "intervention_value": round(mean_intervention, 3),
            "control_value": round(mean_control, 3),
            "effect_size": round(effect, 3),
            "conclusion": conclusion,
            "confidence": confidence,
            "confidence_band": common.confidence_band(confidence),
            "interpretation": interpretation,
            "disclaimer": "یک جلسه موفق اثبات نیست؛ نتیجه فقط با تعداد مشاهده کافی و اندازه اثر گزارش می‌شود.",
        }
    )
    return result


def list_experiments(db: Session, user: models.User) -> list[dict]:
    rows = list(db.scalars(select(models.Experiment).where(models.Experiment.user_id == user.id).order_by(models.Experiment.id.desc())))
    payload = []
    for row in rows:
        counts = db.execute(
            select(models.ExperimentObservation.phase, func.count(models.ExperimentObservation.id))
            .where(models.ExperimentObservation.experiment_id == row.id)
            .group_by(models.ExperimentObservation.phase)
        ).all()
        payload.append(
            {
                "id": row.id,
                "title": row.title,
                "hypothesis": row.hypothesis,
                "metric": row.metric,
                "metric_direction": row.metric_direction,
                "status": row.status,
                "start_date": common.jdate(row.start_date),
                "end_date": common.jdate(row.end_date),
                "intervention": row.intervention,
                "control": row.control,
                "result": row.result or {},
                "confidence": row.confidence,
                "observations": {phase: count for phase, count in counts},
            }
        )
    return payload


def templates() -> list[dict]:
    return TEMPLATES


def research_registry(db: Session) -> list[dict]:
    rows = list(db.scalars(select(models.ResearchEntry).order_by(models.ResearchEntry.id)))
    return [
        {
            "id": row.id,
            "source": row.source,
            "title": row.title,
            "authors": row.authors,
            "year": row.year,
            "url": row.doi_url,
            "finding": row.finding,
            "limitations": row.limitations,
            "product_implication": row.product_implication,
            "evidence_level": row.evidence_level,
            "linked_params": row.linked_params or [],
            "review_date": common.jdate(row.review_date),
        }
        for row in rows
    ]


def add_research(db: Session, payload: dict) -> models.ResearchEntry:
    if payload.get("evidence_level") not in config.value("evidence.levels"):
        raise ValidationError(
            "سطح شواهد باید یکی از EMPIRICAL, RESEARCH_SUPPORTED, HEURISTIC, USER_SPECIFIC, EXPERIMENTAL باشد."
        )
    entry = models.ResearchEntry(
        source=payload.get("source"),
        title=payload.get("title") or "بدون عنوان",
        authors=payload.get("authors"),
        year=common.to_int(payload.get("year")),
        doi_url=payload.get("url") or payload.get("doi_url"),
        finding=payload.get("finding"),
        limitations=payload.get("limitations"),
        product_implication=payload.get("product_implication"),
        evidence_level=payload.get("evidence_level"),
        review_date=common.parse_date_if_string(payload.get("review_date")),
        linked_params=payload.get("linked_params") or [],
    )
    db.add(entry)
    db.flush()
    return entry
