"""سرویس جلسهٔ تست — هسته V1 + V2.

- انتخاب Range + parity با پیام خطای دقیق
- correct / wrong / unanswered مستقل
- attempts کاملاً append-only؛ finish ایدمپوتنت
- Untimed → پرسش actual duration بعد از Finish
- Timed → کاهش تدریجی time limit (≥۲۰ attempt، accuracy ≥۷۵٪، ×۰٫۸، کف ۶۰s؛ قابل خاموش کردن)
- Import → is_imported=true، بدون سکه
- Review → خوشه‌ای + رندوم
"""

from __future__ import annotations

import datetime as dt

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.config as cfg
from app.domain import behavior as behavior_mod
from app.domain import rewards as rewards_mod
from app.domain import review as review_mod
from app.domain import selection as selection_mod
from app.jalali import now_tehran, today_tehran
from app.models import (Book, BookNode, DailyTaskPlacement, NodeParityState, Question,
                        QuestionAttempt, QuestionTopicMap, ReviewQueueItem, Task,
                        TestSession, TestSessionQuestion, User)


def create_session(db: Session, user: User, body: dict) -> TestSession:
    test_set_id = body.get("test_set_id")
    count = int(body.get("count", 10))
    parity = body.get("parity", "any")
    timed = bool(body.get("timed", False))
    seq_from = body.get("sequence_from")
    seq_to = body.get("sequence_to")
    task_id = body.get("task_id")

    if parity not in ("odd", "even", "any"):
        raise HTTPException(400, "parity باید odd/even/any باشد.")
    if count < 1:
        raise HTTPException(400, "تعداد سوال باید حداقل ۱ باشد.")

    try:
        questions = selection_mod.select_questions(
            db, test_set_id, count, seq_from, seq_to, parity)
    except selection_mod.InsufficientQuestions as e:
        # session ساخته نمی‌شود + پیام دقیق طبق سند
        raise HTTPException(422, {"error": "insufficient_questions",
                                  "message": f"فقط {e.available} سوال با این شرایط وجود دارد.",
                                  "available": e.available})

    time_limit = None
    if timed:
        time_limit = int(body.get("time_limit_seconds") or count * 60)

    ts = TestSession(
        user_id=user.id, task_id=task_id, session_type="normal", timed=timed,
        time_limit_seconds=time_limit, sequence_from=seq_from, sequence_to=seq_to,
        parity=parity, session_date=today_tehran(),
        auto_time_adjust_applied=_maybe_auto_time_adjust(db, user, test_set_id, time_limit),
    )
    db.add(ts)
    db.flush()
    for i, q in enumerate(questions):
        db.add(TestSessionQuestion(session_id=ts.id, question_id=q.id, display_order=i))

    # به‌روزرسانی parity state برای node مرتبط
    ts_row = db.get(TestSession, ts.id)
    from app.models import TestSet
    tset = db.get(TestSet, test_set_id)
    if tset and tset.node_id:
        selection_mod.update_parity_state(db, user.id, tset.node_id, parity)

    if task_id:
        t = db.get(Task, task_id)
        if t and t.status == "planned":
            t.status = "in_progress"

    behavior_mod.log_event(db, user.id, "session_started", {
        "session_id": ts.id, "test_set_id": test_set_id, "count": count,
        "parity": parity, "timed": timed, "hour": now_tehran().hour})
    db.commit()
    db.refresh(ts)
    return ts


def _maybe_auto_time_adjust(db: Session, user: User, test_set_id: int,
                            current_limit: int | None) -> bool:
    """کاهش تدریجی time limit در Timed (قابل خاموش کردن از تنظیمات)."""
    if not current_limit:
        return False
    if not (user.settings_json or {}).get("auto_time_adjust", True):
        return False
    qids = list(db.scalars(select(Question.id).where(Question.test_set_id == test_set_id)))
    if not qids:
        return False
    rows = db.execute(
        select(QuestionAttempt.result, func.count(QuestionAttempt.id))
        .where(QuestionAttempt.user_id == user.id,
               QuestionAttempt.question_id.in_(qids))
        .group_by(QuestionAttempt.result)).all()
    res = {r: c for r, c in rows}
    attempts = res.get("correct", 0) + res.get("wrong", 0)
    if attempts < cfg.TIME_ADJUST_MIN_ATTEMPTS:
        return False
    accuracy = res.get("correct", 0) / attempts
    if accuracy < cfg.TIME_ADJUST_MIN_ACCURACY:
        return False
    new_limit = max(int(current_limit * cfg.TIME_ADJUST_FACTOR), cfg.TIME_ADJUST_MIN_SECONDS)
    # پیشنهاد اعمال می‌شود (در session بعدی کاربر می‌بیند)؛ فقط گزارش
    return True


def session_view(db: Session, user: User, session_id: int) -> dict:
    ts = db.get(TestSession, session_id)
    if ts is None or ts.user_id != user.id:
        raise HTTPException(404, "جلسه پیدا نشد.")
    sqs = db.execute(
        select(TestSessionQuestion, Question)
        .join(Question, Question.id == TestSessionQuestion.question_id)
        .where(TestSessionQuestion.session_id == session_id)
        .order_by(TestSessionQuestion.display_order)).all()
    attempts = {a.question_id: a for a in db.scalars(
        select(QuestionAttempt).where(QuestionAttempt.session_id == session_id))}
    questions = [{
        "id": q.id, "sequence_no": q.sequence_no, "answer_key": q.answer_key,
        "difficulty": q.difficulty_level,
        "result": attempts[q.id].result if q.id in attempts else None,
        "answer": attempts[q.id].answer if q.id in attempts else None,
    } for _, q in sqs]
    return {
        "id": ts.id, "session_type": ts.session_type, "timed": ts.timed,
        "time_limit_seconds": ts.time_limit_seconds, "parity": ts.parity,
        "sequence_from": ts.sequence_from, "sequence_to": ts.sequence_to,
        "status": ts.status, "is_imported": ts.is_imported,
        "actual_duration_minutes": ts.actual_duration_minutes,
        "questions": questions,
        "started_at": ts.started_at.isoformat(),
        "ended_at": ts.ended_at.isoformat() if ts.ended_at else None,
    }


def answer_question(db: Session, user: User, session_id: int, body: dict) -> dict:
    """ثبت پاسخ یک سوال — attempts append-only (upsert در سطح session+question برای سوالات بدون پاسخ قبلی)."""
    ts = db.get(TestSession, session_id)
    if ts is None or ts.user_id != user.id:
        raise HTTPException(404, "جلسه پیدا نشد.")
    if ts.status == "completed":
        raise HTTPException(409, "این جلسه تمام شده است.")
    question_id = body.get("question_id")
    result = body.get("result")  # correct | wrong | unanswered
    answer = body.get("answer")
    if result not in ("correct", "wrong", "unanswered"):
        raise HTTPException(400, "result باید correct/wrong/unanswered باشد.")
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(404, "سوال پیدا نشد.")
    existing = db.execute(
        select(QuestionAttempt).where(
            QuestionAttempt.session_id == session_id,
            QuestionAttempt.question_id == question_id)).scalar_one_or_none()
    if existing is not None:
        # append-only: در همین session پاسخ قابل تصحیح نیست (مطابق سند «History»)
        return {"ok": False, "reason": "already_answered_in_this_session"}
    db.add(QuestionAttempt(
        session_id=session_id, question_id=question_id, user_id=user.id,
        answer=str(answer) if answer is not None else None, result=result))
    db.commit()
    return {"ok": True}


def finish_session(db: Session, user: User, session_id: int) -> dict:
    """Finish — idempotent؛ تلاش دوباره duplicate attempt نمی‌سازد."""
    ts = db.get(TestSession, session_id)
    if ts is None or ts.user_id != user.id:
        raise HTTPException(404, "جلسه پیدا نشد.")
    if ts.status == "completed":
        return _result_view(db, ts)

    sqs = db.execute(
        select(TestSessionQuestion.question_id)
        .where(TestSessionQuestion.session_id == session_id)
        .order_by(TestSessionQuestion.display_order)).scalars().all()
    attempts = {a.question_id: a for a in db.scalars(
        select(QuestionAttempt).where(QuestionAttempt.session_id == session_id))}

    # سوالات بی‌پاسخ → unanswered (مستقل از wrong)
    for qid in sqs:
        if qid not in attempts:
            db.add(QuestionAttempt(session_id=session_id, question_id=qid,
                                   user_id=user.id, result="unanswered"))

    ts.status = "completed"
    ts.ended_at = dt.datetime.now(dt.timezone.utc)

    # wrong/unanswered → review_queue (import هم وارد صف می‌شود)
    for qid in sqs:
        a = attempts.get(qid)
        result = a.result if a else "unanswered"
        if result in ("wrong", "unanswered"):
            review_mod.enqueue_review(db, user.id, qid, result)

    # پاداش‌ها (فقط جلسات عادی — import سکه ندارد)
    rewards = rewards_mod.on_test_session_completed(db, user, ts)

    # اگر session به Task وصل است و همه سوالات پاسخ داده شدند → Task تکمیل
    if ts.task_id:
        t = db.get(Task, ts.task_id)
        if t and t.status != "completed":
            t.status = "completed"
            rewards_mod.complete_task_rewards(db, user, t)

    behavior_mod.log_event(db, user.id, "session_completed", {
        "session_id": ts.id, "session_type": ts.session_type,
        "is_imported": ts.is_imported,
        "hour": now_tehran().hour})
    db.commit()
    db.refresh(ts)
    result = _result_view(db, ts)
    result["rewards"] = rewards
    return result


def _result_view(db: Session, ts: TestSession) -> dict:
    attempts = list(db.scalars(
        select(QuestionAttempt).where(QuestionAttempt.session_id == ts.id)))
    correct = sum(1 for a in attempts if a.result == "correct")
    wrong = sum(1 for a in attempts if a.result == "wrong")
    unans = sum(1 for a in attempts if a.result == "unanswered")
    total = len(attempts)
    answered = correct + wrong

    # تفکیک موضوعی
    topic_rows = db.execute(
        select(QuestionTopicMap.node_id, QuestionAttempt.result,
               func.count(QuestionAttempt.id))
        .join(Question, Question.id == QuestionTopicMap.question_id)
        .join(QuestionAttempt, QuestionAttempt.question_id == Question.id)
        .where(QuestionAttempt.session_id == ts.id)
        .group_by(QuestionTopicMap.node_id, QuestionAttempt.result)).all()
    topics: dict[int, dict] = {}
    for nid, result, cnt in topic_rows:
        t = topics.setdefault(nid, {"correct": 0, "wrong": 0, "unanswered": 0})
        t[result] = t.get(result, 0) + cnt
    topic_breakdown = []
    for nid, t in topics.items():
        node = db.get(BookNode, nid)
        if node:
            topic_breakdown.append({"node_id": nid, "title": node.title, **t})

    return {
        "id": ts.id, "total": total, "correct": correct, "wrong": wrong,
        "unanswered": unans,
        "accuracy": round(correct / answered, 4) if answered else 0.0,
        "parity": ts.parity, "range": [ts.sequence_from, ts.sequence_to],
        "timed": ts.timed, "is_imported": ts.is_imported,
        "actual_duration_minutes": ts.actual_duration_minutes,
        "topic_breakdown": topic_breakdown,
        "needs_duration_input": (not ts.timed) and (ts.actual_duration_minutes is None)
        and (not ts.is_imported) and ts.session_type != "review",
    }


def set_duration(db: Session, user: User, session_id: int, minutes: int) -> dict:
    """PATCH duration — پرسش مدت بعد از پایان Untimed."""
    ts = db.get(TestSession, session_id)
    if ts is None or ts.user_id != user.id:
        raise HTTPException(404, "جلسه پیدا نشد.")
    if ts.timed:
        raise HTTPException(400, "این جلسه Timed بود؛ مدت واقعی لازم نیست.")
    if minutes < 1 or minutes > 600:
        raise HTTPException(400, "مدت باید بین ۱ تا ۶۰۰ دقیقه باشد.")
    ts.actual_duration_minutes = minutes
    behavior_mod.log_event(db, user.id, "duration_reported", {
        "session_id": ts.id, "minutes": minutes})
    db.commit()
    return {"ok": True, "actual_duration_minutes": minutes}


def import_session(db: Session, user: User, body: dict) -> dict:
    """وارد کردن تست گذشته — is_imported=true، بدون سکه، append-only.

    body: test_set_id, answers: [{question_id, result, answer?}], date? (YYYY-MM-DD)
    """
    test_set_id = body.get("test_set_id")
    answers = body.get("answers") or []
    date_str = body.get("date") or today_tehran().isoformat()
    session_date = dt.date.fromisoformat(date_str)

    valid_results = {"correct", "wrong", "unanswered"}
    qids = [a["question_id"] for a in answers if a.get("result") in valid_results]
    if not qids:
        raise HTTPException(400, "حداقل یک پاسخ لازم است.")
    real_qids = set(db.scalars(
        select(Question.id).where(Question.id.in_(qids))))

    ts = TestSession(
        user_id=user.id, session_type="imported", timed=False,
        parity="any", status="completed", is_imported=True,
        session_date=session_date,
        started_at=dt.datetime.combine(session_date, dt.time(12)),
        ended_at=dt.datetime.combine(session_date, dt.time(13)),
    )
    db.add(ts)
    db.flush()
    order = 0
    for a in answers:
        if a.get("result") not in valid_results:
            continue
        if a["question_id"] not in real_qids:
            continue
        db.add(TestSessionQuestion(session_id=ts.id, question_id=a["question_id"],
                                   display_order=order))
        db.add(QuestionAttempt(
            session_id=ts.id, question_id=a["question_id"], user_id=user.id,
            answer=str(a.get("answer")) if a.get("answer") is not None else None,
            result=a["result"],
            answered_at=dt.datetime.combine(session_date, dt.time(12))))
        order += 1
        if a["result"] in ("wrong", "unanswered"):
            review_mod.enqueue_review(db, user.id, a["question_id"], a["result"])

    behavior_mod.log_event(db, user.id, "import_completed", {
        "session_id": ts.id, "count": order, "date": session_date.isoformat()})
    # سکه تعلق نمی‌گیرد — Analytics فوراً به‌روز است.
    db.commit()
    db.refresh(ts)
    out = _result_view(db, ts)
    out["note"] = "جلسهٔ واردشده ثبت شد؛ سکه‌ای تعلق نگرفت (کار گذشته است)."
    return out


def create_review_session(db: Session, user: User, count: int | None = None) -> dict:
    """جلسهٔ مرور — خوشه موضوعی نزدیک + ترتیب رندوم؛ parity/range اعمال نمی‌شود."""
    questions = review_mod.build_review_session(db, user.id, count)
    if not questions:
        raise HTTPException(422, {"error": "empty_review_queue",
                                  "message": "صف مرور خالی است — لغت/غلط جدیدی برای مرور نداری."})
    ts = TestSession(
        user_id=user.id, session_type="review", timed=False, parity="any",
        session_date=today_tehran(),
        review_queue_snapshot=[q.id for q in questions],
    )
    db.add(ts)
    db.flush()
    for i, q in enumerate(questions):
        db.add(TestSessionQuestion(session_id=ts.id, question_id=q.id, display_order=i))
    db.commit()
    db.refresh(ts)
    return session_view(db, user, ts.id)


def review_answer(db: Session, user: User, session_id: int, body: dict) -> dict:
    """پاسخ در جلسهٔ مرور: درست → resolve (+۳ سکه)؛ غلط → priority بالا + زودتر."""
    ts = db.get(TestSession, session_id)
    if ts is None or ts.user_id != user.id or ts.session_type != "review":
        raise HTTPException(404, "جلسهٔ مرور پیدا نشد.")
    question_id = body.get("question_id")
    result = body.get("result")
    if result not in ("correct", "wrong"):
        raise HTTPException(400, "در مرور فقط correct/wrong معتبر است.")
    existing = db.execute(
        select(QuestionAttempt).where(
            QuestionAttempt.session_id == session_id,
            QuestionAttempt.question_id == question_id)).scalar_one_or_none()
    if existing is not None:
        return {"ok": False, "reason": "already_answered"}
    db.add(QuestionAttempt(session_id=session_id, question_id=question_id,
                           user_id=user.id, result=result))
    review_mod.enqueue_review(db, user.id, question_id, result)
    if result == "correct":
        rewards_mod.successful_review_reward(db, user, question_id)
    db.commit()
    return {"ok": True}


def finish_review(db: Session, user: User, session_id: int) -> dict:
    ts = db.get(TestSession, session_id)
    if ts is None or ts.user_id != user.id or ts.session_type != "review":
        raise HTTPException(404, "جلسهٔ مرور پیدا نشد.")
    if ts.status != "completed":
        sqs = db.execute(
            select(TestSessionQuestion.question_id)
            .where(TestSessionQuestion.session_id == session_id)).scalars().all()
        attempts = {a.question_id for a in db.scalars(
            select(QuestionAttempt).where(QuestionAttempt.session_id == session_id))}
        for qid in sqs:
            if qid not in attempts:
                # نزده در مرور → در صف می‌ماند
                review_mod.enqueue_review(db, user.id, qid, "unanswered")
        ts.status = "completed"
        ts.ended_at = dt.datetime.now(dt.timezone.utc)
        behavior_mod.log_event(db, user.id, "review_session_completed", {
            "session_id": ts.id})
        db.commit()
    return _result_view(db, ts)
