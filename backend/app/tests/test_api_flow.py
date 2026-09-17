"""API-level acceptance flow: INPUT → MODEL → DECIDE → PLAN → EXECUTE → OBSERVE → LEARN → REPLAN.

Runs against the real FastAPI app (fresh+seeded DB per test) so routing, payload
shapes and Persian presentation are covered, not just the engines.
"""

from __future__ import annotations

import re

LATIN_DIGIT = re.compile(r"[0-9]")


def _bootstrap(client, monkeypatch=None):
    response = client.post("/api/bootstrap", json={})
    assert response.status_code == 200, response.text
    return response.json()


def _taught_and_questions(client, count=20):
    assert client.post("/api/topics/1/taught", json={"taught": True, "cascade": True}).status_code == 200
    assert (
        client.post(
            "/api/books/1/nodes/3/questions/range", json={"from_sequence": 1, "to_sequence": count}
        ).status_code
        == 200
    )
    keys = client.put(
        "/api/books/1/nodes/3/answer-key",
        json={"items": [{"sequence_no": i, "answer_key": str((i % 4) + 1)} for i in range(1, count + 1)]},
    )
    assert keys.status_code == 200, keys.text
    return count


def _submit(client, entries, count=20, duration=41):
    session = client.post(
        "/api/test-sessions", json={"book_id": 1, "topic_id": 3, "count": count, "start_now": True}
    ).json()
    return client.post(
        f"/api/test-sessions/{session['id']}/submit",
        json={"entries": entries, "actual_duration_minutes": duration},
    )


def test_full_flow_input_to_replan(client):
    bootstrap = _bootstrap(client)
    assert bootstrap["today"] and bootstrap["date_long"]
    assert not LATIN_DIGIT.search(bootstrap["date_long"]), "the UI must never show Gregorian dates"
    assert not LATIN_DIGIT.search(bootstrap["today"])

    _taught_and_questions(client)
    detail = client.get("/api/topics/1").json()
    assert detail["taught"]["taught"] is True

    session = client.post(
        "/api/test-sessions", json={"book_id": 1, "topic_id": 3, "count": 10, "start_now": True}
    ).json()
    assert session["questions"] and all("sequence_no" in item for item in session["questions"])

    entries = []
    for index, question in enumerate(session["questions"]):
        if index < 5:
            entries.append(
                {"question_id": question["question_id"], "state": "ANSWERED", "selected_choice": str((index % 4) + 1)}
            )
        elif index < 8:
            entries.append({"question_id": question["question_id"], "state": "UNANSWERED"})
        else:
            entries.append({"question_id": question["question_id"], "state": "NOT_ENTERED"})
    result = client.post(
        f"/api/test-sessions/{session['id']}/submit",
        json={"entries": entries, "actual_duration_minutes": 41},
    ).json()

    assert result["total"] == 10
    assert result["answered"] == 5
    assert result["unanswered"] == 3
    assert result["not_entered"] == 2
    assert result["not_evaluable"] == 0
    assert result["missing_answer_keys"] == 0
    assert result["pending_correction"] is False, "NOT_ENTERED rows must never ask for answer-key correction"
    assert result["invariant_ok"] is True
    assert result["status"] == "completed"
    assert result["rewards"]["coins"] > 0
    assert result["planned_duration_low"] < result["planned_duration_high"]

    # re-asking for the result of a finished session must not double the coins
    again = client.post(f"/api/test-sessions/{session['id']}/submit", json={"entries": []}).json()
    assert again["idempotent"] is True
    assert again["rewards"]["coins"] == result["rewards"]["coins"]

    state = client.get("/api/learning/state/3").json()
    assert state["accuracy"] is not None
    assert state["not_entered"] == 2 or state.get("not_entered") is not None

    review = client.post("/api/review/build").json()
    assert review is not None
    queue = client.get("/api/review/queue").json()
    assert queue["stats"]["open"] >= 1

    dashboard = client.get("/api/dashboard").json()
    assert "what_matters_now" in dashboard and "what_next" in dashboard
    priorities = dashboard["what_matters_now"]["priorities"]
    assert priorities and priorities[0]["top_reasons"], "priorities must always cite their drivers"
    assert priorities[0]["top_reasons"][0]["evidence"].get("reason")

    recommendation = client.get("/api/recommendations?refresh=true").json()
    assert "recommendations" in recommendation

    planning = client.post("/api/planning/sessions", json={}).json()
    assert planning["stages"]
    week = client.get("/api/planning/week").json()
    assert week["days"] and "capacity" in week


def test_missing_answer_key_asks_for_correction_instead_of_scoring(client):
    _bootstrap(client)
    assert client.post("/api/topics/1/taught", json={"taught": True, "cascade": True}).status_code == 200
    assert (
        client.post("/api/books/1/nodes/3/questions/range", json={"from_sequence": 1, "to_sequence": 10}).status_code
        == 200
    )
    session = client.post(
        "/api/test-sessions", json={"book_id": 1, "topic_id": 3, "count": 10, "start_now": True}
    ).json()
    for question in session["questions"]:  # deterministic: this test is about missing keys
        cleared = client.put(
            f"/api/questions/{question['question_id']}/answer-key", json={"answer_key": None, "reason": "تست"}
        )
        assert cleared.status_code == 200, cleared.text
    entries = [
        {"question_id": question["question_id"], "state": "ANSWERED", "selected_choice": "1"}
        for question in session["questions"]
    ]
    result = client.post(f"/api/test-sessions/{session['id']}/submit", json={"entries": entries}).json()
    assert result["wrong"] == 0, "an answer without a key is not wrong, it is unknown"
    assert result["not_evaluable"] == 10
    assert result["missing_answer_keys"] == 10
    assert result["pending_correction"] is True
    assert result["status"] == "pending_correction"
    assert result["invariant_ok"] is True


def test_answer_key_correction_re_evaluates_and_keeps_the_old_key(client):
    _bootstrap(client)
    _taught_and_questions(client, count=10)
    question = client.get("/api/books/1/nodes/3/questions?limit=1").json()
    rows = question.get("items") or question.get("questions")
    question_id = rows[0]["id"]
    before = rows[0].get("answer_key")

    corrected = client.put(
        f"/api/questions/{question_id}/answer-key", json={"answer_key": "3", "reason": "تصحیح"}
    )
    assert corrected.status_code == 200, corrected.text
    body = corrected.json()
    assert body["changed"] is True
    history = client.get(f"/api/questions/{question_id}/history").json()
    versions = history.get("answer_key_history") or []
    assert len(versions) >= 2, "the previous key must survive as a version"
    if before:
        assert before in {item.get("answer_key") for item in versions}


def test_jalali_only_and_week_starts_on_saturday(client):
    _bootstrap(client)
    week = client.get("/api/planning/week").json()
    first = week["days"][0]
    assert first["date_long"].startswith("شنبه")
    assert not LATIN_DIGIT.search(first["date"] + first["date_long"])
    capacity = client.get("/api/capacity/today").json()
    assert capacity["theoretical_minutes"] >= capacity["realistic_minutes"]
    assert not LATIN_DIGIT.search(str(capacity["explanation"]))
