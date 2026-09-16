"""مسیرهای تحلیل و اهداف — V1."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_user
from app.db import get_db
from app.domain import analytics
from app.domain.planning import build_candidates, week_progress
from app.jalali import today_tehran, week_start_of
from app.models import (BookNode, Subject, User, WeeklyGoal, WeeklyGoalItem)

router = APIRouter()


class GoalItemBody(BaseModel):
    goal_type: str  # count | topic
    target_value: int
    subject_id: int | None = None
    book_id: int | None = None
    node_id: int | None = None


class WeekGoalsBody(BaseModel):
    items: list[GoalItemBody]


@router.get("/progress/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(get_user)):
    return analytics.overview(db, user)


@router.get("/progress/books/{book_id}")
def book_progress(book_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    out = analytics.book_progress(db, user, book_id)
    if not out:
        raise HTTPException(404, "کتاب پیدا نشد.")
    return out


@router.get("/analytics/weaknesses")
def weaknesses(limit: int = 10, db: Session = Depends(get_db), user: User = Depends(get_user)):
    return analytics.weaknesses(db, user, limit)


@router.get("/analytics/trends")
def trends(db: Session = Depends(get_db), user: User = Depends(get_user)):
    return analytics.overview(db, user)["trend"]


# ------------------------------- Goals ---------------------------------------

@router.get("/goals/weeks/{week}")
def get_goals(week: str, db: Session = Depends(get_db), user: User = Depends(get_user)):
    week_start = dt.date.fromisoformat(week)
    goal = db.execute(
        select(WeeklyGoal).where(WeeklyGoal.user_id == user.id,
                                 WeeklyGoal.week_start == week_start)
    ).scalar_one_or_none()
    items = []
    if goal:
        for gi in db.scalars(select(WeeklyGoalItem).where(WeeklyGoalItem.goal_id == goal.id)):
            node = db.get(BookNode, gi.node_id) if gi.node_id else None
            subj = db.get(Subject, gi.subject_id) if gi.subject_id else None
            items.append({
                "id": gi.id, "goal_type": gi.goal_type, "target_value": gi.target_value,
                "subject": subj.name if subj else None, "node": node.title if node else None,
            })
    return {"week": week, "goal_id": goal.id if goal else None, "items": items,
            "progress": week_progress(db, user.id, week_start)}


@router.post("/goals/weeks/{week}")
def set_goals(week: str, body: WeekGoalsBody, db: Session = Depends(get_db),
              user: User = Depends(get_user)):
    week_start = dt.date.fromisoformat(week)
    if week_start.weekday() != 5:
        raise HTTPException(400, "هفته باید از شنبه شروع شود (تاریخ شنبه).")
    goal = db.execute(
        select(WeeklyGoal).where(WeeklyGoal.user_id == user.id,
                                 WeeklyGoal.week_start == week_start)
    ).scalar_one_or_none()
    if goal is None:
        goal = WeeklyGoal(user_id=user.id, week_start=week_start,
                          week_end=week_start + dt.timedelta(days=6), active=True)
        db.add(goal)
        db.flush()
    # بازنویسی آیتمها (اهداف کاربر است؛ نه history)
    for old in db.scalars(select(WeeklyGoalItem).where(WeeklyGoalItem.goal_id == goal.id)):
        db.delete(old)
    for it in body.items:
        if it.goal_type not in ("count", "topic"):
            raise HTTPException(400, "goal_type باید count یا topic باشد.")
        db.add(WeeklyGoalItem(goal_id=goal.id, goal_type=it.goal_type,
                              target_value=it.target_value, subject_id=it.subject_id,
                              book_id=it.book_id, node_id=it.node_id))
    db.commit()
    return get_goals(week, db, user)


@router.get("/goals/candidates")
def goal_candidates(date: str | None = None, db: Session = Depends(get_db),
                    user: User = Depends(get_user)):
    """کاندیدهای پیشنهادی برای یک روز (با دلیل)."""
    d = dt.date.fromisoformat(date) if date else today_tehran()
    week_start = week_start_of(d)
    cands = build_candidates(db, user, d, week_start)[:12]
    return {"date": d.isoformat(), "week_start": week_start.isoformat(), "candidates": cands}
