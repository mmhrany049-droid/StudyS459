"""API tests: planner + tasks + overrides (spec 14)."""

from fastapi.testclient import TestClient

from tests.helpers import base_config


def _setup(client: TestClient) -> dict:
    book_id = client.post("/books/import", json=base_config()).json()["book_id"]
    tree = client.get(f"/books/{book_id}/nodes").json()
    t1 = tree["nodes"][0]["children"][0]["id"]
    return {"book_id": book_id, "t1": t1}


def test_planner_flow(client: TestClient) -> None:
    ctx = _setup(client)
    task = client.post("/tasks", json={
        "task_type": "test", "title": "تست ت۱", "node_id": ctx["t1"],
        "question_count": 10, "parity": "odd", "estimated_minutes": 20,
        "source_type": "manual"}).json()
    assert task["status"] == "planned" and task["placed_on"] is None

    days = client.put("/planner/placements", json={"placements": [
        {"task_id": task["id"], "date": "2026-09-12", "position": 0}]}).json()
    assert days[0]["workload_minutes"] == 20

    day = client.get("/planner/day/2026-09-12").json()
    assert day["is_school_day"] is True and day["capacity_minutes"] == 90
    assert day["placements"][0]["task"]["id"] == task["id"]

    week = client.get("/planner/week/2026-09-14").json()
    assert week["week_start"] == "2026-09-12" and len(week["days"]) == 7
    assert week["unplaced"] == []

    done = client.post(f"/tasks/{task['id']}/complete").json()
    assert done["status"] == "completed"

    ov = client.post("/school-day-overrides", json={
        "date": "2026-09-12", "is_school_day": False,
        "reason": "مدرسه نمی‌روم"}).json()
    assert ov["is_school_day"] is False
    day2 = client.get("/planner/day/2026-09-12").json()
    assert (day2["capacity_minutes"], day2["override"]) == (240, True)


def test_planner_errors(client: TestClient) -> None:
    _setup(client)
    assert client.get("/planner/day/xyz").status_code == 422
    r = client.put("/planner/placements", json={"placements": []})
    assert r.status_code == 422 and r.json()["error"]["code"] == "empty_placements"
    r = client.put("/planner/placements", json={"placements": [
        {"task_id": 999, "date": "2026-09-12"}]})
    assert r.status_code == 404
    assert client.post("/tasks/999/complete").status_code == 404
    assert client.patch("/tasks/999", json={"title": "x"}).status_code == 404
    r = client.post("/tasks", json={"task_type": "test", "title": "x",
                                    "node_id": 999, "question_count": 3})
    assert r.status_code == 404
