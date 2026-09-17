"""Goals router: three-month goals, milestones, objectives, adaptation."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db import models
from ...db.base import get_db
from ...services import common, goals as goal_service, recommendation
from ..deps import current_user

router = APIRouter(tags=["goals"])


class GoalPayload(BaseModel):
    title: str
    goal_type: str = "three_month"
    subject_id: Optional[int] = None
    book_id: Optional[int] = None
    topic_id: Optional[int] = None
    # a goal can cover several books / topics at once (V3 doc 06)
    subject_ids: list[int] = []
    book_ids: list[int] = []
    topic_ids: list[int] = []
    start_date: Optional[str] = None
    target_date: Optional[str] = None
    baseline: dict = {}
    target: dict = {}
    objectives: list[dict] = []
    notes: Optional[str] = None


@router.get("/goals")
def list_goals(user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    goals = goal_service.list_goals(db, user)
    db.commit()
    return {
        "goals": goals,
        "note": "پیشرفت روی چند بُعد (پوشش/دقت/آمادگی) گزارش می‌شود، نه یک عدد خوش‌بینانه.",
    }


@router.post("/goals")
def create_goal(payload: GoalPayload, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    goal = goal_service.create_goal(db, user, payload.model_dump())
    db.commit()
    return goal_service.goal_payload(db, user, goal)


@router.get("/goals/{goal_id}")
def get_goal(goal_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    goal = db.get(models.Goal, goal_id)
    if not goal or goal.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("هدف پیدا نشد.")
    goal_service.refresh_progress(db, user, goal)
    db.commit()
    return goal_service.goal_payload(db, user, goal)


@router.patch("/goals/{goal_id}")
def update_goal(
    goal_id: int, changes: dict = Body(...), user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    goal = goal_service.update_goal(db, user, goal_id, changes)
    db.commit()
    return goal_service.goal_payload(db, user, goal)


@router.post("/goals/{goal_id}/refresh")
def refresh(goal_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    goal = db.get(models.Goal, goal_id)
    if not goal or goal.user_id != user.id:
        from ...core.errors import NotFoundError

        raise NotFoundError("هدف پیدا نشد.")
    progress = goal_service.refresh_progress(db, user, goal)
    adaptation = goal_service.adapt_milestones(db, user, goal)
    db.commit()
    return {"goal_id": goal_id, "progress": progress, "adaptation": adaptation}


@router.get("/goals/{goal_id}/candidate-tasks")
def candidate_tasks(goal_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {"candidates": goal_service.candidate_tasks(db, user, goal_id)}


@router.post("/goals/{goal_id}/plan-week")
def plan_week(goal_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Turn the goal's most urgent gaps into recommendations for this week."""
    from ...core.timeutil import today_local

    candidates = goal_service.candidate_tasks(db, user, goal_id, limit=4)
    created = []
    for candidate in candidates:
        row = recommendation.build_recommendation(
            db, user, topic_id=candidate["topic_id"], scope="goal", day=today_local(), quiet=True
        )
        created.append({"recommendation_id": row.id, "topic_id": candidate["topic_id"], "title": row.title})
    db.commit()
    return {"created": created, "note": "پیشنهادها فقط پیشنهادند؛ تبدیل به کار با تأیید تو انجام می‌شود."}
