"""V3.1 phase acceptance tests.

One test class per phase of `study_system_v3_1_docs/09_PHASE_PLAN_V3_1.md`, so a
phase can be reported and verified independently:

* Phase 1 — audit, additive migration, restored content parser
* Phase 2 — unified exam system + exam center
* Phase 3 — chemistry checkup coverage range
* Phase 4 — curriculum 10–12 and «plannable only with a question bank»
* Phase 5 — Jalali calendar 1405–1408
* Phase 6 — extensible study-task types
* Phase 7 — purposeful questioning wired to capacity/planner
* Phase 8 — dashboard/UX surface
"""

from __future__ import annotations

import datetime as dt
import os

from sqlalchemy import inspect, select, text

from app.db import models, seed_content
from app.db.base import get_engine
from app.domain import enums


# ---------------------------------------------------------------------------
# Phase 1 — audit / restore
# ---------------------------------------------------------------------------


def test_phase1_additive_migration_keeps_rows(tmp_path):
    """A V3 database file must upgrade in place: rows survive, columns are only added.

    The legacy file is built with the stdlib sqlite3 module (exactly what an old
    installation looks like on disk) and then opened by a fresh engine, which is the
    real upgrade path: `init_db()` creates missing tables and `sync_schema` adds the
    V3.1 columns without touching a single row.
    """
    import sqlite3

    from app.db import base as db_base
    from app.db.migrations import missing_columns, sync_schema

    legacy = tmp_path / "legacy_v3.db"
    connection = sqlite3.connect(legacy)
    connection.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(64), display_name VARCHAR(128), timezone VARCHAR(64));
        CREATE TABLE exams (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            title VARCHAR(200),
            exam_type VARCHAR(16),
            exam_date DATE
        );
        INSERT INTO users (id, username, display_name, timezone)
        VALUES (1, 'legacy', 'دانش‌آموز قدیمی', 'Asia/Tehran');
        INSERT INTO exams (id, user_id, title, exam_type, exam_date)
        VALUES (1, 1, 'امتحان نوبت اول', 'school', '2026-01-01');
        """
    )
    connection.commit()
    connection.close()

    db_base.reset_engine()
    os.environ["STUDYS459_DB_PATH"] = str(legacy)
    db_base.init_db()
    engine = db_base.get_engine()
    try:
        assert missing_columns(engine) == {}
        columns = {column["name"] for column in inspect(engine).get_columns("exams")}
        assert {"subjects", "files", "question_count", "answer_key"} <= columns
        assert sync_schema(engine) == {}, "migration must be idempotent"

        session = db_base.get_session_factory()()
        try:
            exam = session.scalars(select(models.Exam).where(models.Exam.id == 1)).first()
            assert exam is not None, "the V3 row must survive the upgrade"
            assert exam.title == "امتحان نوبت اول"
            user = session.scalars(select(models.User).where(models.User.id == 1)).first()
            assert user is not None and user.display_name == "دانش‌آموز قدیمی"
        finally:
            session.close()
    finally:
        db_base.reset_engine()


def test_phase1_chemistry_tree_and_markers():
    """The refreshed chemistry TOC must parse into a real tree (it parsed to 0 nodes before)."""
    book = seed_content.parse_chemistry(
        seed_content.os.path.join(seed_content.REPO_ROOT, seed_content.CHEMISTRY_FILE)
    )
    assert book is not None
    counts = seed_content.count_nodes(book)
    assert counts["chapters"] == 3, counts
    assert counts["leaves"] >= 80, counts
    assert len(book.markers) >= 10, "checkup/comprehensive markers must be captured"
    checkups = [marker for marker in book.markers if marker.kind == "checkup"]
    assert checkups, "chemistry has explicit «آزمون چکاپ» lines"
    assert all(marker.included_topics for marker in checkups), "a checkup always covers a segment"
    segment = checkups[0]
    assert segment.covered_from and segment.covered_to
    assert len(segment.included_topics) >= 2, "a checkup is a range, never a single topic"


def test_phase1_all_three_books_still_parse():
    books = {book.stable_key: book for book in seed_content.load_all()}
    assert set(books) == {"calculus1-neshralgo", "chemistry2-mobtakeran", "physics2-kheilisabz"}
    for key, book in books.items():
        counts = seed_content.count_nodes(book)
        assert counts["chapters"] >= 3, (key, counts)
        assert counts["leaves"] >= 20, (key, counts)
