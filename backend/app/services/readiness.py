"""
آمادگی امتحان — سند 07_EXAM_READINESS (+ S6 حالت «۱۴ روز مانده»).
پیشنهاد فقط از سوال‌هایی که در بانک همان مباحث تعریف شده‌اند.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config as cfg
from .. import models as m
from ..utils import jalali
from .common import node_full_title, node_stats, questions_of_node
from .planner import day_capacity, suggested_task_count
from .test_engine import suggest_parity


def create_upcoming(db: Session, user: m.User, title: str, exam_date: date,
                    node_ids: list[int], notes: str = "") -> m.UpcomingExam:
    row = m.UpcomingExam(user_id=user.id, title=title, exam_date=exam_date, notes=notes)
    db.add(row)
    db.flush()
    for nid in dict.fromkeys(node_ids):
        db.add(m.UpcomingExamTopic(upcoming_exam_id=row.id, node_id=nid))
    db.flush()
    return row


def list_upcoming(db: Session, user: m.User) -> list[dict]:
    rows = db.scalars(select(m.UpcomingExam).where(
        m.UpcomingExam.user_id == user.id).order_by(m.UpcomingExam.exam_date)).all()
    out = []
    for r in rows:
        topics = db.scalars(select(m.UpcomingExamTopic).where(
            m.UpcomingExamTopic.upcoming_exam_id == r.id)).all()
        days_left = (r.exam_date - date.today()).days
        out.append({
            "id": r.id,
            "title": r.title,
            "exam_date": r.exam_date.isoformat(),
            "exam_date_jalali": jalali.to_jalali_str(r.exam_date, with_weekday=True),
            "days_left": days_left,
            "countdown_mode": 0 <= days_left <= cfg.READINESS_COUNTDOWN_DAYS,
            "reminder": days_left in (0, 1, 3),   # S15
            "topic_count": len(topics),
            "notes": r.notes,
        })
    return out


def suggested_tasks(db: Session, user: m.User, upcoming_id: int,
                    wrong_only: bool = False) -> dict:
    ue = db.get(m.UpcomingExam, upcoming_id)
    if not ue or ue.user_id != user.id:
        raise ValueError("آمادگی امتحان یافت نشد.")
    topics = [t.node_id for t in db.scalars(select(m.UpcomingExamTopic).where(
        m.UpcomingExamTopic.upcoming_exam_id == upcoming_id)).all()]

    today = date.today()
    days_left = (ue.exam_date - today).days
    cap = day_capacity(db, user, today)
    per_day_tasks = suggested_task_count(db, user, today)

    suggestions = []
    low_coverage = 0
    total_needed = 0
    missing_bank: list[str] = []

    for node_id in topics:
        stats = node_stats(db, user.id, node_id)
        title = node_full_title(db, node_id)
        if stats["total"] == 0:
            missing_bank.append(title)
            continue
        if stats["coverage"] < cfg.READINESS_LOW_COVERAGE_THRESHOLD:
            low_coverage += 1

        qs = questions_of_node(db, node_id)
        qids = [q.id for q in qs if q.answer_key is not None]
        attempted = set()
        if qids:
            attempted = {
                r[0] for r in db.execute(select(m.QuestionAttempt.question_id).where(
                    m.QuestionAttempt.user_id == user.id,
                    m.QuestionAttempt.question_id.in_(qids))).all()
            }
        unseen = [qid for qid in qids if qid not in attempted]
        review_open = db.scalars(select(m.ReviewQueue).where(
            m.ReviewQueue.user_id == user.id, m.ReviewQueue.status == "open",
            m.ReviewQueue.question_id.in_(qids or [0]))).all() if qids else []

        # ترتیب اولویت طبق سند: Coverage پایین → غلط/نزده review → دیده‌نشده
        priority = 0
        parts: list[str] = []
        if stats["coverage"] < cfg.READINESS_LOW_COVERAGE_THRESHOLD:
            priority += 60
            parts.append(f"Coverage پایین ({stats['coverage']*100:.0f}٪)")
        if review_open:
            priority += 25 + min(15, len(review_open))
            parts.append(f"{len(review_open)} غلط/نزده باز در مرور")
        if unseen:
            priority += 10
            parts.append(f"{len(unseen)} تست دیده‌نشده")
        if days_left <= cfg.READINESS_DEADLINE_BOOST_DAYS:
            priority += 15
            parts.append(f"فقط {days_left} روز تا امتحان")

        if wrong_only:   # فیلتر «فقط غلط‌ها»
            if not review_open:
                continue
            count = min(len(review_open), 15)
        else:
            count = min(15, max(5, len(review_open) + min(len(unseen), 10)))
        if count == 0:
            continue
        total_needed += count
        suggestions.append({
            "node_id": node_id,
            "title": title,
            "short_title": db.get(m.BookNode, node_id).title,
            "book_id": db.get(m.BookNode, node_id).book_id,
            "coverage": stats["coverage"],
            "accuracy": stats["accuracy"],
            "open_review": len(review_open),
            "unseen": len(unseen),
            "suggested_count": count,
            "parity": suggest_parity(db, user.id, node_id),
            "priority": priority,
            "reason": " • ".join(parts) or "مرور عمومی مبحث",
        })

    suggestions.sort(key=lambda s: s["priority"], reverse=True)
    week_capacity_tests = max(1, per_day_tasks * 7 * 8)
    overload = total_needed > week_capacity_tests

    return {
        "upcoming_exam": {
            "id": ue.id, "title": ue.title,
            "exam_date": ue.exam_date.isoformat(),
            "exam_date_jalali": jalali.to_jalali_str(ue.exam_date, with_weekday=True),
            "days_left": days_left,
        },
        "countdown_mode": 0 <= days_left <= cfg.READINESS_COUNTDOWN_DAYS,
        "topics_total": len(topics),
        "topics_low_coverage": low_coverage,
        "low_coverage_ratio": round(low_coverage / len(topics), 2) if topics else 0.0,
        "total_suggested_tests": total_needed,
        "week_capacity_tests": week_capacity_tests,
        "capacity_warning": (
            f"مجموع {total_needed} تست پیشنهادی از ظرفیت تخمینی هفته "
            f"({week_capacity_tests} تست) بیشتر است؛ اولویت را روی مباحث بالای لیست بگذار."
            if overload else None
        ),
        "missing_bank": missing_bank,
        "today_capacity": cap,
        "suggestions": suggestions,
    }


def materialize_tasks(db: Session, user: m.User, upcoming_id: int,
                      limit: int = 5) -> dict:
    """ساخت Task «آمادگی امتحان X» با deadline نزدیک تاریخ امتحان."""
    data = suggested_tasks(db, user, upcoming_id)
    ue = db.get(m.UpcomingExam, upcoming_id)
    created = 0
    for s in data["suggestions"][:limit]:
        exists = db.scalar(select(m.Task).where(
            m.Task.user_id == user.id, m.Task.node_id == s["node_id"],
            m.Task.source_type == "planner", m.Task.source_id == upcoming_id,
            m.Task.status == "pending"))
        if exists:
            continue
        book = db.get(m.Book, s["book_id"])
        db.add(m.Task(
            user_id=user.id, task_type="exam_prep",
            title=f"آمادگی امتحان {ue.title} — {s['short_title']} ({s['suggested_count']} تست)",
            subject_id=book.subject_id if book else None,
            book_id=s["book_id"], node_id=s["node_id"],
            source_type="planner", source_id=upcoming_id,
            priority=min(99, s["priority"]), quantity=s["suggested_count"],
            estimated_minutes=max(20, s["suggested_count"] * 3),
            parity=s["parity"], planned_date=date.today(), due_at=ue.exam_date,
            recommendation_reason=s["reason"], planner_version=cfg.APP_VERSION,
            evidence_json={"upcoming_exam_id": upcoming_id, "priority": s["priority"]},
        ))
        created += 1
    db.flush()
    return {"created": created}


def weekly_exam_coverage_card(db: Session, user: m.User) -> dict:
    """کارت هفتگی پوشش امتحانات پیش‌رو برای داشبورد."""
    items = []
    for ue in db.scalars(select(m.UpcomingExam).where(
            m.UpcomingExam.user_id == user.id,
            m.UpcomingExam.exam_date >= date.today()).order_by(
            m.UpcomingExam.exam_date).limit(4)).all():
        topics = db.scalars(select(m.UpcomingExamTopic).where(
            m.UpcomingExamTopic.upcoming_exam_id == ue.id)).all()
        if not topics:
            continue
        covs = [node_stats(db, user.id, t.node_id)["coverage"] for t in topics]
        items.append({
            "id": ue.id,
            "title": ue.title,
            "days_left": (ue.exam_date - date.today()).days,
            "exam_date_jalali": jalali.to_jalali_str(ue.exam_date),
            "avg_coverage": round(sum(covs) / len(covs), 3),
            "low_coverage_topics": sum(
                1 for c in covs if c < cfg.READINESS_LOW_COVERAGE_THRESHOLD),
            "topic_count": len(topics),
        })
    return {"items": items}
