"""API tests: progress + analytics endpoints (spec 14)."""

import uuid

from fastapi.testclient import TestClient

from tests.helpers import base_config


def _setup(client: TestClient) -> dict:
    book_id = client.post("/books/import", json=base_config()).json()["book_id"]
    tree = client.get(f"/books/{book_id}/nodes").json()
    t1 = tree["nodes"][0]["children"][0]["id"]
    view = client.post("/test-sessions", json={
        "node_id": t1, "count": 3, "parity": "any", "timed": False}).json()
    session_id = view["session"]["id"]
    qids = [q["question_id"] for q in view["questions"]]
    client.post(f"/test-sessions/{session_id}/answers", json={"answers": [
        {"question_id": qids[0], "answer": "2", "client_attempt_id": str(uuid.uuid4())}]})
    client.post(f"/test-sessions/{session_id}/finish")
    return {"book_id": book_id, "t1": t1, "qid": qids[0]}


def test_progress_endpoints(client: TestClient) -> None:
    ctx = _setup(client)
    overview = client.get("/progress/overview").json()
    assert overview["sessions_completed"] == 1
    assert overview["volume"] == 3
    assert len(overview["books"]) == 1

    book = client.get(f"/progress/books/{ctx['book_id']}").json()
    assert len(book["topics"]) == 3
    t1 = next(t for t in book["topics"] if t["node_id"] == ctx["t1"])
    assert t1["coverage"] == 1.0

    node = client.get(f"/progress/nodes/{ctx['t1']}").json()
    assert node["node"]["node_id"] == ctx["t1"]
    assert node["children"] == []

    hist = client.get(f"/progress/questions/{ctx['qid']}").json()
    assert hist["sessions_count"] == 1
    assert hist["attempt_count"] == 1
    assert "answer_key" not in hist  # exact key check (has_answer_key is fine)


def test_analytics_endpoints(client: TestClient) -> None:
    _setup(client)
    trends = client.get("/analytics/trends?days=7&group_by=day").json()
    assert len(trends["points"]) == 7
    assert sum(p["volume"] for p in trends["points"]) == 3
    weekly = client.get("/analytics/trends?days=7&group_by=week").json()
    assert len(weekly["points"]) >= 1

    weak = client.get("/analytics/weaknesses?min_volume=1").json()
    assert len(weak["items"]) >= 1


def test_analytics_errors(client: TestClient) -> None:
    assert client.get("/progress/books/999").status_code == 404
    assert client.get("/progress/nodes/999").status_code == 404
    assert client.get("/progress/questions/999").status_code == 404
    r = client.get("/analytics/trends?group_by=month")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_group_by"
    r = client.get("/analytics/weaknesses?limit=500")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_limit"
