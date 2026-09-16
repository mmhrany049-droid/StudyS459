"""
بخش «تدریس‌شده» — سند 04_TAUGHT_TOPICS.
تدریس‌شده هرگز خودکار mastery/learned نمی‌شود.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config as cfg
from .. import models as m
from ..utils import jalali
from .common import node_full_title, node_stats


def add_taught(db: Session, user: m.User, node_id: int, taught_at: date | None,
               source_type: str, source_id: int | None, notes: str) -> m.TaughtTopic:
    row = m.TaughtTopic(
        user_id=user.id, node_id=node_id, taught_at=taught_at or date.today(),
        source_type=source_type, source_id=source_id, notes=notes,
    )
    db.add(row)
    db.flush()
    return row


def _status(stats: dict) -> tuple[str, str]:
    if stats["total"] == 0:
        return "no_bank", "تدریس‌شده ولی بانک تست ندارد"
    if stats["coverage"] < cfg.TAUGHT_LOW_COVERAGE_THRESHOLD:
        return "under_practiced", "تدریس‌شده ولی کم‌تمرین"
    if stats["accuracy"] < 0.6:
        return "weak", "تدریس‌شده با ضعف"
    return "good", "تدریس‌شده و خوب"


def insights(db: Session, user: m.User) -> dict:
    rows = db.scalars(
        select(m.TaughtTopic).where(m.TaughtTopic.user_id == user.id)
        .order_by(m.TaughtTopic.taught_at.desc())
    ).all()
    seen: set[int] = set()
    items = []
    warnings: list[str] = []
    for r in rows:
        if r.node_id in seen:
            continue
        seen.add(r.node_id)
        node = db.get(m.BookNode, r.node_id)
        if not node:
            continue
        book = db.get(m.Book, node.book_id)
        stats = node_stats(db, user.id, r.node_id)
        code, label = _status(stats)
        if code == "no_bank":
            warnings.append(
                f"«{node.title}» تدریس شده ولی بانک تست ندارد؛ اول سوال/پاسخ‌نامه تعریف کن."
            )  # S10
        days_since = (date.today() - r.taught_at).days
        items.append({
            "id": r.id,
            "node_id": r.node_id,
            "title": node.title,
            "full_title": node_full_title(db, r.node_id),
            "book_title": book.title if book else "",
            "subject": book.subject.name if book else "",
            "taught_at": r.taught_at.isoformat(),
            "taught_at_jalali": jalali.to_jalali_str(r.taught_at),
            "days_since": days_since,
            "fresh": days_since <= cfg.TAUGHT_RECENT_DAYS,   # post-teach 48h
            "source_type": r.source_type,
            "notes": r.notes,
            "has_bank": stats["total"] > 0,
            "total_questions": stats["total"],
            "coverage": stats["coverage"],
            "accuracy": stats["accuracy"],
            "open_review": stats["open_review"],
            "untouched": stats["total"] - stats["attempted"],
            "status": code,
            "status_label": label,
        })

    suggestions = [
        {
            "node_id": it["node_id"],
            "title": it["full_title"],
            "reason": (
                f"تدریس‌شده {it['days_since']} روز پیش، Coverage "
                f"{it['coverage']*100:.0f}٪ — {it['untouched']} تست نزده باقی است."
            ),
            "suggested_count": min(10, max(5, it["untouched"])),
            "priority": (100 - int(it["coverage"] * 100)) + (15 if it["fresh"] else 0),
        }
        for it in items
        if it["has_bank"] and it["untouched"] > 0
        and it["coverage"] < cfg.TAUGHT_LOW_COVERAGE_THRESHOLD
    ]
    suggestions.sort(key=lambda s: s["priority"], reverse=True)

    return {
        "items": items,
        "warnings": warnings,
        "suggestions": suggestions[:10],
        "counts": {
            "total": len(items),
            "no_bank": sum(1 for i in items if i["status"] == "no_bank"),
            "under_practiced": sum(1 for i in items if i["status"] == "under_practiced"),
            "weak": sum(1 for i in items if i["status"] == "weak"),
            "good": sum(1 for i in items if i["status"] == "good"),
            "recent_48h": sum(1 for i in items if i["fresh"]),
        },
    }


def recently_taught_nodes(db: Session, user_id: int, days: int = 14) -> list[int]:
    cut = date.today() - timedelta(days=days)
    return list(db.scalars(select(m.TaughtTopic.node_id).where(
        m.TaughtTopic.user_id == user_id, m.TaughtTopic.taught_at >= cut)).all())
