"""API tests: academic + exam endpoints (spec 14)."""

from fastapi.testclient import TestClient

from tests.helpers import base_config


def _setup(client: TestClient) -> dict:
    book_id = client.post("/books/import", json=base_config()).json()["book_id"]
    book = client.get(f"/books/{book_id}").json()
    tree = client.get(f"/books/{book_id}/nodes").json()
    t1 = tree["nodes"][0]["children"][0]["id"]
    return {"book_id": book_id, "subject_id": book["subject"]["id"], "t1": t1}


def test_academic_flow(client: TestClient) -> None:
    ctx = _setup(client)
    sched = client.post("/schedules", json={
        "schedule_type": "school", "title": "مدرسه", "day_of_week": 5,
        "start_time": "08:00", "end_time": "10:00",
        "subject_id": ctx["subject_id"]}).json()
    assert sched["duration_minutes"] == 120
    assert len(client.get("/schedules").json()) == 1

    cs = client.post("/class-sessions", json={
        "schedule_id": sched["id"], "date": "2026-09-12",
        "subject_id": ctx["subject_id"], "attended": True}).json()
    assert cs["id"] > 0

    taught = client.post("/taught-lessons", json={
        "class_session_id": cs["id"], "subject_id": ctx["subject_id"],
        "node_id": ctx["t1"], "taught_at": "2026-09-12T08:30:00",
        "duration_minutes": 45}).json()
    assert taught["node_title"] == "عنوان ۱"

    hw = client.post("/homework", json={
        "source_type": "school", "title": "تکلیف", "subject_id": ctx["subject_id"],
        "due_at": "2026-09-20T20:00:00", "estimated_minutes": 30,
        "create_task": True}).json()
    assert hw["task_id"] is not None
    hw2 = client.patch(f"/homework/{hw['id']}", json={"status": "done"}).json()
    assert hw2["status"] == "done"
    assert len(client.get("/homework?status=pending").json()) == 0


def test_exam_flow(client: TestClient) -> None:
    ctx = _setup(client)
    exam = client.post("/exams", json={
        "title": "آزمون", "exam_type": "mock",
        "exam_date": "2026-09-10"}).json()
    exam = client.post(f"/exams/{exam['id']}/questions", json={"questions": [
        {"sequence_no": 1, "topic_node_id": ctx["t1"], "result": "correct"},
        {"sequence_no": 2, "result": "wrong"},
    ]}).json()
    assert len(exam["questions"]) == 2
    rep = client.get(f"/exams/{exam['id']}/analytics").json()
    assert (rep["correct"], rep["wrong"], rep["unmapped"]) == (1, 1, 1)
    assert client.get("/exams/999").status_code == 404


def test_academic_errors(client: TestClient) -> None:
    assert client.post("/schedules", json={
        "schedule_type": "school", "title": "x", "day_of_week": 5,
        "start_time": "10:00", "end_time": "09:00"}).status_code == 422
    assert client.post("/homework", json={
        "title": "x", "subject_id": 999,
        "due_at": "2026-09-20T20:00:00"}).status_code == 404
    assert client.patch("/homework/999", json={"status": "done"}).status_code == 404
    assert client.get("/homework?status=bogus").status_code == 422
