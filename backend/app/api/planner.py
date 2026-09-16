"""مسیرهای برنامه‌ریز و کنترل دستی — V1 + V2.1.

اصل غیرقابل مذاکره (23_MANUAL_EDIT_AND_CONTROL_V2_1):
- کاربر مالک برنامه است: ایجاد/ویرایش/حذف/جابه‌جایی/split/merge/تغییر تعداد/اولویت/زمان.
- تغییرات دستی با source=manual ثبت می‌شوند و Planner بدون اجازه overwrite نمی‌کند.
- مدل پیشنهاد A و کاربر B را انتخاب کرد → B اجرا می‌شود؛ override خطا نیست، evidence است.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_user
from app.db import get_db
from app.domain import behavior as behavior_mod
from app.domain import capacity as capacity_mod
from app.domain import planning as planning_mod
from app.domain import rewards as rewards_mod
from app.domain.interview import (apply_answer, complete, get_or_create, interview_view,
                                  planner_inputs)
from app.jalali import (jalali_str, today_tehran, week_days, week_start_of, weekday_name_fa)
from app.models import (DailyTaskPlacement, Task, User)

router = APIRouter()


class TaskBody(BaseModel):
    title: str
    task_type: str = "test"
    date: str
    priority: int = 5
    estimated_minutes: int | None = None
    book_id: int | None = None
    node_id: int | None = None
    question_count: int = 20
    parity: str | None = None
    timed: bool = False
    override_reason: str | None = None


class TaskPatchBody(BaseModel):
    title: str | None = None
    priority: int | None = None
    question_count: int | None = None
    estimated_minutes: int | None = None
    parity: str | None = None
    timed: bool | None = None
    status: str | None = None
    override_reason: str | None = None


class MoveBody(BaseModel):
    date: str
    position: int | None = None


class SplitBody(BaseModel):
    second_date: str | None = None
    ratio: float = 0.5


class MergeBody(BaseModel):
    other_task_id: int


class InterviewAnswerBody(BaseModel):
    question_id: str
    answer: object


def _task_dict(db: Session, t: Task, date=None) -> dict:
    placement = db.execute(
        select(DailyTaskPlacement).where(DailyTaskPlacement.task_id == t.id)
        .order_by(DailyTaskPlacement.id.desc())).scalars().first()
    d = date or (placement.date if placement else None)
    return {
        "id": t.id, "title": t.title, "task_type": t.task_type,
        "status": t.status, "priority": t.priority,
        "estimated_minutes": t.estimated_minutes,
        "date": d.isoformat() if d else None,
        "book_id": t.book_id, "node_id": t.node_id,
        "question_count": t.question_count, "parity": t.parity, "timed": t.timed,
        "source": t.source, "manual_override": t.manual_override,
        "override_reason": t.override_reason,
        "recommendation_reason": t.recommendation_reason,
        "evidence": t.evidence_json or {},
        "created_by": t.created_by, "updated_by": t.updated_by,
    }


# ------------------------------- Planner views -------------------------------

@router.get("/planner/day/{date}")
def day_plan(date: str, db: Session = Depends(get_db), user: User = Depends(get_user)):
    d = dt.date.fromisoformat(date)
    info = capacity_mod.day_info(db, user.id, d)
    tasks = db.execute(
        select(Task).join(DailyTaskPlacement, DailyTaskPlacement.task_id == Task.id)
        .where(DailyTaskPlacement.date == d, Task.user_id == user.id,
               Task.status != "cancelled")
        .order_by(Task.priority.desc(), Task.id)).scalars().all()

    est_total = sum(t.estimated_minutes or 60 for t in tasks)
    over_capacity = est_total > info["capacity_minutes"]
    low_priority = sorted(tasks, key=lambda t: (t.priority, -(
        t.estimated_minutes or 0)))[:3] if over_capacity else []

    week_start = week_start_of(d)
    state = None
    try:
        from app.domain.state import current_state
        state = current_state(db, user)
        state = state["state"]
    except Exception:
        pass
    rec = capacity_mod.recommended_task_count(db, user.id, info["day_type"],
                                              state.get("energy") if state else None)
    return {
        "date": d.isoformat(),
        "display": {"jalali": jalali_str(d), "weekday": weekday_name_fa(d)},
        "day_info": info,
        "tasks": [_task_dict(db, t, d) for t in tasks],
        "capacity_recommendation": rec,
        "over_capacity": over_capacity,
        "over_capacity_warning": (
            f"مجموع زمان کارهای امروز ({est_total} دقیقه) از ظرفیت روز "
            f"({info['capacity_minutes']} دقیقه) بیشتر است. هیچ کاری خودکار حذف نشده؛ "
            "کم‌اولویت‌ترین‌ها برای جابه‌جایی:" if over_capacity else None),
        "low_priority_suggestions": [
            {"id": t.id, "title": t.title, "priority": t.priority} for t in low_priority],
        "suggestions": planning_mod.build_candidates(db, user, d, week_start)[:6],
    }


@router.get("/planner/week/{week}")
def week_plan(week: str, db: Session = Depends(get_db), user: User = Depends(get_user)):
    week_start = dt.date.fromisoformat(week)
    if week_start.weekday() != 5:
        raise HTTPException(400, "هفته باید با شنبه شروع شود.")
    days = week_days(week_start)
    out_days = []
    for d in days:
        info = capacity_mod.day_info(db, user.id, d)
        tasks = db.execute(
            select(Task).join(DailyTaskPlacement, DailyTaskPlacement.task_id == Task.id)
            .where(DailyTaskPlacement.date == d, Task.user_id == user.id,
                   Task.status != "cancelled")
            .order_by(Task.priority.desc(), Task.id)).scalars().all()
        out_days.append({
            "date": d.isoformat(), "weekday": weekday_name_fa(d),
            "jalali": jalali_str(d), "day_type": info["day_type"],
            "capacity_minutes": info["capacity_minutes"],
            "classes": info["classes"],
            "tasks": [_task_dict(db, t, d) for t in tasks],
        })
    interview = planner_inputs(db, user, week_start)
    return {
        "week_start": week_start.isoformat(),
        "week_end": days[-1].isoformat(),
        "display": f"{jalali_str(days[0])} تا {jalali_str(days[-1])}",
        "days": out_days,
        "goal_progress": planning_mod.week_progress(db, user.id, week_start),
        "interview": {"available": interview.get("available", False),
                      "completed": interview.get("completed", False)},
        "is_current_week": week_start == week_start_of(today_tehran()),
    }


@router.get("/habits/summary")
def habits(db: Session = Depends(get_db), user: User = Depends(get_user)):
    return capacity_mod.habits_summary(db, user.id)


# ------------------------------- Planning engine -----------------------------

class GenerateBody(BaseModel):
    week_start: str
    rebuild: bool = False


@router.post("/planning/generate")
def generate(body: GenerateBody, db: Session = Depends(get_db), user: User = Depends(get_user)):
    week_start = dt.date.fromisoformat(body.week_start)
    if week_start.weekday() != 5:
        raise HTTPException(400, "هفته باید با شنبه شروع شود.")
    return planning_mod.generate_week_plan(db, user, week_start, rebuild=False)


@router.post("/planning/rebuild")
def rebuild(body: GenerateBody, db: Session = Depends(get_db), user: User = Depends(get_user)):
    """بازسازی برنامه — فقط با تأیید صریح کاربر؛ Taskهای دستی دست‌نخورده می‌مانند."""
    week_start = dt.date.fromisoformat(body.week_start)
    if week_start.weekday() != 5:
        raise HTTPException(400, "هفته باید با شنبه شروع شود.")
    return planning_mod.generate_week_plan(db, user, week_start, rebuild=True)


@router.post("/planning/evaluate")
def evaluate(week: str, db: Session = Depends(get_db), user: User = Depends(get_user)):
    """حلقهٔ تطبیق: ارزیابی یک هفته و به‌روزرسانی ظرفیت."""
    week_start = dt.date.fromisoformat(week)
    out = planning_mod.evaluate_past_week(db, user, week_start)
    db.commit()
    return out


# ------------------------------- Weekly interview ----------------------------

@router.post("/planning/weekly-interview/start")
def interview_start(week: str, db: Session = Depends(get_db), user: User = Depends(get_user)):
    week_start = dt.date.fromisoformat(week)
    get_or_create(db, user.id, week_start)
    db.commit()
    return interview_view(db, user, week_start)


@router.get("/planning/weekly-interview/{week}")
def interview_get(week: str, db: Session = Depends(get_db), user: User = Depends(get_user)):
    week_start = dt.date.fromisoformat(week)
    return interview_view(db, user, week_start)


@router.post("/planning/weekly-interview/{week}/answer")
def interview_answer(week: str, body: InterviewAnswerBody, db: Session = Depends(get_db),
                     user: User = Depends(get_user)):
    week_start = dt.date.fromisoformat(week)
    out = apply_answer(db, user, week_start, body.question_id, body.answer)
    db.commit()
    if not out.get("ok"):
        raise HTTPException(400, out.get("reason"))
    return interview_view(db, user, week_start)


@router.post("/planning/weekly-interview/{week}/complete")
def interview_complete(week: str, db: Session = Depends(get_db), user: User = Depends(get_user)):
    week_start = dt.date.fromisoformat(week)
    out = complete(db, user, week_start)
    behavior_mod.log_event(db, user.id, "interview_completed",
                           {"week_start": week_start.isoformat()})
    db.commit()
    return {"ok": True, "answers": out["answers"]}


# ------------------------------- Tasks / Manual control ----------------------

@router.post("/tasks")
def create_task(body: TaskBody, db: Session = Depends(get_db), user: User = Depends(get_user)):
    d = dt.date.fromisoformat(body.date)
    t = Task(
        user_id=user.id, task_type=body.task_type, title=body.title,
        source_type="manual", source="manual",
        priority=body.priority, estimated_minutes=body.estimated_minutes,
        due_at=d, status="planned",
        book_id=body.book_id, node_id=body.node_id,
        question_count=body.question_count, parity=body.parity, timed=body.timed,
        manual_override=True, override_reason=body.override_reason,
        created_by="user", updated_by="user",
    )
    db.add(t)
    db.flush()
    db.add(DailyTaskPlacement(task_id=t.id, date=d, position=0))
    behavior_mod.log_event(db, user.id, "task_created", {
        "task_id": t.id, "title": t.title, "manual": True})
    db.commit()
    return _task_dict(db, t)


@router.get("/tasks")
def list_tasks(date: str | None = None, db: Session = Depends(get_db),
               user: User = Depends(get_user)):
    stmt = select(Task).where(Task.user_id == user.id, Task.status != "cancelled")
    if date:
        stmt = stmt.join(DailyTaskPlacement, DailyTaskPlacement.task_id == Task.id) \
            .where(DailyTaskPlacement.date == dt.date.fromisoformat(date))
    return [_task_dict(db, t) for t in db.scalars(stmt.order_by(Task.id.desc())).all()]


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatchBody, db: Session = Depends(get_db),
               user: User = Depends(get_user)):
    t = db.get(Task, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "کار پیدا نشد.")
    if body.title is not None:
        t.title = body.title
    if body.priority is not None:
        t.priority = max(1, min(10, body.priority))
    if body.question_count is not None:
        t.question_count = max(1, body.question_count)
    if body.estimated_minutes is not None:
        t.estimated_minutes = body.estimated_minutes
    if body.parity is not None:
        t.parity = body.parity
    if body.timed is not None:
        t.timed = body.timed
    if body.status is not None:
        if body.status not in ("planned", "in_progress", "completed", "cancelled"):
            raise HTTPException(400, "وضعیت نامعتبر است.")
        t.status = body.status
    # هر ویرایش دستی → manual_override (Planner دیگر بدون اجازه تغییرش نمی‌دهد)
    t.manual_override = True
    t.updated_by = "user"
    if body.override_reason:
        t.override_reason = body.override_reason
    behavior_mod.log_event(db, user.id, "task_edited", {"task_id": t.id})
    db.commit()
    return _task_dict(db, t)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    t = db.get(Task, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "کار پیدا نشد.")
    behavior_mod.log_event(db, user.id, "task_deleted", {"task_id": t.id, "title": t.title})
    for p in db.scalars(select(DailyTaskPlacement).where(DailyTaskPlacement.task_id == t.id)):
        db.delete(p)
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/move")
def move_task(task_id: int, body: MoveBody, db: Session = Depends(get_db),
              user: User = Depends(get_user)):
    t = db.get(Task, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "کار پیدا نشد.")
    d = dt.date.fromisoformat(body.date)
    placement = db.execute(
        select(DailyTaskPlacement).where(DailyTaskPlacement.task_id == t.id)
        .order_by(DailyTaskPlacement.id.desc())).scalars().first()
    if placement is None:
        placement = DailyTaskPlacement(task_id=t.id, date=d, position=body.position or 0)
        db.add(placement)
    else:
        placement.date = d
        if body.position is not None:
            placement.position = body.position
    t.due_at = d
    t.manual_override = True
    t.updated_by = "user"
    behavior_mod.log_event(db, user.id, "task_rescheduled", {"task_id": t.id, "to": body.date})
    db.commit()
    return _task_dict(db, t)


@router.post("/tasks/{task_id}/split")
def split_task(task_id: int, body: SplitBody, db: Session = Depends(get_db),
               user: User = Depends(get_user)):
    """Split — مثلاً برای شکستن کار سخت (پیشنهاد تشخیص اهمال‌کاری)."""
    t = db.get(Task, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "کار پیدا نشد.")
    placement = db.execute(
        select(DailyTaskPlacement).where(DailyTaskPlacement.task_id == t.id)
        .order_by(DailyTaskPlacement.id.desc())).scalars().first()
    d1 = placement.date if placement else today_tehran()
    d2 = dt.date.fromisoformat(body.second_date) if body.second_date else d1

    total = max(t.question_count, 2)
    first = max(1, int(total * min(max(body.ratio, 0.1), 0.9)))
    second = total - first

    t.question_count = first
    t.title = f"{t.title} (۱ از ۲)"
    t.manual_override = True
    t.updated_by = "user"

    t2 = Task(
        user_id=user.id, task_type=t.task_type, title=f"{t.title.replace(' (۱ از ۲)', '')} (۲ از ۲)",
        source_type=t.source_type, source="manual", priority=t.priority,
        estimated_minutes=t.estimated_minutes, due_at=d2, status="planned",
        book_id=t.book_id, node_id=t.node_id, question_count=second,
        parity=t.parity, timed=t.timed, manual_override=True,
        created_by="user", updated_by="user")
    db.add(t2)
    db.flush()
    db.add(DailyTaskPlacement(task_id=t2.id, date=d2, position=1))
    behavior_mod.log_event(db, user.id, "task_split", {
        "task_id": t.id, "new_task_id": t2.id})
    db.commit()
    return {"ok": True, "first": _task_dict(db, t), "second": _task_dict(db, t2)}


@router.post("/tasks/{task_id}/merge")
def merge_task(task_id: int, body: MergeBody, db: Session = Depends(get_db),
               user: User = Depends(get_user)):
    t1 = db.get(Task, task_id)
    t2 = db.get(Task, body.other_task_id)
    if t1 is None or t2 is None or t1.user_id != user.id or t2.user_id != user.id:
        raise HTTPException(404, "کار پیدا نشد.")
    t1.question_count = t1.question_count + t2.question_count
    t1.title = t1.title.replace(" (۱ از ۲)", "")
    t1.manual_override = True
    t1.updated_by = "user"
    if (t2.estimated_minutes or 0) > (t1.estimated_minutes or 0):
        t1.estimated_minutes = t2.estimated_minutes
    behavior_mod.log_event(db, user.id, "task_merged", {
        "task_id": t1.id, "absorbed": t2.id})
    for p in db.scalars(select(DailyTaskPlacement).where(DailyTaskPlacement.task_id == t2.id)):
        db.delete(p)
    db.delete(t2)
    db.commit()
    return _task_dict(db, t1)


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    t = db.get(Task, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "کار پیدا نشد.")
    if t.status == "completed":
        return _task_dict(db, t)
    t.status = "completed"
    t.updated_by = "user"
    rewards_mod.complete_task_rewards(db, user, t)

    # حلقهٔ تطبیق: مشاهدهٔ امروز برای ظرفیت
    placement = db.execute(
        select(DailyTaskPlacement).where(DailyTaskPlacement.task_id == t.id)
        .order_by(DailyTaskPlacement.id.desc())).scalars().first()
    if placement:
        from app.jalali import is_school_day
        day_type = "school" if is_school_day(placement.date) else "free"
        done_today = db.execute(
            select(Task).join(DailyTaskPlacement, DailyTaskPlacement.task_id == Task.id)
            .where(DailyTaskPlacement.date == placement.date, Task.user_id == user.id,
                   Task.status == "completed")).scalars().all()
        capacity_mod.update_capacity_from_observation(db, user.id, day_type, len(done_today))

    behavior_mod.log_event(db, user.id, "task_completed", {
        "task_id": t.id, "task_type": t.task_type,
        "difficulty": "hard" if (t.estimated_minutes or 60) >= 100 else "normal"})
    db.commit()
    return _task_dict(db, t)


@router.post("/tasks/{task_id}/uncomplete")
def uncomplete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    t = db.get(Task, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "کار پیدا نشد.")
    t.status = "planned"
    behavior_mod.log_event(db, user.id, "task_uncompleted", {"task_id": t.id})
    db.commit()
    return _task_dict(db, t)


@router.post("/tasks/{task_id}/accept-suggestion")
def accept_suggestion(task_id: int, db: Session = Depends(get_db),
                      user: User = Depends(get_user)):
    """پذیرش پیشنهاد سیستم → تبدیل به تعهد کاربر."""
    t = db.get(Task, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "کار پیدا نشد.")
    t.source = "manual"
    t.manual_override = True
    t.updated_by = "user"
    behavior_mod.log_event(db, user.id, "suggestion_accepted", {"task_id": t.id})
    db.commit()
    return _task_dict(db, t)


@router.post("/tasks/{task_id}/reject-suggestion")
def reject_suggestion(task_id: int, db: Session = Depends(get_db),
                      user: User = Depends(get_user)):
    """رد پیشنهاد — نه خطا، بلکه evidence برای Planner."""
    t = db.get(Task, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "کار پیدا نشد.")
    behavior_mod.log_event(db, user.id, "suggestion_rejected", {
        "task_id": t.id, "title": t.title, "reason": t.recommendation_reason})
    for p in db.scalars(select(DailyTaskPlacement).where(DailyTaskPlacement.task_id == t.id)):
        db.delete(p)
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.put("/planner/placements")
def set_placements(placements: list[dict], db: Session = Depends(get_db),
                   user: User = Depends(get_user)):
    for p in placements:
        t = db.get(Task, p.get("task_id"))
        if t is None or t.user_id != user.id:
            continue
        d = dt.date.fromisoformat(p["date"])
        row = db.execute(
            select(DailyTaskPlacement).where(DailyTaskPlacement.task_id == t.id)
            .order_by(DailyTaskPlacement.id.desc())).scalars().first()
        if row is None:
            db.add(DailyTaskPlacement(task_id=t.id, date=d,
                                      position=p.get("position", 0)))
        else:
            row.date = d
            row.position = p.get("position", row.position)
        t.due_at = d
        t.manual_override = True
    db.commit()
    return {"ok": True}
