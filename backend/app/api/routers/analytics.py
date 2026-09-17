"""Analytics, progress, behaviour, onboarding, check-ins and explainability."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.timeutil import today_local
from ...db import models
from ...db.base import get_db
from ...services import (
    analytics,
    behaviour,
    duration as duration_service,
    learning,
    recommendation,
)
from ..deps import current_user, parse_day

router = APIRouter(tags=["analytics"])


class CheckinPayload(BaseModel):
    phase: str = "start"
    answers: dict = {}
    skipped: bool = False


class ReflectionPayload(BaseModel):
    answers: dict = {}
    skipped: bool = False


class OnboardingAnswerPayload(BaseModel):
    code: str
    answer: dict = {}
    skip: bool = False


class StatePayload(BaseModel):
    answers: dict = {}


class DistractionPayload(BaseModel):
    pattern_code: str
    hours: int = 72


@router.get("/progress/overview")
def overview(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    payload = analytics.overall_stats(db, user)
    payload["weaknesses"] = analytics.weakness_report(db, user, limit=8)
    payload["trends"] = analytics.trends(db, user, days=14)
    return payload


@router.get("/progress/books/{book_id}")
def book_progress(book_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return analytics.book_progress(db, user, book_id)


@router.get("/analytics/trends")
def trends(days: int = Query(30, le=180), user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return analytics.trends(db, user, days=days)


@router.get("/analytics/weaknesses")
def weaknesses(limit: int = Query(15, le=100), user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {
        "items": analytics.weakness_report(db, user, limit=limit),
        "note": "ضعف از جمع غلط‌ها ساخته نمی‌شود؛ ابعاد پوشش، دقت، نگه‌داشت و عدم‌قطعیت جدا گزارش می‌شوند.",
    }


@router.post("/analytics/rebuild")
def rebuild(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = learning.rebuild_all(db, user)
    db.commit()
    return {**result, "note": "همه مقادیر مشتق‌شده از داده خام بازساخته شدند."}


# ---------------------------------------------------------------------------
# Explainability
# ---------------------------------------------------------------------------


@router.get("/recommendations")
def list_recommendations(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    refresh: bool = False,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = recommendation.list_recommendations(db, user, status=status, limit=limit)
    if refresh or not items:
        recommendation.generate_recommendations(db, user)
        db.commit()
        items = recommendation.list_recommendations(db, user, status=status, limit=limit)
    return {
        "recommendations": items,
        "note": "پیشنهاد ≠ کار؛ تا وقتی خودت تبدیلش نکنی هیچ چیزی به برنامه اضافه نمی‌شود.",
    }


@router.get("/recommendations/{recommendation_id}/explain")
def explain(
    recommendation_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    row = db.get(models.Recommendation, recommendation_id)
    if not row or row.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("پیشنهاد پیدا نشد.")
    return recommendation.explanation(db, recommendation_id)


@router.post("/recommendations/{recommendation_id}/feedback")
def feedback(
    recommendation_id: int,
    action: str = Query(..., description="accept | increase | decrease | reject | adjust"),
    payload: dict = Body({}),
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = recommendation.record_feedback(db, user, recommendation_id, action, payload=payload)
    db.commit()
    return result


@router.post("/recommendations/{recommendation_id}/to-task")
def to_task(
    recommendation_id: int, payload: dict = Body({}), user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    from ...services import tasks as tasks_service

    row = db.get(models.Recommendation, recommendation_id)
    if not row or row.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("پیشنهاد پیدا نشد.")
    day = parse_day(payload.get("planned_date")) or today_local()
    task = recommendation.convert_to_task(db, user, row, day=day, minutes=payload.get("minutes"))
    db.commit()
    return {"task": tasks_service.task_payload(task), "recommendation_status": row.status}


@router.get("/priorities")
def priorities(
    limit: int = Query(20, le=100),
    day: Optional[str] = None,
    explain: bool = False,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    from ...services import priority as priority_service

    items = priority_service.compute_priorities(db, user, day=parse_day(day), limit=limit)
    return {
        "items": [
            {**item, "explanation": priority_service.explain_priority(item) if explain else None} for item in items
        ],
        "weights": {
            key: {"value": value.value, "provenance": value.provenance, "confidence": value.confidence}
            for key, value in __import__("app.config", fromlist=["config"]).PARAMS.items()
            if key.startswith("priority.weight")
        },
    }


# ---------------------------------------------------------------------------
# Time estimation
# ---------------------------------------------------------------------------


@router.get("/duration/estimate")
def estimate(
    task_type: str = "test_session",
    question_count: Optional[int] = None,
    topic_id: Optional[int] = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    return duration_service.estimate_for_task(
        db, user, task_type=task_type, question_count=question_count, topic_id=topic_id
    )


@router.get("/duration/insights")
def duration_insights(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return duration_service.insights(db, user)


# ---------------------------------------------------------------------------
# Behaviour, state, onboarding
# ---------------------------------------------------------------------------


@router.get("/user-model")
def user_model(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return behaviour.profile_payload(db, user)


@router.get("/onboarding/questions/next")
def next_question(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    question = behaviour.next_onboarding_question(db, user)
    db.commit()
    return {
        "question": question,
        "done": question is None,
        "summary": behaviour.profile_payload(db, user)["personality"] if question is None else None,
    }


@router.post("/onboarding/answers")
def answer_question(
    payload: OnboardingAnswerPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = behaviour.answer_onboarding(db, user, payload.code, payload.answer, skip=payload.skip)
    db.commit()
    return result


@router.post("/onboarding/complete")
def complete_onboarding(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = behaviour.complete_onboarding(db, user)
    db.commit()
    return result


@router.get("/onboarding/summary")
def onboarding_summary(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return behaviour.profile_payload(db, user)


@router.get("/state/current")
def current_state(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return behaviour.current_state(db, user)


@router.post("/state/check-in")
def check_in(payload: StatePayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    behaviour.check_in(db, user, payload.answers, phase="start")
    db.commit()
    return behaviour.current_state(db, user)


@router.get("/behavior/summary")
def behaviour_summary(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    payload = behaviour.behaviour_summary(db, user)
    db.commit()
    return payload


@router.get("/behavior/features")
def behaviour_features(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return behaviour.observed_features(db, user)


@router.post("/behavior/patterns/dismiss")
def dismiss_pattern(
    payload: DistractionPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    result = behaviour.dismiss_pattern(db, user, payload.pattern_code, payload.hours)
    db.commit()
    return result


@router.get("/checkins/questions")
def checkin_questions(phase: str = "start") -> dict:
    return {"phase": phase, "questions": behaviour.daily_questionnaire(phase)}


@router.post("/checkins")
def save_checkin(payload: CheckinPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = behaviour.save_daily_checkin(db, user, payload.phase, payload.answers, skipped=payload.skipped)
    db.commit()
    return result


@router.get("/reflections/questions")
def reflection_questions() -> dict:
    return {"questions": behaviour.WEEKLY_REFLECTION_QUESTIONS}


@router.post("/reflections")
def save_reflection(payload: ReflectionPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    result = behaviour.save_weekly_reflection(db, user, payload.answers, skipped=payload.skipped)
    db.commit()
    return result


@router.get("/notifications")
def notifications(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    rows = list(
        db.query(models.Notification)
        .filter(models.Notification.user_id == user.id)
        .order_by(models.Notification.id.desc())
        .limit(30)
    )
    return {
        "notifications": [
            {
                "id": row.id,
                "kind": row.kind,
                "title": row.title,
                "body": row.body,
                "quiet": row.quiet,
                "read": bool(row.read_at),
            }
            for row in rows
        ],
        "quiet_mode": user.quiet_mode,
    }
