"""Time estimation engine.

V3 rules, implemented literally:

* during the first month we never ask the user to *predict* a duration; we ask
  what it actually took **after** completion, and fall back to a rough
  60–120 minute band when a range is needed;
* once there is enough evidence we personalise and return ranges such as
  "۶۵ تا ۸۲ دقیقه" **with a confidence**;
* we detect systematic drift instead of hiding everything behind one global
  average;
* interval coverage and prediction error are evaluated continuously.
"""

from __future__ import annotations

import datetime as _dt
import statistics
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import local_now, now_utc, safe_div, today_local
from ..db import models
from . import common

MODEL_VERSION = config.MODEL_VERSION


def record_observation(
    db: Session,
    user: models.User,
    *,
    actual_minutes: int,
    task_type: Optional[str] = None,
    question_count: Optional[int] = None,
    topic_id: Optional[int] = None,
    book_id: Optional[int] = None,
    session_id: Optional[int] = None,
    task_id: Optional[int] = None,
    difficulty: Optional[int] = None,
    predicted_low: Optional[int] = None,
    predicted_high: Optional[int] = None,
    source: str = "user",
) -> models.DurationObservation:
    """Raw observation. There is no UI anywhere that asks for a *prediction*."""
    if actual_minutes is None or actual_minutes <= 0:
        from ..core.errors import ValidationError

        raise ValidationError("مدت زمان واقعی باید بزرگ‌تر از صفر باشد.")
    within = None
    if predicted_low and predicted_high:
        within = predicted_low <= actual_minutes <= predicted_high
    hour = local_now().hour
    period = "morning" if 4 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 21 else "night"
    observation = models.DurationObservation(
        user_id=user.id,
        task_id=task_id,
        session_id=session_id,
        task_type=task_type,
        topic_id=topic_id,
        book_id=book_id,
        question_count=question_count,
        difficulty=difficulty,
        actual_minutes=int(actual_minutes),
        predicted_low=predicted_low,
        predicted_high=predicted_high,
        within_range=within,
        time_of_day=period,
        source=source,
        recorded_at=now_utc(),
    )
    db.add(observation)
    db.flush()
    common.observe(
        db, user.id, "duration_observed",
        payload={"minutes": actual_minutes, "task_type": task_type, "question_count": question_count},
        source="user", session_id=session_id, task_id=task_id,
    )
    return observation


def _observations(db: Session, user: models.User, **filters) -> list[models.DurationObservation]:
    stmt = select(models.DurationObservation).where(models.DurationObservation.user_id == user.id)
    if filters.get("task_type"):
        stmt = stmt.where(models.DurationObservation.task_type == filters["task_type"])
    if filters.get("topic_id"):
        stmt = stmt.where(models.DurationObservation.topic_id == filters["topic_id"])
    if filters.get("book_id"):
        stmt = stmt.where(models.DurationObservation.book_id == filters["book_id"])
    return list(db.scalars(stmt.order_by(models.DurationObservation.recorded_at)))


def _minutes_per_question(observations: list[models.DurationObservation]) -> list[float]:
    values = []
    for obs in observations:
        if obs.question_count and obs.question_count > 0 and obs.actual_minutes:
            values.append(obs.actual_minutes / obs.question_count)
    return values


def drift_report(db: Session, user: models.User, task_type: Optional[str] = None) -> dict:
    observations = _observations(db, user, task_type=task_type)
    window = config.value("duration.drift_window")
    if len(observations) < window * 2:
        return {
            "detected": False,
            "reason": "داده کافی برای تشخیص تغییر سیستماتیک نیست.",
            "observations": len(observations),
        }
    recent = [o.actual_minutes for o in observations[-window:]]
    previous = [o.actual_minutes for o in observations[-2 * window : -window]]
    recent_mean = statistics.fmean(recent)
    previous_mean = statistics.fmean(previous)
    change = safe_div(recent_mean - previous_mean, previous_mean or 0) or 0.0
    threshold = config.value("duration.drift_threshold")
    return {
        "detected": abs(change) >= threshold,
        "direction": "slower" if change > 0 else "faster",
        "change_ratio": round(change, 3),
        "recent_mean_minutes": round(recent_mean, 1),
        "previous_mean_minutes": round(previous_mean, 1),
        "threshold": threshold,
        "message": (
            f"میانگین جلسات اخیرت حدود {abs(round(change * 100))}٪ "
            f"{'کندتر' if change > 0 else 'سریع‌تر'} از قبل شده—برآوردها با همین روند به‌روز می‌شود."
            if abs(change) >= threshold
            else "تغییر سیستماتیک معناداری دیده نشد."
        ),
    }


def estimate_for_task(
    db: Session,
    user: models.User,
    *,
    task_type: str,
    question_count: Optional[int] = None,
    topic_id: Optional[int] = None,
    book_id: Optional[int] = None,
    intervention: Optional[str] = None,
) -> dict:
    """Return {low, high, point, confidence, method, evidence}."""
    if not question_count:
        return _session_bundle_estimate(db, user, task_type=task_type, intervention=intervention)

    per_question_limit_low = config.value("session.min_minutes_per_question")
    per_question_limit_high = config.value("session.max_minutes_per_question")

    topic_obs = _observations(db, user, topic_id=topic_id) if topic_id else []
    type_obs = _observations(db, user, task_type=task_type)
    all_obs = _observations(db, user)

    min_topic = config.value("duration.min_observations_for_topic_model")
    min_personal = config.value("duration.min_observations_for_personal_range")

    method = "first_month_fallback"
    based_on: dict = {}
    low = high = point = None
    confidence = 0.0

    if topic_id and len([o for o in topic_obs if o.question_count]) >= min_topic:
        rates = _minutes_per_question(topic_obs)
        method = "topic_model"
        based_on = {"observations": len(rates), "scope": "topic", "topic_id": topic_id}
    elif len([o for o in type_obs if o.question_count]) >= min_personal:
        rates = _minutes_per_question(type_obs)
        method = "type_model"
        based_on = {"observations": len(rates), "scope": "task_type", "task_type": task_type}
    elif len([o for o in all_obs if o.question_count]) >= min_personal:
        rates = _minutes_per_question(all_obs)
        method = "personal_model"
        based_on = {"observations": len(rates), "scope": "all"}
    else:
        rates = []

    if rates:
        rates = [max(per_question_limit_low, min(per_question_limit_high, rate)) for rate in rates]
        median_rate = statistics.median(rates)
        spread = statistics.pstdev(rates) if len(rates) > 1 else median_rate * 0.25
        low_factor = config.value("duration.tight_range_low_factor" if len(rates) >= min_personal else "duration.wide_range_low_factor")
        high_factor = config.value("duration.tight_range_high_factor" if len(rates) >= min_personal else "duration.wide_range_high_factor")
        point = median_rate * question_count
        low = max(question_count * per_question_limit_low, (median_rate - max(spread * 0.5, median_rate * 0.10)) * question_count)
        high = min(question_count * per_question_limit_high, (median_rate + max(spread * 0.75, median_rate * 0.18)) * question_count)
        low = max(1, int(round(low)))
        high = max(low + 1, int(round(high)))
        point = max(1, int(round(point)))
        confidence = min(
            common.confidence_from_evidence(len(rates)),
            0.55 + 0.35 * (1 - min(1.0, spread / (median_rate or 1))),
        )
    else:
        # First month: broad band, explicitly low confidence, no false precision
        low = max(question_count * per_question_limit_low, question_count * 1.8)
        high = min(question_count * per_question_limit_high, question_count * 4.2)
        low, high = int(round(low)), int(round(high))
        point = int(round((low + high) / 2))
        confidence = 0.2
        based_on = {
            "observations": len(all_obs),
            "reason": "کمتر از حد آستانه داده داریم؛ بازه پهن و با اطمینان پایین گزارش می‌شود.",
        }

    drift = drift_report(db, user, task_type)
    if drift.get("detected") and drift.get("direction") == "slower":
        low = int(round(low * 1.10))
        high = int(round(high * 1.15))
        based_on["drift"] = drift
    elif drift.get("detected"):
        low = int(round(low * 0.95))
        high = int(round(high * 0.95))
        based_on["drift"] = drift

    based_on["question_count"] = question_count
    based_on["intervention"] = intervention
    return {
        "low_minutes": low,
        "high_minutes": high,
        "point_minutes": point,
        "confidence": round(confidence, 3),
        "confidence_band": common.confidence_band(confidence),
        "method": method,
        "evidence_count": based_on.get("observations", 0),
        "based_on": based_on,
        "label": f"{low} تا {high} دقیقه",
        "model_version": MODEL_VERSION,
    }


def _session_bundle_estimate(db: Session, user: models.User, *, task_type: str, intervention: Optional[str]) -> dict:
    low = config.value("session.bundle_min_minutes")
    high = config.value("session.bundle_max_minutes")
    observations = _observations(db, user, task_type=task_type)
    if len(observations) >= config.value("duration.min_observations_for_personal_range"):
        mean_minutes = statistics.fmean([o.actual_minutes for o in observations])
        low = max(15, int(round(mean_minutes * 0.8)))
        high = int(round(mean_minutes * 1.25))
        confidence = common.confidence_from_evidence(len(observations))
        method = "personal_model"
    else:
        confidence = 0.2
        method = "first_month_fallback"
    return {
        "low_minutes": low,
        "high_minutes": high,
        "point_minutes": int(round((low + high) / 2)),
        "confidence": round(confidence, 3),
        "confidence_band": common.confidence_band(confidence),
        "method": method,
        "evidence_count": len(observations),
        "based_on": {
            "note": "هر وعده مطالعه به‌طور پیش‌فرض ۶۰ تا ۱۲۰ دقیقه در نظر گرفته می‌شود تا داده کافی برسد.",
            "intervention": intervention,
        },
        "label": f"{low} تا {high} دقیقه",
        "model_version": MODEL_VERSION,
    }


def store_prediction(
    db: Session,
    user: models.User,
    *,
    scope_type: str,
    scope_id: Optional[int],
    task_type: Optional[str],
    question_count: Optional[int],
    estimate: dict,
) -> models.DurationPrediction:
    row = models.DurationPrediction(
        user_id=user.id,
        scope_type=scope_type,
        scope_id=scope_id,
        task_type=task_type,
        question_count=question_count,
        low_minutes=estimate["low_minutes"],
        high_minutes=estimate["high_minutes"],
        point_minutes=estimate["point_minutes"],
        confidence=estimate["confidence"],
        evidence_count=estimate.get("evidence_count", 0),
        method=estimate["method"],
        based_on=estimate.get("based_on", {}),
        model_version=MODEL_VERSION,
    )
    db.add(row)
    db.flush()
    return row


def prediction_quality(db: Session, user: models.User) -> dict:
    observations = [
        o for o in _observations(db, user) if o.predicted_low and o.predicted_high and o.within_range is not None
    ]
    if not observations:
        return {
            "evaluated": 0,
            "interval_coverage": None,
            "mean_absolute_error": None,
            "message": "هنوز برآوردی برای ارزیابی ثبت نشده است.",
        }
    inside = sum(1 for o in observations if o.within_range)
    errors = [
        abs(o.actual_minutes - (o.predicted_low + o.predicted_high) / 2) for o in observations
    ]
    return {
        "evaluated": len(observations),
        "interval_coverage": round(inside / len(observations), 3),
        "mean_absolute_error": round(statistics.fmean(errors), 1),
        "mean_absolute_percentage_error": round(
            statistics.fmean([abs(o.actual_minutes - (o.predicted_low + o.predicted_high) / 2) / o.actual_minutes for o in observations]),
            3,
        ),
        "target_coverage_band": [0.6, 0.9],
        "message": "پوشش بازه باید در محدوده ۶۰ تا ۹۰ درصد باشد؛ خیلی پهن = بی‌دقت، خیلی باریک = بیش‌اطمینان.",
    }


def insights(db: Session, user: models.User) -> dict:
    observations = _observations(db, user)
    by_type: dict[str, list[int]] = {}
    for obs in observations:
        by_type.setdefault(obs.task_type or "other", []).append(obs.actual_minutes)
    return {
        "total_observations": len(observations),
        "drift": drift_report(db, user),
        "quality": prediction_quality(db, user),
        "by_type": [
            {
                "task_type": key,
                "count": len(values),
                "mean_minutes": round(statistics.fmean(values), 1),
                "median_minutes": statistics.median(values),
            }
            for key, values in sorted(by_type.items())
        ],
        "policy": {
            "ask_prediction_from_user": False,
            "note": "سیستم هیچ‌وقت از کاربر نمی‌خواهد مدت کار را پیش‌بینی کند؛ فقط بعد از انجام، مدت واقعی پرسیده می‌شود.",
        },
    }
