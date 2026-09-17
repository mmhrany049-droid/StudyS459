"""Shared service helpers: ownership, audit trail, Jalali serialization."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import jalali
from ..core.errors import ConflictError, NotFoundError, ValidationError  # noqa: F401
from ..core.timeutil import now_utc, today_local
from ..db import models

# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


def resolve_user(db: Session, user_id: Optional[int] = None) -> models.User:
    """Single-user product (V1 scope) but every query is ownership scoped."""
    if user_id:
        user = db.get(models.User, user_id)
        if not user:
            raise NotFoundError("کاربر پیدا نشد.")
        return user
    user = db.scalars(select(models.User).order_by(models.User.id)).first()
    if not user:
        user = models.User(username="me", display_name="دانش‌آموز")
        db.add(user)
        db.flush()
    return user


def create_user(db: Session, display_name: str, username: str = "me", **kwargs) -> models.User:
    user = models.User(username=username, display_name=display_name, **kwargs)
    db.add(user)
    db.flush()
    db.add(models.UserProfile(user_id=user.id, personality={}, preferences={}, self_reported={}))
    db.add(models.OnboardingState(user_id=user.id, asked_codes=[], skipped_codes=[], uncertainty={}))
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Audit trail (never lose raw history)
# ---------------------------------------------------------------------------


def audit(
    db: Session,
    event_type: str,
    *,
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    actor: str = "user",
    reason: Optional[str] = None,
    before: Any = None,
    after: Any = None,
) -> models.AuditEvent:
    event = models.AuditEvent(
        user_id=user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        reason=reason,
        before=before or {},
        after=after or {},
    )
    db.add(event)
    return event


def observe(
    db: Session,
    user_id: int,
    kind: str,
    *,
    payload: Optional[dict] = None,
    source: str = "observed",
    day: Optional[_dt.date] = None,
    task_id: Optional[int] = None,
    session_id: Optional[int] = None,
    observed_at: Optional[_dt.datetime] = None,
) -> models.BehaviorObservation:
    """Every meaningful user action becomes raw, append-only behavioural data."""
    observation = models.BehaviorObservation(
        user_id=user_id,
        kind=kind,
        observed_at=observed_at or now_utc(),
        day=day or today_local(),
        source=source,
        payload=payload or {},
        task_id=task_id,
        session_id=session_id,
    )
    db.add(observation)
    return observation


# ---------------------------------------------------------------------------
# Serialization helpers (Jalali is presentation, storage stays Gregorian)
# ---------------------------------------------------------------------------


def jdate(value: Optional[_dt.date]) -> Optional[str]:
    return jalali.format_jalali(value)


def jdate_long(value: Optional[_dt.date]) -> Optional[str]:
    return jalali.format_jalali_long(value)


def jdatetime(value: Optional[_dt.datetime]) -> Optional[str]:
    return jalali.format_jalali(value)


def weekday_fa(value: Optional[_dt.date]) -> Optional[str]:
    return jalali.weekday_name_fa(value) if value else None


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def require(condition: bool, message: str, *, details: Optional[dict] = None) -> None:
    if not condition:
        raise ValidationError(message, details=details)


def paginate(items: list, limit: Optional[int] = None, offset: int = 0) -> list:
    if limit is None:
        limit = len(items)
    return items[offset: offset + limit]


def chunks(sequence: Iterable, size: int) -> Iterable[list]:
    batch: list = []
    for item in sequence:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def normalize_digits(text: str) -> str:
    """Persian/Arabic digits -> latin (users type «۱۴۰۴/۰۶/۲۴» all the time)."""
    return jalali.normalize_digits(text)


def to_persian_digits(text: str) -> str:
    return jalali.to_persian_digits(text)


def parse_date_if_string(value: Any) -> Optional[_dt.date]:
    """Accept ISO (2026-09-15) or Jalali (1405/06/24) strings."""
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    text = str(value).strip()
    if "/" in text and text[:4].isdigit() and int(text[:4]) > 1500:
        return jalali.parse_jalali(text)
    if "-" in text and len(text) >= 8 and text[4] == "-":
        return _dt.date.fromisoformat(text[:10])
    return jalali.parse_jalali(text)


def parse_datetime_if_string(value: Any) -> Optional[_dt.datetime]:
    """Accept an ISO datetime, a date, or a bare 'HH:MM' (=> today at that time)."""
    if value in (None, ""):
        return None
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date):
        return _dt.datetime.combine(value, _dt.time(0, 0))
    text = str(value).strip()
    if len(text) <= 5 and ":" in text and "-" not in text and "/" not in text:
        hour, minute = text.split(":", 1)
        return _dt.datetime.combine(today_local(), _dt.time(int(hour), int(minute)))
    if "T" in text or (":" in text and "-" in text):
        from ..core.timeutil import parse_iso

        return parse_iso(text)
    day = parse_date_if_string(text)
    return _dt.datetime.combine(day, _dt.time(0, 0)) if day else None


def confidence_band(confidence: Optional[float]) -> str:
    from .. import config

    if confidence is None:
        return "unknown"
    if confidence < config.value("confidence.low"):
        return "low"
    if confidence < config.value("confidence.medium"):
        return "medium"
    return "high"


def confidence_from_evidence(evidence_count: int) -> float:
    """3 observations must not weigh as much as 30 (V2.1 confidence policy)."""
    from .. import config

    table = config.value("confidence.max_by_evidence")
    confidence = 0.0
    for threshold, value in table:
        if evidence_count >= threshold:
            confidence = float(value)
    return confidence


def money_round(value: float) -> int:
    return int(round(value + 1e-9))
