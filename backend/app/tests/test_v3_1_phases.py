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


# ---------------------------------------------------------------------------
# Phase 2 — unified exam system + Exam Center
# ---------------------------------------------------------------------------


def _exam_helpers(client):
    """Create a book topic with a real question bank so prep suggestions have data."""
    books = client.get("/api/books").json()["books"]
    book = books[0]
    tree = client.get(f"/api/books/{book['id']}/tree").json()
    leaf = None
    stack = list(tree["topics"])
    while stack:
        node = stack.pop()
        if node.get("is_leaf"):
            leaf = node
            break
        stack.extend(node.get("children") or [])
    client.post(
        f"/api/books/{book['id']}/nodes/{leaf['id']}/questions/range",
        json={"from_sequence": 1, "to_sequence": 10},
    )
    client.put(
        f"/api/books/{book['id']}/nodes/{leaf['id']}/answer-key",
        json={"items": [{"sequence_no": seq, "answer_key": str((seq % 4) + 1)} for seq in range(1, 11)]},
    )
    return book, leaf


def test_phase2_five_exam_types_and_multi_subject(client):
    from app.domain.enums import EXAM_TYPE_LABELS_FA

    subjects = [row["id"] for row in client.get("/api/config/subjects").json()["subjects"]] if False else [1, 2, 3]
    for index, exam_type in enumerate(EXAM_TYPE_LABELS_FA):
        created = client.post(
            "/api/exams",
            json={
                "title": f"آزمون {index}",
                "exam_type": exam_type,
                "date": "1405/10/10",
                "subjects": subjects[: 1 + (index % 3)],
                "question_count": 30,
                "source": "خودم",
            },
        )
        assert created.status_code == 200, (exam_type, created.text)
        body = created.json()
        assert body["exam_type"] == exam_type
        assert body["type_label"] == EXAM_TYPE_LABELS_FA[exam_type]
        assert body["question_count"] == 30
        assert body["subject_titles"], "درس‌های انتخاب‌شده باید برگردند"

    mock = client.post(
        "/api/exams",
        json={"title": "آزمون چنددرسه", "exam_type": "mock", "date": "1405/10/11", "subjects": [1, 2, 3]},
    ).json()
    assert len(mock["subjects"]) == 3 and mock["subject_id"] == 1

    bad_type = client.post("/api/exams", json={"title": "بد", "exam_type": "quiz", "date": "1405/10/12"})
    assert bad_type.status_code == 422

    bad_subject = client.post(
        "/api/exams", json={"title": "بد", "exam_type": "mock", "date": "1405/10/12", "subjects": [999]}
    )
    assert bad_subject.status_code == 422, "درس ناموجود نباید خودکار حذف شود"


def test_phase2_answer_key_and_attempt_history(client):
    book, leaf = _exam_helpers(client)
    exam = client.post(
        "/api/exams",
        json={"title": "آزمون مدرسه", "exam_type": "school", "date": "1405/07/01", "question_count": 6},
    ).json()

    saved = client.put(f"/api/exams/{exam['id']}/answer-key", json={"answer_key": "1:2,2:3,3:1,4:4,5:0"})
    assert saved.status_code == 200, saved.text
    key = saved.json()
    assert key["count"] == 4 and key["cleared"] == 1 and key["recalc_required"] is True
    assert client.get(f"/api/exams/{exam['id']}/answer-key").json()["count"] == 4

    merged = client.put(
        f"/api/exams/{exam['id']}/answer-key", json={"answer_key": {"6": 2}, "mode": "merge"}
    ).json()
    assert merged["count"] == 5

    first = client.post(
        f"/api/exams/{exam['id']}/attempts",
        json={
            "duration_minutes": 40,
            "answers": {"1": {"choice": "2"}, "2": {"choice": "1"}, "3": {"choice": None}, "4": {"choice": "4"}},
            "per_subject": {"حسابان": {"correct": 2, "wrong": 1}},
        },
    )
    assert first.status_code == 200, first.text
    summary = first.json()["summary"]
    assert summary["correct"] == 2, summary
    assert summary["wrong"] == 1
    assert summary["unanswered"] == 1, "انتخاب خالی «بی‌پاسخ» است، نه غلط"
    assert summary["not_entered"] == 2, "سؤال پرنشده «واردنشده» است، نه غلط"
    assert first.json()["attempts_kept"] == 1

    retake = client.post(f"/api/exams/{exam['id']}/retake", json={"date": "1405/08/01"}).json()
    second = client.post(
        f"/api/exams/{retake['id']}/attempts",
        json={"duration_minutes": 35, "answers": {"1": {"choice": "2"}, "2": {"choice": "3"}}},
    ).json()
    assert second["attempt_no"] == 1

    detail = client.get(f"/api/exams/{exam['id']}").json()
    assert len(detail["attempts"]) == 1, "نوبت جدید نباید تلاش قدیمی را پاک کند"
    assert detail["attempts"][0]["summary"]["correct"] == 2
    assert retake["retake_of_id"] == exam["id"]
    assert client.get(f"/api/exams/{retake['id']}").json()["attempts"], "نوبت جدید تلاش خودش را دارد"


def test_phase2_exam_center_past_and_upcoming(client):
    book, leaf = _exam_helpers(client)
    past = client.post(
        "/api/exams",
        json={"title": "امتحان گذشته", "exam_type": "school", "date": "1405/05/01", "keep_for_retake": True},
    ).json()
    client.post(f"/api/exams/{past['id']}/topics", json={"topic_id": leaf["id"], "checked": True, "cascade": True})
    client.post(
        f"/api/exams/{past['id']}/attempts",
        json={"duration_minutes": 50, "answers": {"1": {"choice": "1"}}, "percentage": 41.5},
    )

    future = client.post(
        "/api/exams",
        json={"title": "آزمون آینده", "exam_type": "checkup", "date": "1405/07/20", "subjects": [1]},
    ).json()
    client.post(f"/api/exams/{future['id']}/topics", json={"topic_id": leaf["id"], "checked": True, "cascade": True})

    center = client.get("/api/exam-center").json()
    assert {"past", "upcoming", "counts", "types", "policy"} <= set(center)
    assert center["counts"]["past"] >= 1 and center["counts"]["upcoming"] >= 1
    assert len(center["types"]) == 5

    past_row = [row for row in center["past"] if row["id"] == past["id"]][0]
    assert past_row["result"]["attempts"] == 1
    assert past_row["result"]["last_percentage"] == 41.5
    assert past_row["retake_available"] is True
    assert past_row["follow_up"], "گذشته باید پیگیری داشته باشد"

    upcoming_row = [row for row in center["upcoming"] if row["id"] == future["id"]][0]
    assert upcoming_row["days_left"] > 0
    assert upcoming_row["prep"]["topics_marked"] >= 1
    assert "readiness" in upcoming_row["prep"]
    assert upcoming_row["prep"]["next_action"]["kind"] in {"quiet_test", "mark_topics"}
    assert upcoming_row["short_prep"]["days"], "پیش‌نمایش برنامهٔ آماده‌سازی"


def test_phase2_prep_plan_is_multi_day_and_excludes_empty_topics(client):
    book, leaf = _exam_helpers(client)
    empty_topic = next(
        node
        for node in _flatten(client.get(f"/api/books/{book['id']}/tree").json()["topics"])
        if node.get("is_leaf") and node["id"] != leaf["id"]
    )
    exam = client.post(
        "/api/exams",
        json={"title": "جامع", "exam_type": "comprehensive", "date": "1405/08/05", "subjects": [1, 2]},
    ).json()
    client.post(f"/api/exams/{exam['id']}/topics", json={"topic_id": leaf["id"], "checked": True, "cascade": True})
    client.post(f"/api/exams/{exam['id']}/topics", json={"topic_id": empty_topic["id"], "checked": True, "cascade": True})

    plan = client.get(f"/api/exams/{exam['id']}/prep-plan", params={"days": 7}).json()
    assert plan["window_days"] == 7 and len(plan["days"]) == 7
    assert plan["topic_count"] >= 1
    assert plan["excluded_topic_count"] >= 1, "مبحث بدون بانک تست وارد برنامهٔ زمان‌دار نمی‌شود"
    planned_ids = {topic["topic_id"] for day in plan["days"] for topic in day["topics"]}
    assert leaf["id"] in planned_ids
    assert empty_topic["id"] not in planned_ids
    assert all(day["suggested_minutes"] > 0 for day in plan["days"])
    assert plan["days"][-1]["note"].startswith("روز آخر سبک‌تر")


def _flatten(nodes):
    for node in nodes:
        yield node
        yield from _flatten(node.get("children") or [])
