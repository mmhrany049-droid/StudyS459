"""API tests: Test Engine endpoints (spec 14)."""

import uuid

from fastapi.testclient import TestClient

from tests.helpers import base_config


def _assert_no_key(obj, key: str) -> None:
    """Recursively assert no dict uses `key` (exact match, not substring)."""
    if isinstance(obj, dict):
        assert key not in obj
        for v in obj.values():
            _assert_no_key(v, key)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_key(v, key)


def _import_book(client: TestClient) -> int:
    r = client.post("/books/import", json=base_config())
    assert r.status_code == 201, r.text
    return r.json()["book_id"]


def _node_id(client: TestClient, book_id: int, code: str) -> int:
    tree = client.get(f"/books/{book_id}/nodes").json()

    def walk(nodes):
        for n in nodes:
            if n["code"] == code:
                return n["id"]
            found = walk(n["children"])
            if found:
                return found
        return None

    node_id = walk(tree["nodes"])
    assert node_id is not None
    return node_id


def test_full_flow_over_http(client: TestClient) -> None:
    book_id = _import_book(client)
    node_id = _node_id(client, book_id, "t1")

    r = client.post("/test-sessions", json={
        "node_id": node_id, "count": 3, "parity": "any", "timed": False,
    })
    assert r.status_code == 201, r.text
    view = r.json()
    session_id = view["session"]["id"]
    assert len(view["questions"]) == 3
    _assert_no_key(view, "answer_key")  # keys never leak to clients

    qids = [q["question_id"] for q in view["questions"]]
    r = client.post(f"/test-sessions/{session_id}/answers", json={"answers": [
        {"question_id": qids[0], "answer": "2", "response_time_seconds": 12,
         "client_attempt_id": str(uuid.uuid4())},
        {"question_id": qids[1], "answer": "9",  # wrong on purpose
         "client_attempt_id": str(uuid.uuid4())},
    ]})
    assert r.status_code == 201, r.text
    assert r.json()["attempts"][0]["duplicate"] is False

    r = client.post(f"/test-sessions/{session_id}/finish")
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["total"] == 3
    assert result["correct"] + result["wrong"] + result["unanswered"] + result["pending"] == 3
    assert result["unanswered"] == 1
    assert len(result["topic_breakdown"]) >= 1
    _assert_no_key(r.json(), "answer_key")

    # Idempotent finish.
    again = client.post(f"/test-sessions/{session_id}/finish").json()
    assert again["result"] == result

    # Parity state untouched by "any".
    ps = client.get(f"/nodes/{node_id}/parity-state").json()
    assert ps["last_parity"] is None and ps["suggested_parity"] is None


def test_contract_example_shape_accepted(client: TestClient) -> None:
    """The verbatim body shape from 14_API_CONTRACT_V1.md must work."""
    book_id = _import_book(client)
    node_id = _node_id(client, book_id, "t1")
    r = client.post("/test-sessions", json={
        "node_id": node_id, "count": 20, "sequence_from": 21,
        "sequence_to": 41, "parity": "odd", "timed": False,
    })
    # Shape accepted; pool too small -> clear insufficient message (spec 06).
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "insufficient_questions"
    assert "فقط 0" in body["error"]["message"]
    assert body["error"]["details"]["available"] == 0


def test_parity_lifecycle_over_http(client: TestClient) -> None:
    book_id = _import_book(client)
    node_id = _node_id(client, book_id, "t1")

    r = client.post("/test-sessions", json={
        "node_id": node_id, "count": 2, "parity": "odd", "timed": False})
    assert r.status_code == 201, r.text
    assert all(q["sequence_no"] % 2 == 1 for q in r.json()["questions"])

    ps = client.get(f"/nodes/{node_id}/parity-state").json()
    assert ps["last_parity"] == "odd"
    assert ps["suggested_parity"] == "even"

    r = client.post("/test-sessions", json={
        "node_id": node_id, "count": 1, "parity": "even", "timed": False})
    assert r.status_code == 201, r.text
    ps = client.get(f"/nodes/{node_id}/parity-state").json()
    assert (ps["last_parity"], ps["suggested_parity"]) == ("even", "odd")


def test_timed_session_reports_remaining(client: TestClient) -> None:
    book_id = _import_book(client)
    node_id = _node_id(client, book_id, "t1")
    r = client.post("/test-sessions", json={
        "node_id": node_id, "count": 1, "timed": True, "time_limit_seconds": 600})
    assert r.status_code == 201, r.text
    session = r.json()["session"]
    assert session["timed"] is True
    assert 0 < session["remaining_seconds"] <= 600
    assert session["expired"] is False

    # Untimed with a limit is rejected (spec 13 invariant).
    r = client.post("/test-sessions", json={
        "node_id": node_id, "count": 1, "timed": False, "time_limit_seconds": 60})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_timed_config"


def test_session_not_found_and_guards(client: TestClient) -> None:
    assert client.get("/test-sessions/999").status_code == 404
    assert client.get("/test-sessions/999").json()["error"]["code"] == "session_not_found"
    r = client.post("/test-sessions/999/finish")
    assert r.status_code == 404
    r = client.post("/test-sessions/999/answers", json={"answers": [
        {"question_id": 1, "answer": "1", "client_attempt_id": str(uuid.uuid4())}]})
    assert r.status_code == 404
    assert client.get("/nodes/999/parity-state").status_code == 404


def test_inactive_book_blocks_session(client: TestClient) -> None:
    book_id = _import_book(client)
    node_id = _node_id(client, book_id, "t1")
    assert client.delete(f"/users/me/books/{book_id}/activate").status_code == 200
    r = client.post("/test-sessions", json={"node_id": node_id, "count": 1})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "book_inactive"
