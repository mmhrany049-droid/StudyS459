"""Seed: subjects, books/nodes, کلاس‌های تقویتی پیش‌فرض (سند 03_DEFAULT_CLASSES), badges."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..services.rewards import ensure_badges
from .books_data import BOOKS

DEFAULT_CLASSES = [
    ("کلاس تقویتی حسابان", "حسابان"),
    ("کلاس تقویتی شیمی", "شیمی"),
    ("کلاس تقویتی فیزیک", "فیزیک"),
]
LEAFY = {"leaf", "concours", "checkup", "comprehensive", "chapter_exam"}


def _insert_tree(db: Session, book: m.Book, nodes: list, parent_id: int | None,
                 depth: int = 0) -> None:
    for idx, (title, node_type, children) in enumerate(nodes):
        node = m.BookNode(
            book_id=book.id, parent_id=parent_id, node_type=node_type,
            title=title, order_index=idx,
            metadata_json={"depth": depth, "test_type":
                           node_type if node_type in
                           ("concours", "checkup", "comprehensive", "chapter_exam")
                           else "normal"},
        )
        db.add(node)
        db.flush()
        if children:
            _insert_tree(db, book, children, node.id, depth + 1)
        elif node_type in LEAFY:
            # هر leaf یک Test Set خالی می‌گیرد؛ سوال‌ها را کاربر در بانک تست می‌سازد.
            db.add(m.TestSet(
                book_id=book.id, node_id=node.id, title=title,
                test_type=node.metadata_json["test_type"],
            ))
    db.flush()


def seed_books(db: Session) -> dict:
    created_books = 0
    for spec in BOOKS:
        subject = db.scalar(select(m.Subject).where(m.Subject.name == spec["subject"]))
        if not subject:
            subject = m.Subject(name=spec["subject"], color=spec["color"])
            db.add(subject)
            db.flush()
        book = db.scalar(select(m.Book).where(m.Book.stable_key == spec["stable_key"]))
        if book:
            continue
        book = m.Book(
            stable_key=spec["stable_key"], title=spec["title"],
            publisher=spec["publisher"], subject_id=subject.id,
            has_difficulty_levels=spec["has_difficulty_levels"],
        )
        db.add(book)
        db.flush()
        _insert_tree(db, book, spec["tree"], None)
        created_books += 1
    db.commit()
    return {"books_created": created_books}


def seed_default_classes(db: Session, user: m.User) -> dict:
    created = 0
    for title, subject_name in DEFAULT_CLASSES:
        exists = db.scalar(select(m.Schedule).where(
            m.Schedule.user_id == user.id, m.Schedule.title == title))
        if exists:
            continue
        subject = db.scalar(select(m.Subject).where(m.Subject.name == subject_name))
        db.add(m.Schedule(
            user_id=user.id, schedule_type="external_class", title=title,
            subject_id=subject.id if subject else None,
            day_of_week=None, recurring=True, source="default_seed_v2",
        ))
        created += 1
    db.commit()
    return {"classes_created": created}


def bootstrap(db: Session) -> dict:
    ensure_badges(db)
    result = seed_books(db)
    user = db.scalars(select(m.User).limit(1)).first()
    if not user:
        user = m.User(username="me", display_name="کاربر SS459")
        db.add(user)
        db.flush()
        db.add(m.UserProfile(user_id=user.id))
        db.commit()
    if (db.scalar(select(func.count(m.Schedule.id)).where(
            m.Schedule.user_id == user.id)) or 0) == 0:
        result |= seed_default_classes(db, user)
    db.commit()
    return result
