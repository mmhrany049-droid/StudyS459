"""Frontend↔API contract: the exact fields the UI reads must exist in the payloads.

The UI is written against these shapes, so a silent rename here would break a page
without any engine test noticing. Kept deliberately explicit (no auto-generated
schema diffing) so each line documents a real screen.
"""

from __future__ import annotations


def _get(client, path, **params):
    response = client.get(f"/api{path}", params=params or None)
    assert response.status_code == 200, f"{path} -> {response.status_code} {response.text[:200]}"
    return response.json()


def _post(client, path, payload=None):
    response = client.post(f"/api{path}", json=payload if payload is not None else {})
    assert response.status_code == 200, f"{path} -> {response.status_code} {response.text[:200]}"
    return response.json()


def _seed_screen_data(client):
    _post(client, "/bootstrap")
    _post(client, "/topics/1/taught", {"taught": True, "cascade": True})
    _post(client, "/books/1/nodes/3/questions/range", {"from_sequence": 1, "to_sequence": 12})
    client.put(
        "/api/books/1/nodes/3/answer-key",
        json={"items": [{"sequence_no": i, "answer_key": str((i % 4) + 1)} for i in range(1, 13)]},
    )
    session = _post(client, "/test-sessions", {"book_id": 1, "topic_id": 3, "count": 6, "start_now": True})
    entries = [
        {"question_id": q["question_id"], "state": "ANSWERED", "selected_choice": "1"}
        for q in session["questions"][:3]
    ] + [
        {"question_id": q["question_id"], "state": "NOT_ENTERED"} for q in session["questions"][3:]
    ]
    _post(client, f"/test-sessions/{session['id']}/submit", {"entries": entries, "actual_duration_minutes": 20})
    _post(client, "/review/build")
    _post(client, "/exams", {"title": "امتحان تست", "exam_type": "school", "date": "1405/09/01"})
    _post(client, "/goals", {"title": "هدف تست", "goal_type": "three_month", "target_date": "1405/12/01", "book_ids": [1]})
    _post(client, "/planning/sessions")
    _post(client, "/planning/sessions/1/generate")
    experiment = _post(client, "/experiments", {"template_key": "warmup_easy_before_hard", "title": "آزمایش تست"})
    return experiment


def test_dashboard_contract(client):
    _seed_screen_data(client)
    dashboard = _get(client, "/dashboard")
    assert set(["today", "what_matters_now", "what_next", "why"]).issubset(dashboard)
    assert {"date", "date_long", "weekday"}.issubset(dashboard["today"])
    priorities = dashboard["what_matters_now"]["priorities"]
    assert priorities, "the dashboard must show priorities once evidence exists"
    priority = priorities[0]
    for key in ("topic_id", "topic_title", "score", "confidence", "top_reasons", "why"):
        assert key in priority, f"dashboard priority is missing {key}"
    assert set(["what", "why", "evidence", "what_can_i_change"]).issubset(priority["why"])
    assert "review" in dashboard["what_matters_now"]
    assert set(["tasks", "over_capacity", "capacity"]).issubset(dashboard["what_next"])
    for task in dashboard["what_next"]["tasks"]:
        assert {"id", "title", "status", "duration_low", "duration_high", "duration_label", "manual_override"}.issubset(task)
    assert set(["suggestions", "quiet"]).issubset(dashboard["why"])
    assert set(["summary", "overload", "what_can_i_change"]).issubset(dashboard["midweek"]) or dashboard["midweek"]
    assert set(["theoretical_minutes_today", "realistic_minutes_today", "explanation"]).issubset(dashboard["time"])
    assert set(["attempts", "answered", "correct", "wrong", "unanswered", "not_entered", "coverage", "accuracy"]).issubset(
        dashboard["learning"]
    )
    assert set(["available", "message"]).issubset(dashboard["habits"])
    assert set(["open", "due_today", "critical"]).issubset(dashboard["what_matters_now"]["review"])


def test_today_and_curriculum_contract(client):
    _seed_screen_data(client)
    tasks = _get(client, "/tasks")
    assert set(["date", "date_long", "tasks", "capacity", "over_capacity"]).issubset(tasks)
    if tasks["tasks"]:
        task = tasks["tasks"][0]
        assert {"id", "title", "status", "task_type", "duration_label", "override_reason", "manual_override"}.issubset(task)

    books = _get(client, "/books")["books"]
    assert books and set(["id", "title", "topic_count", "stats"]).issubset(books[0])
    assert set(["topic_count", "question_count", "questions_with_answer_key", "taught_topics"]).issubset(books[0]["stats"])

    tree = _get(client, "/books/1/tree")
    assert set(["book", "topics", "stats"]).issubset(tree)
    node = tree["topics"][0]
    assert {
        "id",
        "title",
        "node_type",
        "is_leaf",
        "taught_state",
        "taught",
        "direct_question_count",
        "total_questions",
        "children",
    }.issubset(node)
    assert set(["topic_count", "question_count", "taught_topics"]).issubset(tree["stats"])


def test_question_bank_and_response_sheet_contract(client):
    _seed_screen_data(client)
    listing = _get(client, "/books/1/nodes/3/questions", limit=3)
    assert set(["total", "items", "summary"]).issubset(listing)
    assert set(["total", "with_answer_key", "without_answer_key"]).issubset(listing["summary"])
    row = listing["items"][0]
    assert {"id", "sequence_no", "difficulty_level", "answer_key", "answer_key_version", "has_answer_key"}.issubset(row)

    session = _post(client, "/test-sessions", {"book_id": 1, "topic_id": 3, "count": 4, "start_now": True})
    assert {"id", "questions", "planned_duration_label", "states_summary"}.issubset(session)
    assert {"question_id", "sequence_no"}.issubset(session["questions"][0])
    payload = _get(client, f"/test-sessions/{session['id']}")
    assert {"questions", "response_sheet_id", "planned_duration_low", "planned_duration_high"}.issubset(payload)
    result = _post(
        client,
        f"/test-sessions/{session['id']}/submit",
        {
            "entries": [
                {"question_id": session["questions"][0]["question_id"], "state": "ANSWERED", "selected_choice": "1"},
                {"question_id": session["questions"][1]["question_id"], "state": "UNANSWERED"},
                {"question_id": session["questions"][2]["question_id"], "state": "NOT_ENTERED"},
            ],
            "actual_duration_minutes": 12,
        },
    )
    for key in (
        "session_id",
        "status",
        "total",
        "correct",
        "wrong",
        "unanswered",
        "not_entered",
        "not_evaluable",
        "accuracy",
        "duration_minutes",
        "planned_duration_low",
        "planned_duration_high",
        "average_seconds_per_question",
        "topic_breakdown",
        "rewards",
        "pending_correction",
        "missing_answer_keys",
        "invariant_ok",
    ):
        assert key in result, f"submit payload is missing {key}"
    assert {"coins", "events", "streak", "badges"}.issubset(result["rewards"])
    assert "not_entered" in result["topic_breakdown"][0]


def test_import_planner_review_exam_goal_lab_contract(client):
    experiment = _seed_screen_data(client)
    sheet = _get(client, "/attempts/import-sheet", book_id=1)
    assert set(["book", "chapters", "total_questions", "instructions"]).issubset(sheet)
    chapter = sheet["chapters"][0]
    assert set(["chapter_id", "chapter_title", "question_count", "groups"]).issubset(chapter)
    group = chapter["groups"][0]
    assert set(["topic_id", "topic_title", "questions"]).issubset(group)
    assert set(["question_id", "sequence_no", "has_answer_key", "previous_state"]).issubset(group["questions"][0])
    summary = _get(client, "/attempts/import-summary")
    assert set(["sessions", "attempts", "not_entered", "last_import_dates", "note"]).issubset(summary)

    planning = _get(client, "/planning/current")
    assert set(["id", "status", "stages", "priority_suggestions", "questions", "user_decisions", "explanation"]).issubset(planning)
    if planning["priority_suggestions"]:
        suggestion = planning["priority_suggestions"][0]
        assert {"topic_id", "topic_title", "score", "short_reason", "suggested_intervention"}.issubset(suggestion)
    if planning["questions"]:
        assert {"id", "code", "text", "options", "because", "information_value", "answered", "skipped"}.issubset(
            planning["questions"][0]
        )
    week = _get(client, "/planning/week")
    assert set(["days", "capacity", "midweek", "week_label"]).issubset(week)
    day = week["days"][0]
    assert {"date", "date_long", "tasks", "capacity", "over_capacity"}.issubset(day)
    assert {"realistic_minutes", "theoretical_minutes", "planned_minutes"}.issubset(day["capacity"])
    assert {"progress", "threshold", "warning"}.issubset(week["midweek"])

    queue = _get(client, "/review/queue")
    assert set(["stats", "items"]).issubset(queue)
    assert {"open", "due_today", "critical"}.issubset(queue["stats"])
    if queue["items"]:
        item = queue["items"][0]
        assert {"id", "question_id", "sequence_no", "topic_title", "reason", "priority", "scheduled_for"}.issubset(item)
    built = _post(client, "/review/build")
    assert set(["items", "message", "cluster_size", "anchor_topic_id"]).issubset(built)

    exam = _get(client, "/exams")
    assert set(["exams", "today", "note"]).issubset(exam)
    if exam["exams"]:
        row = exam["exams"][0]
        assert {"id", "title", "exam_type", "date", "date_long", "days_left", "keep_for_retake", "percentage"}.issubset(row)
    calendar = _get(client, "/exams/calendar")
    assert set(["from", "to", "exams"]).issubset(calendar)
    assert set(["mocks", "policy"]).issubset(_get(client, "/mocks/retake-list"))
    assert set(["suggestions", "policy"]).issubset(_get(client, "/mocks/quiet-suggestions"))

    goals = _get(client, "/goals")["goals"]
    assert goals
    goal = goals[0]
    assert {"id", "title", "goal_type", "target_date", "days_left", "scope_topic_count", "progress", "notes"}.issubset(goal)
    assert {"metrics", "ratio", "deviation"}.issubset(goal["progress"])
    planned = _post(client, f"/goals/{goal['id']}/plan-week")
    assert set(["created", "note"]).issubset(planned)

    weaknesses = _get(client, "/analytics/weaknesses", limit=5)["items"]
    if weaknesses:
        assert {
            "topic_id",
            "topic_title",
            "diagnosis",
            "coverage",
            "accuracy",
            "confidence",
            "uncertainty",
            "retention",
            "repeated_error_signal",
            "why",
            "suggested_action",
        }.issubset(weaknesses[0])
    trends = _get(client, "/analytics/trends", days=14)
    assert set(["from", "to", "series", "summary", "note"]).issubset(trends)
    assert {"date", "weekday", "attempts", "correct", "wrong", "unanswered", "accuracy"}.issubset(trends["series"][0])

    experiments = _get(client, "/experiments")
    assert set(["experiments", "templates", "policy"]).issubset(experiments)
    if experiments["experiments"]:
        assert {"id", "title", "hypothesis", "metric", "status"}.issubset(experiments["experiments"][0])
    template = experiments["templates"][0]
    assert {"key", "title", "hypothesis", "metric", "metric_direction", "intervention", "control"}.issubset(template)

    analysis = _get(client, f"/experiments/{experiment['id']}/analysis")
    assert set(
        ["experiment_id", "metric", "n_intervention", "n_control", "min_required", "conclusion", "confidence", "interpretation"]
    ).issubset(analysis)

    integrity = _get(client, "/integrity/report")
    assert set(["ok", "issues", "raw_data_untouched", "note"]).issubset(integrity)
    events = _get(client, "/audit", limit=5)["events"]
    assert events and {"id", "event_type", "actor", "at"}.issubset(events[0])
    behaviour = _get(client, "/behavior/summary")
    assert set(["features", "patterns", "raw_events", "observed_vs_self_report"]).issubset(behaviour)
    assert set(["task_completion_rate", "skip_rate", "edit_rate"]).issubset(behaviour["features"])
    state = _get(client, "/state/current")
    assert set(["available", "dimensions", "observed", "message"]).issubset(state)
    me = _get(client, "/me")
    assert {"id", "display_name", "quiet_mode", "auto_time_adjust", "coins", "streak", "today_long"}.issubset(me)
    params = _get(client, "/config/params")
    assert {"params", "model_version", "policy"}.issubset(params)
    telegram = _get(client, "/integrations/telegram")
    assert {"enabled", "chat_id", "optional", "message"}.issubset(telegram)
    progress = _get(client, "/progress/overview")
    assert {"attempts", "answered", "not_entered", "accuracy", "coverage", "weaknesses", "trends"}.issubset(progress)


def test_checkin_reflection_recovery_and_exam_files_contract(client):
    """The forms the student fills in: daily check-in, weekly reflection, recovery, exam files."""
    _seed_screen_data(client)

    start = _get(client, "/checkins/questions", phase="start")
    assert start["phase"] == "start" and start["questions"]
    question = start["questions"][0]
    assert {"code", "text", "kind"}.issubset(question)
    if question["kind"] == "scale":
        assert {"min", "max"}.issubset(question)
    saved = _post(client, "/checkins", {"phase": "start", "answers": {question["code"]: 4}})
    assert {"phase", "date", "skipped", "recorded"}.issubset(saved)
    assert saved["recorded"] is True
    skipped = _post(client, "/checkins", {"phase": "end", "skipped": True})
    assert skipped["skipped"] is True

    reflections = _get(client, "/reflections/questions")
    assert reflections["questions"]
    assert {"code", "text", "kind"}.issubset(reflections["questions"][0])
    reflection = _post(client, "/reflections", {"answers": {reflections["questions"][0]["code"]: "فصل ۲"}})
    assert set(["week_start", "recorded", "skipped"]).issubset(reflection)

    recovery = _post(client, "/tasks/recovery")
    assert set(["missed", "moves", "message"]).issubset(recovery)

    exam = _post(client, "/exams", {"title": "امتحان با فایل", "exam_type": "school", "date": "1405/10/01"})
    bad = client.post(
        f"/api/exams/{exam['id']}/files",
        files={"file": ("payload.exe", b"nope", "application/octet-stream")},
    )
    assert bad.status_code == 422, "only documents and images may be attached"
    uploaded = client.post(
        f"/api/exams/{exam['id']}/files",
        files={"file": ("پاسخبرگ.pdf", b"%PDF-1.4 sample", "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    file_meta = uploaded.json()["files"][0]
    assert {"name", "stored_name", "size", "content_type", "uploaded_at"}.issubset(file_meta)
    assert file_meta["stored_name"].isascii(), "storage names stay ASCII"
    listed = [row for row in _get(client, "/exams")["exams"] if row["id"] == exam["id"]][0]
    assert listed["files"] and listed["files"][0]["name"] == "پاسخبرگ.pdf"
    download = client.get(f"/api/exams/{exam['id']}/files/{file_meta['stored_name']}")
    assert download.status_code == 200 and download.content == b"%PDF-1.4 sample"
