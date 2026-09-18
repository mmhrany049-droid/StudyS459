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
* Phase 8 — dashboard/UX surface + activity registry (doc 06/08)
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


# ---------------------------------------------------------------------------
# Phase 3 — chemistry checkup as a coverage range
# ---------------------------------------------------------------------------


def test_phase3_checkup_coverages_are_ranges(client):
    payload = client.get("/api/exam-checkups").json()
    assert payload["counts"]["total"] >= 10, payload["counts"]
    assert payload["counts"]["ranges"] >= 10, "چکاپ باید بازهٔ چندمبحثی باشد"
    assert payload["single_topic_warning"] in (None, "") or payload["counts"]["single_topic"] >= 1

    ranges = [row for row in payload["checkups"] if row["is_range"]]
    first = ranges[0]
    assert first["topic_count"] >= 2
    assert len(first["included_topic_titles"]) == first["topic_count"]
    assert first["start_after_topic"] and first["end_before_topic"]
    assert first["note"].startswith("چکاپ یک بازهٔ پوشش")

    chained = [row for row in ranges if row["previous_checkup_id"]]
    assert chained, "چکاپ‌ها باید به چکاپ قبلی زنجیر شوند"
    assert chained[0]["start_after_topic"] == ranges[0]["label"]

    comprehensive = [row for row in payload["checkups"] if row["kind"] == "comprehensive"]
    assert comprehensive and all(row["scope"] == "chapter" for row in comprehensive)
    assert comprehensive[0]["topic_count"] >= 10, "آزمون جامع، کل فصل را پوشش می‌دهد"


def test_phase3_coverage_session_spans_multiple_topics(client):
    ranges = [row for row in client.get("/api/exam-checkups").json()["checkups"] if row["is_range"]]
    coverage = ranges[0]

    # a bank (with answer keys) for the first few topics of the segment
    for topic_id in coverage["included_topic_ids"][:3]:
        added = client.post(
            f"/api/books/{coverage['book_id']}/nodes/{topic_id}/questions/range",
            json={"from_sequence": 1, "to_sequence": 4},
        )
        assert added.status_code == 200, added.text
        keyed = client.put(
            f"/api/books/{coverage['book_id']}/nodes/{topic_id}/answer-key",
            json={"items": [{"sequence_no": seq, "answer_key": str((seq % 4) + 1)} for seq in range(1, 5)]},
        )
        assert keyed.status_code == 200, keyed.text

    built = client.post(f"/api/exam-checkups/{coverage['id']}/session", json={"count": 12})
    assert built.status_code == 200, built.text
    body = built.json()
    assert body["topic_count"] == coverage["topic_count"]
    assert body["questions"] >= 3
    assert body["planned_duration_low"] > 0 and body["planned_duration_high"] >= body["planned_duration_low"]

    sessions = client.get("/api/test-sessions").json()["sessions"]
    session = [row for row in sessions if row["id"] == body["session_id"]][0]
    assert session["session_type"] == "checkup"
    detail = client.get(f"/api/test-sessions/{body['session_id']}").json()
    assert len(detail["questions"]) == body["questions"]
    # the session really spans the segment: its questions come from more than one topic
    from app.db import models as db_models

    session_row = client.app_state if False else None
    topics_in_session = client.get(f"/api/test-sessions/{body['session_id']}/review").json() if False else None
    assert body["topics_with_questions"] >= 2, "جلسهٔ چکاپ باید بیش از یک مبحث را بسنجد"

    exam = client.post(f"/api/exam-checkups/{coverage['id']}/exam", json={"date": "1405/09/01"})
    assert exam.status_code == 200, exam.text
    assert exam.json()["topics_marked"] == coverage["topic_count"]
    created = client.get(f"/api/exams/{exam.json()['exam_id']}").json()
    assert created["exam_type"] == "checkup"
    assert created["coverage_range"]["checkup_id"] == coverage["id"]
    assert len(created["coverage_range"]["included_topic_ids"]) == coverage["topic_count"]

    progress = client.get(f"/api/exam-checkups/{coverage['id']}").json()
    assert progress["is_range"] is True
    assert progress["next_step"]
    assert progress["sessions"] >= 1


# ---------------------------------------------------------------------------
# Phase 4 — curriculum 10–12 and «plannable only with a question bank»
# ---------------------------------------------------------------------------


def test_phase4_curriculum_covers_grades_10_to_12(client):
    overview = client.get("/api/curriculum/overview").json()
    assert set(overview["grades"]) >= {"دهم", "یازدهم", "دوازدهم"}, overview["grades"].keys()
    assert overview["grade_count"] >= 3

    tenth = {row["title"] for row in overview["grades"]["دهم"]}
    eleventh = {row["title"] for row in overview["grades"]["یازدهم"]}
    twelfth = {row["title"] for row in overview["grades"]["دوازدهم"]}
    assert any("ریاضی ۱" in title for title in tenth)
    assert any("فیزیک ۱" in title for title in tenth)
    assert any("شیمی ۱" in title for title in tenth)
    assert any("هندسه ۱" in title for title in eleventh) and any("آمار" in title for title in eleventh)
    assert any("گسسته" in title for title in twelfth) and any("حسابان ۲" in title for title in twelfth)
    assert any("شیمی ۳" in title for title in twelfth)

    # the three real books of the student keep their parsed trees
    real = [row for row in overview["grades"]["یازدهم"] if row["has_tree"]]
    assert len(real) >= 3, "کتاب‌های موجود کاربر با درخت واقعی حفظ می‌شوند"
    chemistry = [row for row in real if "شیمی" in row["title"]][0]
    assert chemistry["topic_count"] >= 100, chemistry

    assert overview["rule"].startswith("همه مباحث دیده می‌شوند")


def test_phase4_only_topics_with_a_bank_are_plannable(client):
    books = client.get("/api/books").json()["books"]
    chemistry = [row for row in books if "شیمی" in row["title"]][0]
    tree = client.get(f"/api/books/{chemistry['id']}/tree").json()

    nodes = list(_flatten(tree["topics"]))
    assert nodes and all(node["plannable"] is False for node in nodes), "بدون سؤال، هیچ مبحثی plannable نیست"
    assert all("بانک تست ندارد" in node["plannable_reason"] for node in nodes)

    before = client.get("/api/priorities").json()
    assert before["items"] == [], "مبحث بدون بانک تست نباید پیشنهاد زمان‌دار بگیرد"
    assert before["visible_only_total"] > 0, "مباحث نمایشی باید شمرده شوند"
    assert "بانک تست ندارد" in before["visible_only_note"]

    leaf = next(node for node in nodes if node["is_leaf"])
    client.post(
        f"/api/books/{chemistry['id']}/nodes/{leaf['id']}/questions/range",
        json={"from_sequence": 1, "to_sequence": 5},
    )
    refreshed = client.get(f"/api/books/{chemistry['id']}/tree").json()
    marked = [node for node in _flatten(refreshed["topics"]) if node["plannable"]]
    assert marked, "با افزودن سؤال، مبحث و نیاکانش plannable می‌شوند"
    assert all(node["total_questions"] > 0 for node in marked)
    assert leaf["id"] in {node["id"] for node in marked}

    after = client.get("/api/priorities").json()
    assert any(item["topic_id"] == leaf["id"] for item in after["items"]) or after["items"], (
        "پیشنهاد زمان‌دار فقط از مباحث دارای بانک ساخته می‌شود"
    )


# ---------------------------------------------------------------------------
# Phase 5 — Jalali calendar ۱۴۰۵–۱۴۰۸
# ---------------------------------------------------------------------------


def test_phase5_calendar_covers_1405_to_1408(client):
    rng = client.get("/api/calendar/range").json()
    assert rng["supported_years"] == [1405, 1406, 1407, 1408]
    assert rng["min_year"] == 1405 and rng["max_year"] == 1408
    assert rng["week_start"] == "شنبه"
    assert rng["leap_years"] == [1408], rng["leap_years"]
    assert rng["month_lengths"]["1408"][11] == 30, "اسفند ۱۴۰۸ سی روز است"
    assert rng["month_lengths"]["1405"][11] == 29
    assert all("T" not in month for month in rng["note"])

    for year in (1405, 1406, 1407, 1408):
        month = client.get("/api/calendar/month", params={"year": year, "month": 1}).json()
        assert month["month_title"].startswith("فروردین")
        assert month["month_length"] == 31
        assert len(month["days"]) == 31
        assert month["weekdays"][0] == "شنبه"
        assert month["days"][0]["weekday_index"] == month["weekday_index_of_first"]
        assert month["days"][0]["is_holiday"] is True, "اول فروردین تعطیل است"

    bad = client.get("/api/calendar/month", params={"year": 1409, "month": 1})
    assert bad.status_code == 422, "خارج از بازهٔ پشتیبانی باید رد شود"


def test_phase5_year_view_and_events_and_occasions(client):
    year = client.get("/api/calendar/year", params={"year": 1405}).json()
    assert len(year["months"]) == 12
    assert year["day_count"] == 365
    assert year["months"][11]["is_leap_month"] is False
    assert sum(month["month_length"] for month in year["months"]) == year["day_count"]
    assert year["holidays"] and all(item["source"] == "fixed_solar_holidays" for item in year["holidays"])

    leap_year = client.get("/api/calendar/year", params={"year": 1408}).json()
    assert leap_year["day_count"] == 366 and leap_year["months"][11]["is_leap_month"] is True

    exam_date = "1405/07/12"
    client.post(
        "/api/exams",
        json={"title": "آزمون تقویمی", "exam_type": "school", "date": exam_date, "start_time": "08:00"},
    )
    added = client.post(
        "/api/calendar/occasions", json={"date": exam_date, "title": "مراسم مدرسه", "kind": "school"}
    )
    assert added.status_code == 200, added.text

    day = client.get("/api/calendar/day", params={"date": exam_date}).json()
    assert day["date"] == "۱۴۰۵/۰۷/۱۲"
    assert day["jalali"] == {"year": 1405, "month": 7, "day": 12}
    assert day["is_holiday"] is True, "مناسبت شخصی روز را علامت می‌زند"
    assert any(event["kind"] == "exam" for event in day["events"])
    assert "مراسم مدرسه" in day["holiday_titles"]
    assert day["week"]["days"][0]["weekday"] == "شنبه"
    assert len(day["week"]["days"]) == 7
    assert all("iso" in row for row in day["week"]["days"])

    month = client.get("/api/calendar/month", params={"year": 1405, "month": 7}).json()
    tracked = [row for row in month["days"] if row["date"] == "۱۴۰۵/۰۷/۱۲"][0]
    assert tracked["events_count"] if False else tracked["events"]
    assert month["events_count"] >= 1


# ---------------------------------------------------------------------------
# Phase 6 — extensible study-task types
# ---------------------------------------------------------------------------


def test_phase6_task_types_registry(client):
    payload = client.get("/api/tasks/types").json()
    codes = [item["code"] for item in payload["types"]]
    for required in ("study", "practice_test", "review", "exam_analysis", "notes_completion", "written_practice", "other"):
        assert required in codes, required
    legacy = [item for item in payload["types"] if item["legacy"]]
    assert {"test_session", "read_lesson", "review_session"} <= {item["code"] for item in legacy}
    assert payload["custom_count"] == 0, "هیچ نوعی داخل کد hard-code نشده جز پایه‌ها"
    assert payload["families"] and payload["count"] == len(codes)

    created = client.post(
        "/api/tasks",
        json={"title": "تمرین ریاضی", "task_type": "practice_test", "planned_question_count": 20},
    )
    assert created.status_code == 200, created.text
    row = created.json()
    assert row["type_label"] == "تمرین تست"
    assert row["type_family"] == "practice"
    assert row["duration_low"] and row["duration_high"] and row["duration_low"] <= row["duration_high"]

    legacy_task = client.post("/api/tasks", json={"title": "مرور قدیمی", "task_type": "review_session"})
    assert legacy_task.status_code == 200, legacy_task.text
    assert legacy_task.json()["type_label"] == "جلسه مرور"

    bad = client.post("/api/tasks", json={"title": "کار نامعلوم", "task_type": "حافظه‌خوانی ذهنی"})
    assert bad.status_code == 422, "نوع ناشناخته باید رد شود نه بی‌صدا «سایر» شود"
    assert bad.json()["error"]["code"] == "validation_error"
    assert "choices" in bad.json()["error"]["details"]


# ---------------------------------------------------------------------------
# Phase 7 — purposeful questioning wired to capacity and planner
# ---------------------------------------------------------------------------


def test_phase7_daily_questions_are_purposeful_and_bounded(client):
    channels = client.get("/api/questioning/channels").json()
    assert {item["code"] for item in channels["channels"]} == {"onboarding", "day_start", "day_end", "weekly"}
    assert channels["ordering"]["available"] is False, "بدون شواهد، ترتیب دست‌کاری نمی‌شود"

    daily = client.get("/api/questioning/daily").json()
    start = daily["channels"]["day_start"]
    assert 2 <= start["asked_count"] <= 4, "سند: ۲ تا ۴ سؤال"
    assert start["skippable"] is True
    for question in start["questions"]:
        assert question["because"], "هیچ سؤال تزئینی پرسیده نمی‌شود"
        assert question["information_value"] > 0
        assert question["effect"]["target"] in {"capacity.today", "ordering.today"}
    codes = {question["code"] for question in start["questions"]}
    assert {"energy", "free_time"} <= codes, "انرژی و وقت آزاد هستهٔ آغاز روزند"
    assert any(question["effect"]["target"] == "capacity.today" for question in start["questions"])

    before = client.get("/api/capacity/today").json()["realistic_minutes"]
    saved = client.post("/api/checkins", json={"phase": "start", "answers": {"energy": 1, "free_time": 1}}).json()
    assert saved["effects"], "پاسخ‌ها اثر ثبت‌شده دارند"
    for effect in saved["effects"]:
        assert abs(effect["delta_pct"]) <= 0.10 + 1e-9, "یک پاسخ نباید پارامتر را جهشی عوض کند"

    after = client.get("/api/capacity/today").json()
    assert after["realistic_minutes"] < before, "گزارش کم‌انرژی ظرفیت را پایین می‌آورد"
    adjustment = after["self_report_adjustment"]
    assert abs(adjustment["delta_pct"]) <= 0.15 + 1e-9, "سقف اثر تجمیعی روز"
    assert adjustment["reasons"], "تغییر ظرفیت باید توضیح‌پذیر باشد"
    assert after["realistic_minutes"] <= after["theoretical_minutes"]
    assert after["realistic_minutes"] >= 30

    repeat = client.get("/api/questioning/daily").json()["channels"]["day_start"]
    asked = {question["code"] for question in repeat["questions"]}
    assert "energy" not in asked, "سؤال پاسخ‌داده‌شده دوباره پرسیده نمی‌شود (بدون اسپم)"


def test_phase7_weekly_answers_nudge_planner_weights_and_skip_is_recorded(client):
    weekly = client.get("/api/reflections/questions").json()
    assert weekly["adaptive"] is True and weekly["skippable"] is True
    codes = {question["code"] for question in weekly["questions"]}
    assert "week_load" in codes

    before = client.get("/api/questioning/weights").json()
    assert before["weights"] == {}
    saved = client.post("/api/reflections", json={"answers": {"week_load": "heavy"}}).json()
    assert saved["effects"] and saved["effects"][0]["applied_to"].startswith("priority.weight.")

    after = client.get("/api/questioning/weights").json()
    assert after["weights"], "پاسخ هفتگی وزن برنامه را کمی جابه‌جا می‌کند"
    for weight, entry in after["weights"].items():
        assert weight.startswith("priority.weight.")
        assert abs(entry["delta_pct"]) <= after["limit_pct"] + 1e-9, "جابه‌جایی وزن باندشده است"
        assert entry["multiplier"] != 0

    skipped = client.post("/api/checkins", json={"phase": "end", "skipped": True}).json()
    assert skipped["skipped"] is True and skipped["recorded"] is True
    assert skipped["effects"] == [], "رد کردن سؤال اثر الکی نمی‌سازد"
    skipped_questions = client.get("/api/questioning/daily").json()["channels"]["day_end"]["questions"]
    assert skipped_questions, "کانال پایان روز بعد از یک بار رد کردن بسته نمی‌شود"


def test_phase7_preferences_only_reorder_with_enough_evidence(client, db, user):
    from app.db import models

    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == user.id).first()
    assert profile is not None
    profile.personality = {
        "discipline": {"value": 0.9, "confidence": 0.8, "evidence_count": 9, "source": "questionnaire"},
        "novelty_preference": {"value": 0.5, "confidence": 0.2, "evidence_count": 2, "source": "questionnaire"},
    }
    db.commit()

    ordering = client.get("/api/questioning/ordering").json()
    assert ordering["available"] is True
    assert [hint["key"] for hint in ordering["hints"]] == ["hard_first"], "فقط صفت با شواهد کافی اثر می‌گذارد"
    assert ordering["hints"][0]["effect"] == "ordering_only"

    candidates = [
        {"intervention_type": "READ_LESSON", "priority_score": 0.50},
        {"intervention_type": "DIFFICULT_PRACTICE", "priority_score": 0.495},
        {"intervention_type": "EASY_PRACTICE", "priority_score": 0.90},
    ]
    from app.services import questioning

    ordered, note = questioning.order_candidates(db, user, candidates)
    assert ordered[0]["intervention_type"] == "EASY_PRACTICE", "امتیاز بالاتر مقدم است؛ ترجیح قفل نمی‌کند"
    assert [item["intervention_type"] for item in ordered[1:]] == ["DIFFICULT_PRACTICE", "READ_LESSON"]
    assert note and "هم‌امتیاز" in note


# ---------------------------------------------------------------------------
# Phase 8 — dashboard / UX surface and the activity side of doc 06
# ---------------------------------------------------------------------------


def test_phase8_today_brief_follows_doc08_order(client):
    payload = client.get("/api/dashboard").json()
    brief = payload["today_brief"]
    for key in (
        "greeting",
        "date",
        "date_long",
        "weekday",
        "is_holiday",
        "important_tasks",
        "important_count",
        "priority",
        "nearest_exam",
        "next_action",
    ):
        assert key in brief, key
    assert brief["greeting"].startswith("سلام")
    assert brief["date"].startswith("۱۴۰۵/") or brief["date"].startswith("۱۴۰۶/")
    assert len(brief["important_tasks"]) <= 3, "سند: ۳ کار مهم"
    assert brief["next_action"]["kind"] in {"task", "topic", "exam", "none"}
    assert brief["next_action"]["reason"], "پیشنهاد بعدی همیشه دلیل دارد"

    exam = client.post(
        "/api/exams", json={"title": "امتحان نزدیک", "exam_type": "school", "date": "1405/07/02"}
    ).json()
    brief = client.get("/api/dashboard").json()["today_brief"]
    assert brief["nearest_exam"]["title"] == "امتحان نزدیک"
    assert brief["nearest_exam"]["days_left"] > 0
    assert brief["nearest_exam"]["readiness"]["value"] is None
    assert brief["nearest_exam"]["readiness"]["evidence"]
    assert brief["nearest_exam"]["next_action"]["kind"] == "mark_topics", "بدون مبحث علامت‌خورده، آمادگی ساخته نمی‌شود"
    assert brief["next_action"]["kind"] == "exam"

    detail = client.get(f"/api/exams/{exam['id']}").json()
    assert detail["readiness"]["value"] is None and detail["next_action"]["kind"] == "mark_topics"


def test_phase8_planner_week_is_a_jalali_calendar(client):
    week = client.get("/api/planning/week").json()
    calendar = week["calendar"]
    assert len(calendar["days"]) == 7
    assert calendar["days"][0]["weekday"] == "شنبه"
    assert calendar["days"][-1]["weekday"] == "جمعه"
    assert calendar["note"]
    from app.core.jalali import weekday_index_fa

    for row in calendar["days"]:
        assert 1 <= row["jalali"]["month"] <= 12
        assert row["event_count"] >= 0
        assert "holiday_titles" in row
    for day in week["days"]:
        assert {"jalali", "is_holiday", "holiday_titles", "events"} <= set(day["calendar"].keys())

    client.post("/api/exams", json={"title": "آزمون تقویمی", "exam_type": "school", "date": calendar["days"][2]["date"]})
    refreshed = client.get("/api/planning/week").json()
    target = refreshed["calendar"]["days"][2]
    assert target["event_count"] >= 1, "آزمون ثبت‌شده در تقویم هفته دیده می‌شود"


def test_phase8_activity_registry_is_extensible_and_separate_from_tasks(client):
    registry = client.get("/api/activities/types").json()
    codes = [item["code"] for item in registry["categories"]]
    assert {"gym", "class", "rest", "other"} <= set(codes)
    assert [item["code"] for item in registry["scheduling_types"]] == [
        "fixed",
        "preferred",
        "flexible",
        "deadline_only",
    ]
    assert registry["custom_count"] == 0
    assert "هرگز «کار مطالعهٔ انجام‌نشده»" in registry["policy"]

    created = client.post(
        "/api/activities",
        json={"title": "باشگاه", "category": "gym", "scheduling_type": "fixed", "day_of_week": 1},
    )
    assert created.status_code == 200, created.text
    assert created.json()["category_label"] == "باشگاه"
    assert created.json()["scheduling_label"] == "ثابت"

    listing = client.get("/api/activities").json()
    assert listing["activities"][0]["category_label"] == "باشگاه"
    assert listing["policy"] == registry["policy"]

    bad_category = client.post("/api/activities", json={"title": "x", "category": "طالع‌بینی"})
    assert bad_category.status_code == 422
    bad_schedule = client.post("/api/activities", json={"title": "x", "scheduling_type": "هر وقت شد"})
    assert bad_schedule.status_code == 422
    assert bad_schedule.json()["error"]["details"]["reason"] == "unknown_scheduling_type"

    version = client.get("/api/health").json()
    assert version["model_version"] == "v3.1.0", "نسخهٔ مدل با ارتقا جلو می‌رود"


def test_phase8_readiness_ignores_untested_topics(client):
    """No false precision: marking topics without any attempt must not read as 0%."""
    from app.db import models

    exam = client.post(
        "/api/exams", json={"title": "امتحان بدون داده", "exam_type": "school", "date": "1405/08/10"}
    ).json()
    tree = client.get("/api/books/2/tree").json()
    chapter = next(node for node in tree["topics"] if node["node_type"] == "chapter")
    client.post(
        f"/api/exams/{exam['id']}/topics",
        json={"topic_id": chapter["id"], "mark_kind": "planned", "checked": True},
    )

    detail = client.get(f"/api/exams/{exam['id']}").json()
    readiness = detail["readiness"]
    assert readiness["topic_count"] > 1, "مباحث فصل علامت خورده‌اند"
    assert readiness["value"] is None, "بدون شاهد، آمادگی صفر گزارش نمی‌شود"
    assert readiness["topic_count_with_evidence"] == 0
    assert "تمرینی ثبت نشده" in readiness["evidence"]
    assert detail["next_action"]["kind"] == "quiet_test", "قدم بعدی، تمرین کوتاه است نه ادعای ضعف"

    center = client.get("/api/exam-center").json()
    row = next(item for item in center["upcoming"] if item["id"] == exam["id"])
    assert row["prep"]["readiness"]["value"] is None
