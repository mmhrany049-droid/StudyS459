"""مسیرهای اصلی: auth، کتاب‌ها، کلاس‌ها/برنامهٔ هفتگی، تنظیمات."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_user
from app.db import get_db
from app.jalali import (jalali_str, season_mode, today_tehran, week_start_of, weekday_name_fa)
from app.models import (Book, BookNode, NodeParityState, Schedule, SchoolDayOverride, Subject,
                        Task, User, UserBookActivation)
from app.domain import behavior as behavior_mod

router = APIRouter()


class ActivationBody(BaseModel):
    active: bool


class ScheduleBody(BaseModel):
    title: str
    subject_id: int | None = None
    day_of_week: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    recurring: bool = True


class OverrideBody(BaseModel):
    date: str
    is_school_day: bool
    reason: str = ""


class SettingsBody(BaseModel):
    auto_time_adjust: bool | None = None
    season_override: str | None = None
    display_name: str | None = None


# ------------------------------- Auth ---------------------------------------

@router.get("/auth/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_user)):
    return {
        "id": user.id, "username": user.username, "display_name": user.display_name,
        "grade": user.grade, "track": user.track, "timezone": user.timezone,
        "coins": user.coins, "total_points": user.total_points,
        "current_streak": user.current_streak, "longest_streak": user.longest_streak,
        "settings": user.settings_json or {},
        "today": {
            "iso": today_tehran().isoformat(),
            "jalali": jalali_str(today_tehran()),
            "weekday": weekday_name_fa(today_tehran()),
            "week_start": week_start_of(today_tehran()).isoformat(),
            "season_mode": season_mode(today_tehran(),
                                       (user.settings_json or {}).get("season_override")),
        },
    }


@router.post("/auth/login")
def login(db: Session = Depends(get_db), user: User = Depends(get_user)):
    return {"ok": True, "user_id": user.id}


@router.post("/auth/logout")
def logout():
    return {"ok": True}


@router.patch("/settings")
def patch_settings(body: SettingsBody, db: Session = Depends(get_db),
                   user: User = Depends(get_user)):
    s = dict(user.settings_json or {})
    if body.auto_time_adjust is not None:
        s["auto_time_adjust"] = body.auto_time_adjust
    if body.season_override is not None:
        if body.season_override not in ("school_term", "summer", "none", ""):
            raise HTTPException(400, "season_override نامعتبر است.")
        s["season_override"] = None if body.season_override in ("none", "") else body.season_override
    if body.display_name is not None:
        user.display_name = body.display_name
    user.settings_json = s
    behavior_mod.log_event(db, user.id, "settings_changed", body.model_dump(exclude_none=True))
    db.commit()
    return {"ok": True, "settings": s}


# ------------------------------- Books --------------------------------------

@router.get("/books")
def list_books(db: Session = Depends(get_db), user: User = Depends(get_user)):
    out = []
    for b in db.scalars(select(Book).order_by(Book.id)):
        act = db.execute(
            select(UserBookActivation).where(
                UserBookActivation.user_id == user.id,
                UserBookActivation.book_id == b.id)).scalar_one_or_none()
        subject = db.get(Subject, b.subject_id)
        out.append({
            "id": b.id, "stable_key": b.stable_key, "title": b.title,
            "publisher": b.publisher, "subject": subject.name if subject else None,
            "active": bool(act and act.active),
        })
    return out


@router.get("/books/{book_id}/nodes")
def book_nodes(book_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    nodes = list(db.scalars(
        select(BookNode).where(BookNode.book_id == book_id).order_by(BookNode.order_index)))
    by_parent: dict[int, list] = {}
    for n in nodes:
        by_parent.setdefault(n.parent_id or 0, []).append(n)

    def node_dict(n: BookNode) -> dict:
        parity = db.execute(
            select(NodeParityState).where(NodeParityState.user_id == user.id,
                                          NodeParityState.node_id == n.id)
        ).scalar_one_or_none()
        return {
            "id": n.id, "title": n.title, "node_type": n.node_type,
            "code": n.code, "order": n.order_index,
            "last_parity": parity.last_parity if parity else None,
            "children": [node_dict(c) for c in by_parent.get(n.id, [])],
        }

    return [node_dict(r) for r in by_parent.get(0, [])]


@router.post("/users/me/books/{book_id}/activate")
def activate_book(book_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    act = db.execute(
        select(UserBookActivation).where(UserBookActivation.user_id == user.id,
                                         UserBookActivation.book_id == book_id)
    ).scalar_one_or_none()
    if act is None:
        db.add(UserBookActivation(user_id=user.id, book_id=book_id, active=True))
    else:
        act.active = True
    db.commit()
    return {"ok": True, "active": True}


@router.delete("/users/me/books/{book_id}/activate")
def deactivate_book(book_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    act = db.execute(
        select(UserBookActivation).where(UserBookActivation.user_id == user.id,
                                         UserBookActivation.book_id == book_id)
    ).scalar_one_or_none()
    if act is not None:
        act.active = False
        db.commit()
    return {"ok": True, "active": False}


@router.get("/nodes/{node_id}/parity-state")
def parity_state(node_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    from app.domain.selection import suggest_parity
    st = db.execute(
        select(NodeParityState).where(NodeParityState.user_id == user.id,
                                      NodeParityState.node_id == node_id)
    ).scalar_one_or_none()
    return {
        "node_id": node_id,
        "last_parity": st.last_parity if st else None,
        "suggested_next": suggest_parity(db, user.id, node_id),
    }


@router.get("/nodes/{node_id}/test-sets")
def node_test_sets(node_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    from app.domain.selection import descendant_test_sets
    node = db.get(BookNode, node_id)
    if node is None:
        raise HTTPException(404, "مبحث پیدا نشد.")
    sets = descendant_test_sets(db, node)
    from sqlalchemy import func
    from app.models import Question
    out = []
    for ts in sets:
        n = db.scalar(select(func.count(Question.id)).where(Question.test_set_id == ts.id)) or 0
        out.append({
            "id": ts.id, "title": ts.title, "test_type": ts.test_type,
            "question_count": n,
            "node_id": ts.node_id,
        })
    return out


@router.get("/test-sets/{test_set_id}/questions")
def test_set_questions(test_set_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    """فهرست سوالات یک مجموعه (بدون ساخت session) — برای فرم Import."""
    from app.models import Question
    rows = db.scalars(
        select(Question).where(Question.test_set_id == test_set_id)
        .order_by(Question.sequence_no)).all()
    return [{"id": q.id, "sequence_no": q.sequence_no, "answer_key": q.answer_key,
             "difficulty": q.difficulty_level} for q in rows]


# ------------------------------- Schedules ----------------------------------

@router.get("/schedules")
def list_schedules(db: Session = Depends(get_db), user: User = Depends(get_user)):
    out = []
    for s in db.scalars(select(Schedule).where(Schedule.user_id == user.id).order_by(Schedule.id)):
        subj = db.get(Subject, s.subject_id) if s.subject_id else None
        out.append({
            "id": s.id, "title": s.title, "schedule_type": s.schedule_type,
            "subject": subj.name if subj else None, "subject_id": s.subject_id,
            "day_of_week": s.day_of_week, "start_time": s.start_time,
            "end_time": s.end_time, "recurring": s.recurring, "source": s.source,
        })
    return out


@router.post("/schedules")
def create_schedule(body: ScheduleBody, db: Session = Depends(get_db),
                    user: User = Depends(get_user)):
    if body.day_of_week is not None and not (0 <= body.day_of_week <= 6):
        raise HTTPException(400, "day_of_week باید ۰ تا ۶ باشد (شنبه=0 ... جمعه=6).")
    s = Schedule(user_id=user.id, title=body.title, subject_id=body.subject_id,
                 day_of_week=body.day_of_week, start_time=body.start_time,
                 end_time=body.end_time, recurring=body.recurring, source="user")
    db.add(s)
    behavior_mod.log_event(db, user.id, "schedule_created", {"title": body.title})
    db.commit()
    return {"id": s.id, "ok": True}


@router.patch("/schedules/{schedule_id}")
def update_schedule(schedule_id: int, body: ScheduleBody, db: Session = Depends(get_db),
                    user: User = Depends(get_user)):
    s = db.get(Schedule, schedule_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(404, "کلاس پیدا نشد.")
    s.title = body.title
    s.subject_id = body.subject_id
    s.day_of_week = body.day_of_week
    s.start_time = body.start_time
    s.end_time = body.end_time
    db.commit()
    return {"ok": True}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db),
                    user: User = Depends(get_user)):
    s = db.get(Schedule, schedule_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(404, "کلاس پیدا نشد.")
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/schedules/seed-defaults")
def seed_default_classes(db: Session = Depends(get_db), user: User = Depends(get_user)):
    """سه کلاس تقویتی پیش‌فرض V2: حسابان، شیمی، فیزیک (source=default_seed_v2)."""
    subjects = {s.name: s for s in db.scalars(select(Subject))}
    created = []
    for name in ("حسابان", "شیمی", "فیزیک"):
        existing = db.execute(
            select(Schedule).where(Schedule.user_id == user.id,
                                   Schedule.source == "default_seed_v2",
                                   Schedule.subject_id == subjects[name].id)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        s = Schedule(user_id=user.id, schedule_type="external_class",
                     title=f"کلاس تقویتی {name}", subject_id=subjects[name].id,
                     day_of_week=None, start_time=None, end_time=None,
                     recurring=True, source="default_seed_v2")
        db.add(s)
        created.append(name)
    db.commit()
    return {"ok": True, "created": created,
            "note": "روز و ساعت هر کلاس را در صفحهٔ کلاس‌ها تکمیل کن."}


@router.get("/school-day-overrides")
def list_overrides(db: Session = Depends(get_db), user: User = Depends(get_user)):
    return [{
        "id": o.id, "date": o.date.isoformat(), "is_school_day": o.is_school_day,
        "reason": o.reason,
    } for o in db.scalars(
        select(SchoolDayOverride).where(SchoolDayOverride.user_id == user.id)
        .order_by(SchoolDayOverride.date))]


@router.post("/school-day-overrides")
def create_override(body: OverrideBody, db: Session = Depends(get_db),
                    user: User = Depends(get_user)):
    d = dt.date.fromisoformat(body.date)
    existing = db.execute(
        select(SchoolDayOverride).where(SchoolDayOverride.user_id == user.id,
                                        SchoolDayOverride.date == d)
    ).scalar_one_or_none()
    if existing is not None:
        existing.is_school_day = body.is_school_day
        existing.reason = body.reason
    else:
        db.add(SchoolDayOverride(user_id=user.id, date=d,
                                 is_school_day=body.is_school_day, reason=body.reason))
    behavior_mod.log_event(db, user.id, "school_day_override", {
        "date": body.date, "is_school_day": body.is_school_day})
    db.commit()
    return {"ok": True}


@router.get("/subjects")
def list_subjects(db: Session = Depends(get_db), user: User = Depends(get_user)):
    return [{"id": s.id, "name": s.name} for s in db.scalars(select(Subject))]
