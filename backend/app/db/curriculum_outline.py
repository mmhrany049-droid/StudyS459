"""Grades ۱۰ تا ۱۲ outline (V3.1 doc 04) — additive, source-labelled.

The repository ships the *tables of contents* of three grade-11 books, and those are
parsed line by line (nothing invented). The other grades are part of the required
curriculum skeleton («درخت کامل؛ plannable فقط با تست»), so this module adds the
**subjects and the official book titles** of grades 10–12 exactly as the V3.1
curriculum document lists them:

* دهم: ریاضی، فیزیک، شیمی
* یازدهم: حسابان، هندسه، آمار، فیزیک، شیمی
* دوازدهم: حسابان، هندسه، گسسته، فیزیک، شیمی

Chapters of a book are only created from a real table-of-contents file: until such a
file exists the book keeps ``hierarchy_note`` telling the student where the chapters
will come from. Nothing is fabricated, and no existing tree is ever touched.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as db_models

# slug → (Persian name, colour, order)
SUBJECTS = [
    ("math", "ریاضی", "#6366f1", 1),
    ("calculus", "حسابان", "#6366f1", 2),
    ("geometry", "هندسه", "#8b5cf6", 3),
    ("statistics", "آمار و احتمال", "#0ea5e9", 4),
    ("discrete", "ریاضیات گسسته", "#a855f7", 5),
    ("physics", "فیزیک", "#f59e0b", 6),
    ("chemistry", "شیمی", "#14b8a6", 7),
]

# (stable_key, title, subject, grade, note)
BOOKS = [
    # دهم — رشته ریاضی
    ("math1-g10", "ریاضی ۱ (دهم)", "math", "دهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    ("physics1-g10", "فیزیک ۱ (دهم)", "physics", "دهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    ("chemistry1-g10", "شیمی ۱ (دهم)", "chemistry", "دهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    # یازدهم — رشته ریاضی (کتاب‌های موجود کاربر زیر همین پایه هستند)
    ("geometry1-g11", "هندسه ۱ (یازدهم)", "geometry", "یازدهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    ("statistics-g11", "آمار و احتمال (یازدهم)", "statistics", "یازدهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    # دوازدهم — رشته ریاضی
    ("calculus2-g12", "حسابان ۲ (دوازدهم)", "calculus", "دوازدهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    ("geometry2-g12", "هندسه ۲ (دوازدهم)", "geometry", "دوازدهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    ("geometry3-g12", "هندسه ۳ (دوازدهم)", "geometry", "دوازدهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    ("discrete-g12", "ریاضیات گسسته (دوازدهم)", "discrete", "دوازدهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    ("physics3-g12", "فیزیک ۳ (دوازدهم)", "physics", "دوازدهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
    ("chemistry3-g12", "شیمی ۳ (دوازدهم)", "chemistry", "دوازدهم", "فصل‌ها با افزودن فایل فهرست کتاب پر می‌شوند."),
]

GRADE_ORDER = {"دهم": 10, "یازدهم": 11, "دوازدهم": 12}


def _find_or_create_subject(db: Session, slug: str, name: str, color: str, order: int) -> db_models.Subject:
    subject = db.scalars(select(db_models.Subject).where(db_models.Subject.slug == slug)).first()
    if subject is None:
        subject = db_models.Subject(slug=slug, name=name, color=color, order_index=order)
        db.add(subject)
        db.flush()
    return subject


def seed_curriculum_outline(db: Session, *, grade_to_add: Optional[str] = None) -> dict:
    """Add the missing grade/subject skeleton. Existing books and trees are untouched."""
    created_books = created_subjects = 0
    for slug, name, color, order in SUBJECTS:
        existed = db.scalars(select(db_models.Subject).where(db_models.Subject.slug == slug)).first()
        _find_or_create_subject(db, slug, name, color, order)
        if existed is None:
            created_subjects += 1

    for stable_key, title, subject_slug, grade, note in BOOKS:
        if grade_to_add and grade != grade_to_add:
            continue
        exists = db.scalars(select(db_models.Book).where(db_models.Book.stable_key == stable_key)).first()
        if exists:
            continue
        subject_slug_exists = db.scalars(select(db_models.Subject).where(db_models.Subject.slug == subject_slug)).first()
        subject = subject_slug_exists or _find_or_create_subject(
            db, subject_slug, subject_slug, "#6366f1", 10 + GRADE_ORDER.get(grade, 11)
        )
        db.add(
            db_models.Book(
                stable_key=stable_key,
                title=title,
                publisher=None,
                subject_id=subject.id,
                grade=grade,
                track="ریاضی",
                hierarchy_note=note,
                config_version="v3.1",
            )
        )
        created_books += 1
    db.flush()
    return {
        "created_books": created_books,
        "created_subjects": created_subjects,
        "grades": sorted({book[3] for book in BOOKS}, key=lambda value: GRADE_ORDER.get(value, 99)),
        "note": "اسکلت پایه‌های دهم تا دوازدهم اضافه شد؛ فصل‌ها فقط از فایل فهرست واقعی ساخته می‌شوند.",
    }


def curriculum_overview(db: Session, user: Optional[db_models.User] = None) -> dict:
    """Grades → subjects → books, with the visible/plannable split of every book."""
    from ..services import curriculum as curriculum_service

    books = list(db.scalars(select(db_models.Book).order_by(db_models.Book.id)))
    grades: dict[str, list[dict]] = {}
    for book in books:
        stats = curriculum_service.book_stats(db, book.id, user)
        row = {
            "book_id": book.id,
            "stable_key": book.stable_key,
            "title": book.title,
            "subject": book.subject.name if book.subject else None,
            "publisher": book.publisher,
            "topic_count": stats["topic_count"],
            "plannable_topic_count": stats["plannable_topic_count"],
            "visible_only_topic_count": stats["visible_only_topic_count"],
            "question_count": stats["question_count"],
            "hierarchy_note": book.hierarchy_note,
            "has_tree": stats["topic_count"] > 0,
        }
        grades.setdefault(book.grade or "نامشخص", []).append(row)
    ordered = {grade: grades[grade] for grade in sorted(grades, key=lambda value: GRADE_ORDER.get(value, 99))}
    return {
        "grades": ordered,
        "grade_count": len(ordered),
        "book_count": len(books),
        "visible_only_count": sum(row["visible_only_topic_count"] for rows in ordered.values() for row in rows),
        "plannable_count": sum(row["plannable_topic_count"] for rows in ordered.values() for row in rows),
        "rule": "همه مباحث دیده می‌شوند؛ فقط مبحثی که بانک تست دارد وارد زمان‌بندی می‌شود.",
    }
