"""API tests: rewards endpoints (spec 14) + history alias."""

import uuid

from fastapi.testclient import TestClient

from tests.helpers import base_config


def test_rewards_endpoints(client: TestClient) -> None:
    book_id = client.post("/books/import", json=base_config()).json()["book_id"]
    tree = client.get(f"/books/{book_id}/nodes").json()
    t1 = tree["nodes"][0]["children"][0]["id"]
    view = client.post("/test-sessions", json={
        "node_id": t1, "count": 3, "parity": "any", "timed": False}).json()
    session_id = view["session"]["id"]
    qids = [q["question_id"] for q in view["questions"]]
    answers = []
    for i, qid in enumerate(qids):
        q = next(x for x in view["questions"] if x["question_id"] == qid)
        key = {"تمرین ۱": {1: "2", 2: "4"}, "چکاپ ۱": {1: "1"}}[q["test_set_title"]][q["sequence_no"]]
        answers.append({"question_id": qid, "answer": key if i < 2 else "9",
                        "client_attempt_id": str(uuid.uuid4())})
    client.post(f"/test-sessions/{session_id}/answers", json={"answers": answers})
    fin = client.post(f"/test-sessions/{session_id}/finish").json()
    assert fin["result"]["points_earned"] == 4  # 2 correct x2

    summary = client.get("/rewards/summary").json()
    assert summary["total_points"] == 4
    assert summary["current_streak"] == 0  # no study tasks
    assert {e["event_type"] for e in summary["recent_events"]} == {
        "test_session", "badge_earned"}  # ch1 hit 100% coverage too

    events = client.get("/rewards/events").json()
    assert events[0]["event_type"] == "badge_earned"  # latest first

    badges = client.get("/rewards/badges").json()
    assert len(badges) == 6
    earned = {b["code"] for b in badges if b["earned"]}
    assert earned == {"chapter_coverage_80"}


def test_question_history_alias(client: TestClient) -> None:
    book_id = client.post("/books/import", json=base_config()).json()["book_id"]
    tree = client.get(f"/books/{book_id}/nodes").json()
    t1 = tree["nodes"][0]["children"][0]["id"]
    view = client.post("/test-sessions", json={
        "node_id": t1, "count": 1, "parity": "any", "timed": False}).json()
    qid = view["questions"][0]["question_id"]
    a = client.get(f"/questions/{qid}/history").json()
    b = client.get(f"/progress/questions/{qid}").json()
    assert a == b
