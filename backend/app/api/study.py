"""داشبورد، برنامه‌ریزی، Taskها، موتور تست، مرور، تدریس‌شده، سکه، رفتار و وضعیت."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config as cfg
from .. import models as m
from ..db import get_db
from ..schemas import (
    DraftIn,
    FinishIn,
    InterviewAnswers,
    OnboardingAnswerIn,
    SessionCreate,
    StateCheckIn,
    TaskIn,
    TaskMove,
    TaskPatch,
    TaskSplit,
    TaughtTopicIn,
    WakeUpIn,
)
from ..services import planner, readiness, rewards, taught, test_engine
from ..services.common import current_user, log_behavior, node_full_title
from ..utils import jalali

router = APIRouter(prefix="/api", tags=["study"])


def _task_dto(db: Session, t: m.Task) -> dict:
    subject = db.get(m.Subject, t.subject_id) if t.subject_id else None
    return {
        "id": t.id, "title": t.title, "task_type": t.task_type,
        "subject": subject.name if subject else None,
        "subject_color": subject.color if subject else "#64748b",
        "book_id": t.book_id, "node_id": t.node_id,
        "node_title": node_full_title(db, t.node_id) if t.node_id else None,
        "source_type": t.source_type, "priority": t.priority,
        "quantity": t.quantity, "estimated_minutes": t.estimated_minutes,
        "parity": t.parity, "planned_date": t.planned_date.isoformat(),
        "planned_date_jalali": jalali.to_jalali_str(t.planned_date),
        "planned_time": t.planned_time,
        "due_at": t.due_at.isoformat() if t.due_at else None,
        "due_at_jalali": jalali.to_jalali_str(t.due_at) if t.due_at else None,
        "status": t.status,
        "recommendation_reason": t.recommendation_reason,
        "manual_override": t.manual_override,
    }


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    user = current_user(db)
    today = date.today()
    tasks = db.scalars(select(m.Task).where(
        m.Task.user_id == user.id, m.Task.planned_date == today)
        .order_by(m.Task.priority.desc())).all()
    done = sum(1 for t in tasks if t.status == "completed")

    attempts_today = db.scalar(select(func.count(m.QuestionAttempt.id)).join(
        m.TestSession, m.QuestionAttempt.session_id == m.TestSession.id).where(
        m.QuestionAttempt.user_id == user.id, m.TestSession.session_date == today)) or 0
    week_start = jalali.week_start(today)
    attempts_week = db.scalar(select(func.count(m.QuestionAttempt.id)).join(
        m.TestSession, m.QuestionAttempt.session_id == m.TestSession.id).where(
        m.QuestionAttempt.user_id == user.id,
        m.TestSession.session_date >= week_start)) or 0
    all_rows = db.execute(select(m.QuestionAttempt.result).where(
        m.QuestionAttempt.user_id == user.id)).all()
    correct = sum(1 for r in all_rows if r[0] == "correct")
    wrong = sum(1 for r in all_rows if r[0] == "wrong")
    unanswered = sum(1 for r in all_rows if r[0] == "unanswered")
    review_open = db.scalar(select(func.count(m.ReviewQueue.id)).where(
        m.ReviewQueue.user_id == user.id, m.ReviewQueue.status == "open")) or 0
    review_due = db.scalar(select(func.count(m.ReviewQueue.id)).where(
        m.ReviewQueue.user_id == user.id, m.ReviewQueue.status == "open",
        m.ReviewQueue.scheduled_for <= today)) or 0

    taught_data = taught.insights(db, user)
    return {
        "user": {"display_name": user.display_name, "grade": user.grade,
                 "track": user.track, "season_mode": user.season_mode},
        "today": jalali.describe(today),
        "week": {
            "start": jalali.to_jalali_str(week_start),
            "end": jalali.to_jalali_str(jalali.week_end(today)),
            "label": f"این هفته (شنبه {jalali.to_jalali_str(week_start)} تا "
                     f"جمعه {jalali.to_jalali_str(jalali.week_end(today))})",
        },
        "tasks": {"total": len(tasks), "done": done, "pending": len(tasks) - done},
        "attempts": {"today": attempts_today, "week": attempts_week,
                     "total": len(all_rows)},
        "quality": {
            "correct": correct, "wrong": wrong, "unanswered": unanswered,
            "accuracy": round(correct / (correct + wrong), 3) if (correct + wrong) else 0.0,
        },
        "review": {"open": review_open, "due": review_due},
        "rewards": rewards.summary(db, user),
        "capacity": planner.day_capacity(db, user, today),
        "state": planner.current_state(db, user),
        "habit": planner.habit_summary(db, user),
        "habit_advice": planner.habit_advice(db, user, today, len(tasks)),
        "taught_counts": taught_data["counts"],
        "taught_warnings": taught_data["warnings"][:3],
        "exam_coverage_card": readiness.weekly_exam_coverage_card(db, user),
        "upcoming_reminders": [
            u for u in readiness.list_upcoming(db, user) if u["reminder"]
        ],
    }


@router.get("/week")
def week_view(anchor: date | None = None, db: Session = Depends(get_db)):
    user = current_user(db)
    days = jalali.week_days(anchor or date.today())
    out = []
    for d in days:
        tasks = db.scalars(select(m.Task).where(
            m.Task.user_id == user.id, m.Task.planned_date == d)
            .order_by(m.Task.priority.desc())).all()
        out.append({
            **jalali.describe(d),
            "capacity": planner.day_capacity(db, user, d),
            "tasks": [_task_dto(db, t) for t in tasks],
        })
    return {"week_start": jalali.to_jalali_str(days[0]),
            "week_end": jalali.to_jalali_str(days[-1]), "days": out}


# ------------------------------------------------------------------ tasks
@router.get("/tasks")
def list_tasks(day: date | None = None, status: str | None = None,
               db: Session = Depends(get_db)):
    user = current_user(db)
    q = select(m.Task).where(m.Task.user_id == user.id)
    if day:
        q = q.where(m.Task.planned_date == day)
    if status:
        q = q.where(m.Task.status == status)
    return [_task_dto(db, t) for t in db.scalars(
        q.order_by(m.Task.planned_date, m.Task.priority.desc())).all()]


@router.post("/tasks")
def create_task(body: TaskIn, db: Session = Depends(get_db)):
    user = current_user(db)
    t = m.Task(user_id=user.id, **{**body.model_dump(),
               "planned_date": body.planned_date or date.today()})
    t.manual_override = body.source_type == "manual"
    db.add(t)
    log_behavior(db, user.id, "task_created", {"source": body.source_type})
    db.commit()
    return _task_dto(db, t)


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch, db: Session = Depends(get_db)):
    user = current_user(db)
    t = db.get(m.Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "کار یافت نشد.")
    data = body.model_dump(exclude_unset=True)
    was_completed = t.status == "completed"
    for k, v in data.items():
        if k == "override_reason":
            t.override_reason = v
        else:
            setattr(t, k, v)
    t.manual_override = True
    if t.status == "completed" and not was_completed:
        t.completed_at = datetime.utcnow()
        if t.task_type != "test":
            rewards.award(db, user, "task_completed", cfg.POINTS_COMPLETE_TASK,
                          "تکمیل کار مطالعه", "task", t.id)
        rewards.touch_streak(db, user)
        _maybe_daily_bonus(db, user, t.planned_date)
    log_behavior(db, user.id, "task_edited", {"task_id": t.id, "fields": list(data)})
    db.commit()
    return _task_dto(db, t)


def _maybe_daily_bonus(db: Session, user: m.User, day: date) -> None:
    tasks = db.scalars(select(m.Task).where(
        m.Task.user_id == user.id, m.Task.planned_date == day)).all()
    test_tasks = [t for t in tasks if t.task_type in ("test", "exam_prep")]
    if test_tasks and all(t.status == "completed" for t in test_tasks):
        already = db.scalar(select(m.RewardEvent).where(
            m.RewardEvent.user_id == user.id, m.RewardEvent.event_date == day,
            m.RewardEvent.event_type == "daily_tests_complete"))
        if not already:
            rewards.award(db, user, "daily_tests_complete", cfg.POINTS_COMPLETE_DAILY_TESTS,
                          "تکمیل تمام تست‌های روز", event_date=day)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    user = current_user(db)
    t = db.get(m.Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "کار یافت نشد.")
    db.delete(t)
    log_behavior(db, user.id, "task_deleted", {"task_id": task_id})
    db.commit()
    return {"deleted": True}


@router.post("/tasks/{task_id}/move")
def move_task(task_id: int, body: TaskMove, db: Session = Depends(get_db)):
    user = current_user(db)
    t = db.get(m.Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "کار یافت نشد.")
    t.planned_date = body.planned_date
    t.manual_override = True
    t.override_reason = body.override_reason
    log_behavior(db, user.id, "task_moved", {"task_id": t.id,
                                             "to": body.planned_date.isoformat()})
    db.commit()
    return _task_dto(db, t)


@router.post("/tasks/{task_id}/split")
def split_task(task_id: int, body: TaskSplit, db: Session = Depends(get_db)):
    user = current_user(db)
    t = db.get(m.Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "کار یافت نشد.")
    per = max(1, t.quantity // body.parts)
    minutes = max(10, t.estimated_minutes // body.parts)
    created = []
    for i in range(body.parts - 1):
        nt = m.Task(
            user_id=user.id, task_type=t.task_type,
            title=f"{t.title} — بخش {i + 2}", subject_id=t.subject_id,
            book_id=t.book_id, node_id=t.node_id, source_type=t.source_type,
            source_id=t.source_id, priority=t.priority, quantity=per,
            estimated_minutes=minutes, parity=t.parity,
            planned_date=t.planned_date + timedelta(days=i + 1),
            due_at=t.due_at, recommendation_reason="ایجادشده با split دستی",
            manual_override=True,
        )
        db.add(nt)
        created.append(nt)
    t.quantity = per
    t.estimated_minutes = minutes
    t.title = f"{t.title} — بخش ۱"
    t.manual_override = True
    db.commit()
    return {"parts": [_task_dto(db, t)] + [_task_dto(db, x) for x in created]}


@router.post("/planning/generate")
def generate(day: date | None = None, replace: bool = False,
             db: Session = Depends(get_db)):
    user = current_user(db)
    res = planner.generate_plan(db, user, day or date.today(), replace)
    db.commit()
    return res


@router.get("/planning/candidates")
def candidates(day: date | None = None, limit: int = 12, db: Session = Depends(get_db)):
    user = current_user(db)
    return planner.candidate_tasks(db, user, day or date.today(), limit)


# ------------------------------------------------------------------ test engine
@router.get("/nodes/{node_id}/parity-state")
def parity_state(node_id: int, db: Session = Depends(get_db)):
    user = current_user(db)
    st = db.scalar(select(m.NodeParityState).where(
        m.NodeParityState.user_id == user.id, m.NodeParityState.node_id == node_id))
    return {
        "last_parity": st.last_parity if st else None,
        "suggested_parity": test_engine.suggest_parity(db, user.id, node_id),
    }


@router.post("/test-sessions")
def create_session(body: SessionCreate, db: Session = Depends(get_db)):
    user = current_user(db)
    try:
        s = test_engine.create_session(
            db, user, body.node_id, body.count, body.sequence_from, body.sequence_to,
            body.parity, body.timed, body.time_limit_seconds, body.task_id)
        db.commit()
    except test_engine.SelectionError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    return get_session(s.id, db)


@router.post("/review-sessions")
def create_review(limit: int | None = None, db: Session = Depends(get_db)):
    user = current_user(db)
    try:
        s = test_engine.create_review_session(db, user, limit)
        db.commit()
    except test_engine.SelectionError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    return get_session(s.id, db)


@router.get("/test-sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    user = current_user(db)
    s = db.get(m.TestSession, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "جلسه یافت نشد.")
    rows = db.scalars(select(m.TestSessionQuestion).where(
        m.TestSessionQuestion.session_id == session_id)
        .order_by(m.TestSessionQuestion.display_order)).all()
    items = []
    for r in rows:
        q = db.get(m.Question, r.question_id)
        ts = db.get(m.TestSet, q.test_set_id)
        items.append({
            "question_id": q.id, "sequence_no": q.sequence_no,
            "difficulty_level": q.difficulty_level,
            "node_title": node_full_title(db, ts.node_id) if ts and ts.node_id else "",
        })
    return {
        "id": s.id, "kind": s.session_kind, "timed": s.timed,
        "time_limit_seconds": s.time_limit_seconds, "parity": s.parity,
        "range": [s.sequence_from, s.sequence_to], "status": s.status,
        "node_title": node_full_title(db, s.node_id) if s.node_id else "مرور",
        "questions": items,
    }


@router.post("/test-sessions/{session_id}/finish")
def finish_session(session_id: int, body: FinishIn, db: Session = Depends(get_db)):
    user = current_user(db)
    s = db.get(m.TestSession, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "جلسه یافت نشد.")
    res = test_engine.finish_session(
        db, user, s, [a.model_dump() for a in body.answers], body.actual_duration_minutes)
    db.commit()
    return res


@router.patch("/test-sessions/{session_id}/duration")
def set_duration(session_id: int, actual_duration_minutes: int,
                 db: Session = Depends(get_db)):
    user = current_user(db)
    s = db.get(m.TestSession, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "جلسه یافت نشد.")
    s.actual_duration_minutes = actual_duration_minutes
    db.commit()
    return {"id": s.id, "actual_duration_minutes": s.actual_duration_minutes}


@router.get("/review/queue")
def review_queue(db: Session = Depends(get_db)):
    user = current_user(db)
    rows = db.scalars(select(m.ReviewQueue).where(
        m.ReviewQueue.user_id == user.id, m.ReviewQueue.status == "open")
        .order_by(m.ReviewQueue.priority.desc(), m.ReviewQueue.scheduled_for)).all()
    out = []
    for r in rows:
        q = db.get(m.Question, r.question_id)
        ts = db.get(m.TestSet, q.test_set_id) if q else None
        out.append({
            "id": r.id, "question_id": r.question_id,
            "sequence_no": q.sequence_no if q else None,
            "node_title": node_full_title(db, ts.node_id) if ts and ts.node_id else "",
            "reason": r.reason, "wrong_count": r.wrong_count,
            "unanswered_count": r.unanswered_count,
            "critical": r.wrong_count >= cfg.REVIEW_CRITICAL_WRONG_COUNT,
            "scheduled_for_jalali": jalali.to_jalali_str(r.scheduled_for),
            "due": r.scheduled_for <= date.today(),
        })
    return {"total": len(out), "items": out}


# ------------------------------------------------------------------ taught
@router.get("/taught-topics")
def taught_list(db: Session = Depends(get_db)):
    return taught.insights(db, current_user(db))


@router.post("/taught-topics")
def taught_add(body: TaughtTopicIn, db: Session = Depends(get_db)):
    user = current_user(db)
    row = taught.add_taught(db, user, body.node_id, body.taught_at,
                            body.source_type, body.source_id, body.notes)
    rewards.check_badges(db, user)
    db.commit()
    return {"id": row.id, "node_id": row.node_id,
            "taught_at_jalali": jalali.to_jalali_str(row.taught_at)}


@router.delete("/taught-topics/{taught_id}")
def taught_delete(taught_id: int, db: Session = Depends(get_db)):
    user = current_user(db)
    row = db.get(m.TaughtTopic, taught_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "یافت نشد.")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.get("/taught-topics/insights")
def taught_insights(db: Session = Depends(get_db)):
    return taught.insights(db, current_user(db))


# ------------------------------------------------------------------ schedule
@router.get("/schedules")
def schedules(db: Session = Depends(get_db)):
    user = current_user(db)
    rows = db.scalars(select(m.Schedule).where(m.Schedule.user_id == user.id)).all()
    return [{
        "id": s.id, "title": s.title, "subject_id": s.subject_id,
        "subject": db.get(m.Subject, s.subject_id).name if s.subject_id else None,
        "day_of_week": s.day_of_week,
        "day_name": jalali.PERSIAN_WEEKDAYS[s.day_of_week] if s.day_of_week is not None else None,
        "start_time": s.start_time, "end_time": s.end_time, "source": s.source,
    } for s in rows]


@router.patch("/schedules/{schedule_id}")
def patch_schedule(schedule_id: int, day_of_week: int | None = None,
                   start_time: str | None = None, end_time: str | None = None,
                   db: Session = Depends(get_db)):
    user = current_user(db)
    s = db.get(m.Schedule, schedule_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "کلاس یافت نشد.")
    if day_of_week is not None:
        s.day_of_week = day_of_week if day_of_week >= 0 else None
    if start_time is not None:
        s.start_time = start_time or None
    if end_time is not None:
        s.end_time = end_time or None
    db.commit()
    return {"id": s.id}


@router.post("/schedules/seed-defaults")
def seed_defaults(db: Session = Depends(get_db)):
    from ..seed.seeder import seed_default_classes
    return seed_default_classes(db, current_user(db))


@router.post("/school-day-overrides")
def override_day(day: date, is_school_day: bool = False, reason: str = "",
                 db: Session = Depends(get_db)):
    user = current_user(db)
    row = db.scalar(select(m.SchoolDayOverride).where(
        m.SchoolDayOverride.user_id == user.id, m.SchoolDayOverride.date == day))
    if row:
        row.is_school_day = is_school_day
        row.reason = reason
    else:
        db.add(m.SchoolDayOverride(user_id=user.id, date=day,
                                   is_school_day=is_school_day, reason=reason))
    db.commit()
    return planner.day_capacity(db, user, day)


# ------------------------------------------------------------------ rewards
@router.get("/rewards/summary")
def rewards_summary(db: Session = Depends(get_db)):
    return rewards.summary(db, current_user(db))


@router.post("/rewards/wake-up")
def wake_up(body: WakeUpIn, db: Session = Depends(get_db)):
    user = current_user(db)
    now = datetime.now()
    if body.time:
        try:
            hh, mm = map(int, body.time.split(":"))
            now = now.replace(hour=hh, minute=mm)
        except ValueError:
            raise HTTPException(400, "فرمت ساعت نامعتبر است (مثال: 06:40).")
    res = rewards.record_wake_up(db, user, now, body.day)
    db.commit()
    return res


@router.get("/rewards/events")
def rewards_events(limit: int = 50, db: Session = Depends(get_db)):
    user = current_user(db)
    rows = db.scalars(select(m.RewardEvent).where(m.RewardEvent.user_id == user.id)
                      .order_by(m.RewardEvent.created_at.desc()).limit(limit)).all()
    return [{
        "id": r.id, "event_type": r.event_type, "points": r.points,
        "description": r.description,
        "date_jalali": jalali.to_jalali_str(r.event_date),
    } for r in rows]


# ------------------------------------------------------------------ V2.1
@router.get("/state/current")
def state_current(db: Session = Depends(get_db)):
    return planner.current_state(db, current_user(db))


@router.post("/state/check-in")
def state_checkin(body: StateCheckIn, db: Session = Depends(get_db)):
    user = current_user(db)
    readiness_val = round(
        body.energy * 0.3 + body.focus * 0.3 + body.motivation * 0.2
        + (1 - body.stress) * 0.1 + (1 - body.fatigue) * 0.1, 2)
    db.add(m.UserStateSnapshot(
        user_id=user.id, energy=body.energy, focus=body.focus,
        motivation=body.motivation, stress=body.stress, fatigue=body.fatigue,
        readiness=readiness_val,
        confidence_json={"source": "self_report", "confidence": 0.6},
    ))
    log_behavior(db, user.id, "state_check_in", body.model_dump())
    db.commit()
    return planner.current_state(db, user)


@router.get("/behavior/features")
def behavior_features(db: Session = Depends(get_db)):
    return planner.behavior_features(db, current_user(db))


@router.get("/habits/summary")
def habits_summary(db: Session = Depends(get_db)):
    return planner.habit_summary(db, current_user(db))


@router.get("/planning/weekly-interview/{week_start}")
def get_interview(week_start: date, db: Session = Depends(get_db)):
    user = current_user(db)
    row = db.scalar(select(m.PlanningInterview).where(
        m.PlanningInterview.user_id == user.id,
        m.PlanningInterview.week_start == week_start))
    return {
        "week_start": week_start.isoformat(),
        "week_start_jalali": jalali.to_jalali_str(week_start),
        "answers": row.answers_json if row else {},
        "completed": row.completed if row else False,
    }


@router.post("/planning/weekly-interview")
def save_interview(body: InterviewAnswers, db: Session = Depends(get_db)):
    user = current_user(db)
    ws = body.week_start or jalali.week_start(date.today())
    row = db.scalar(select(m.PlanningInterview).where(
        m.PlanningInterview.user_id == user.id, m.PlanningInterview.week_start == ws))
    if not row:
        row = m.PlanningInterview(user_id=user.id, week_start=ws)
        db.add(row)
    row.answers_json = {**(row.answers_json or {}), **body.answers}
    row.completed = body.complete or row.completed
    log_behavior(db, user.id, "weekly_interview", {"week_start": ws.isoformat()})
    db.commit()
    return {"week_start_jalali": jalali.to_jalali_str(ws),
            "answers": row.answers_json, "completed": row.completed}


@router.post("/onboarding/answers")
def onboarding_answer(body: OnboardingAnswerIn, db: Session = Depends(get_db)):
    user = current_user(db)
    db.add(m.OnboardingAnswer(user_id=user.id, question_code=body.question_code,
                              answer_value=body.answer_value))
    db.commit()
    return {"saved": True}


@router.get("/onboarding/summary")
def onboarding_summary(db: Session = Depends(get_db)):
    user = current_user(db)
    rows = db.scalars(select(m.OnboardingAnswer).where(
        m.OnboardingAnswer.user_id == user.id)).all()
    return {"answered": len(rows),
            "answers": {r.question_code: r.answer_value for r in rows}}


# ------------------------------------------------------------------ drafts (S2)
@router.get("/drafts/{scope}")
def get_draft(scope: str, db: Session = Depends(get_db)):
    user = current_user(db)
    row = db.scalar(select(m.AnswerDraft).where(
        m.AnswerDraft.user_id == user.id, m.AnswerDraft.scope == scope))
    return {"scope": scope, "payload": row.payload_json if row else {},
            "updated_at": row.updated_at.isoformat() if row else None}


@router.put("/drafts")
def put_draft(body: DraftIn, db: Session = Depends(get_db)):
    user = current_user(db)
    row = db.scalar(select(m.AnswerDraft).where(
        m.AnswerDraft.user_id == user.id, m.AnswerDraft.scope == body.scope))
    if row:
        row.payload_json = body.payload
    else:
        db.add(m.AnswerDraft(user_id=user.id, scope=body.scope, payload_json=body.payload))
    db.commit()
    return {"saved": True, "scope": body.scope}


@router.delete("/drafts/{scope}")
def delete_draft(scope: str, db: Session = Depends(get_db)):
    user = current_user(db)
    db.execute(m.AnswerDraft.__table__.delete().where(
        m.AnswerDraft.user_id == user.id, m.AnswerDraft.scope == scope))
    db.commit()
    return {"deleted": True}


# ------------------------------------------------------------------ progress
@router.get("/progress/overview")
def progress_overview(db: Session = Depends(get_db)):
    from ..services.common import node_stats
    user = current_user(db)
    books = []
    for b in db.scalars(select(m.Book).order_by(m.Book.id)).all():
        roots = db.scalars(select(m.BookNode).where(
            m.BookNode.book_id == b.id, m.BookNode.parent_id.is_(None))
            .order_by(m.BookNode.order_index)).all()
        chapters = []
        for r in roots:
            s = node_stats(db, user.id, r.id)
            chapters.append({"node_id": r.id, "title": r.title, **s})
        total = sum(c["total"] for c in chapters)
        attempted = sum(c["attempted"] for c in chapters)
        correct = sum(c["correct"] for c in chapters)
        wrong = sum(c["wrong"] for c in chapters)
        unanswered = sum(c["unanswered"] for c in chapters)
        books.append({
            "book_id": b.id, "title": b.title, "subject": b.subject.name,
            "color": b.subject.color, "chapters": chapters,
            "total": total, "attempted": attempted,
            "coverage": round(attempted / total, 3) if total else 0.0,
            "correct": correct, "wrong": wrong, "unanswered": unanswered,
            "accuracy": round(correct / (correct + wrong), 3) if (correct + wrong) else 0.0,
        })
    trend = []
    for i in range(13, -1, -1):
        d = date.today() - timedelta(days=i)
        n = db.scalar(select(func.count(m.QuestionAttempt.id)).join(
            m.TestSession, m.QuestionAttempt.session_id == m.TestSession.id).where(
            m.QuestionAttempt.user_id == user.id, m.TestSession.session_date == d)) or 0
        trend.append({"date_jalali": jalali.to_jalali_str(d),
                      "weekday": jalali.weekday_name(d), "attempts": n})
    return {"books": books, "trend": trend,
            "behavior": planner.behavior_features(db, user)}
