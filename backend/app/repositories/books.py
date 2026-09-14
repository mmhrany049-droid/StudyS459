"""Book Engine persistence queries (spec 04 tables)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import (
    Book,
    BookImport,
    BookNode,
    Question,
    Subject,
    TestSet,
    UserBookActivation,
)


# -- subjects ----------------------------------------------------------
def get_subject(db: Session, subject_id: int) -> Subject | None:
    return db.get(Subject, subject_id)


def get_or_create_subject(
    db: Session, *, name: str, grade: int, track: str, type: str
) -> Subject:
    stmt = select(Subject).where(
        Subject.name == name, Subject.grade == grade, Subject.track == track
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing
    subject = Subject(name=name, grade=grade, track=track, subject_type=type)
    db.add(subject)
    db.flush()  # assign id; commit is the service's job
    return subject


# -- books -------------------------------------------------------------
def get_book(db: Session, book_id: int) -> Book | None:
    return db.get(Book, book_id)


def get_book_by_stable_key(db: Session, stable_key: str) -> Book | None:
    stmt = select(Book).where(Book.stable_key == stable_key)
    return db.execute(stmt).scalar_one_or_none()


def list_books(db: Session) -> list[Book]:
    return list(db.execute(select(Book).order_by(Book.id)).scalars().all())


def create_book(
    db: Session,
    *,
    stable_key: str,
    title: str,
    publisher: str,
    subject_id: int,
    grade: int,
    track: str,
    edition: str,
    config_version: int,
) -> Book:
    book = Book(
        stable_key=stable_key,
        title=title,
        publisher=publisher,
        subject_id=subject_id,
        grade=grade,
        track=track,
        edition=edition,
        config_version=config_version,
    )
    db.add(book)
    db.flush()
    return book


# -- imports -----------------------------------------------------------
def get_latest_import(db: Session, book_id: int) -> BookImport | None:
    stmt = (
        select(BookImport)
        .where(BookImport.book_id == book_id)
        .order_by(BookImport.id.desc())
    )
    return db.execute(stmt).scalars().first()


def record_import(db: Session, *, book_id: int, config_hash: str, config_version: int) -> BookImport:
    row = BookImport(book_id=book_id, config_hash=config_hash, config_version=config_version)
    db.add(row)
    db.flush()
    return row


# -- nodes / test sets / questions (reads) ------------------------------
def list_nodes_for_book(db: Session, book_id: int) -> list[BookNode]:
    stmt = (
        select(BookNode)
        .where(BookNode.book_id == book_id)
        .order_by(BookNode.order_index, BookNode.id)
    )
    return list(db.execute(stmt).scalars().all())


def get_node(db: Session, node_id: int) -> BookNode | None:
    return db.get(BookNode, node_id)


def list_children(db: Session, node_id: int) -> list[BookNode]:
    stmt = (
        select(BookNode)
        .where(BookNode.parent_id == node_id)
        .order_by(BookNode.order_index, BookNode.id)
    )
    return list(db.execute(stmt).scalars().all())


def list_test_sets_for_book(db: Session, book_id: int) -> list[TestSet]:
    stmt = select(TestSet).where(TestSet.book_id == book_id).order_by(TestSet.id)
    return list(db.execute(stmt).scalars().all())


def question_counts_by_test_set(db: Session, book_id: int) -> dict[int, int]:
    stmt = (
        select(Question.test_set_id, func.count(Question.id))
        .where(Question.book_id == book_id)
        .group_by(Question.test_set_id)
    )
    return {ts_id: count for ts_id, count in db.execute(stmt).all()}


def count_nodes(db: Session, book_id: int) -> int:
    stmt = select(func.count(BookNode.id)).where(BookNode.book_id == book_id)
    return int(db.execute(stmt).scalar() or 0)


def count_test_sets(db: Session, book_id: int) -> int:
    stmt = select(func.count(TestSet.id)).where(TestSet.book_id == book_id)
    return int(db.execute(stmt).scalar() or 0)


def count_questions(db: Session, book_id: int) -> int:
    stmt = select(func.count(Question.id)).where(Question.book_id == book_id)
    return int(db.execute(stmt).scalar() or 0)


# -- activations --------------------------------------------------------
def get_activation(db: Session, user_id: int, book_id: int) -> UserBookActivation | None:
    return db.get(UserBookActivation, (user_id, book_id))


def set_activation(db: Session, user_id: int, book_id: int, *, active: bool) -> UserBookActivation:
    """Upsert the activation row. The row is NEVER deleted (history-safe)."""
    row = get_activation(db, user_id, book_id)
    if row is None:
        row = UserBookActivation(user_id=user_id, book_id=book_id, active=active)
        db.add(row)
        db.flush()
        return row
    row.active = active
    if active:
        row.activated_at = utcnow()  # last (re)activation time
    db.flush()
    return row
