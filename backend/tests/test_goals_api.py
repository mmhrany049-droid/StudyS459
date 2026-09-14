"""API tests: weekly goal endpoints (spec 14)."""

from datetime import date

from fastapi.testclient import TestClient

from app.analytics.metrics import normalize_week
from tests.helpers import base_config


def _setup(client: TestClient) -> dict:
    book_id = client.post("/books/import", json=base_config()).json()["book_id"]
    tree = client.get(f"/books/{book_id}/nodes").json()
    t1 = tree["nodes"][0]["children"][0]["id"]
    return {"book_id": book_id, "t1": t1,
            "week": normalize_week(date.today())[0].isoformat()}


def test_goal_crud_and_candidates(client: TestClient) -> None:
    ctx = _setup(client)
    week = ctx["week"]
    created = client.post(f"/goals/weeks/{week}", json={"items": [
        {"goal_type": "count", "target_value": 20},
        {"goal_type": "topic", "target_value": 1.0, "node_id": ctx["t1"]},
    ]}).json()
    assert created["week_start"] == week
    assert len(created["items"]) == 2
    assert created["items"][1]["progress"]["remaining"] == 3.0  # fresh pool

    fetched = client.get(f"/goals/weeks/{week}").json()
    assert fetched["id"] == created["id"]

    cands = client.get(f"/goals/{created['id']}/candidate-tasks").json()
    assert len(cands["items"]) >= 1
    assert cands["items"][0]["recommendation_reason"] != ""

    patched = client.patch(f"/goals/{created['id']}", json={"active": False}).json()
    assert patched["active"] is False


def test_goal_errors(client: TestClient) -> None:
    ctx = _setup(client)
    week = ctx["week"]
    assert client.get(f"/goals/weeks/{week}").status_code == 404
    client.post(f"/goals/weeks/{week}", json={"items": [
        {"goal_type": "count", "target_value": 5}]})
    r = client.post(f"/goals/weeks/{week}", json={"items": [
        {"goal_type": "count", "target_value": 5}]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "goal_exists"
    assert client.get("/goals/weeks/xyz").status_code == 422
    assert client.get("/goals/999/candidate-tasks").status_code == 404
    r = client.post("/goals/weeks/2020-01-04", json={"items": [
        {"goal_type": "topic", "target_value": 1.0}]})
    assert r.status_code == 422
    r = client.patch("/goals/999", json={"active": True})
    assert r.status_code == 404
