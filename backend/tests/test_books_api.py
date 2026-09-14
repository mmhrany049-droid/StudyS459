"""API tests: Book Engine endpoints (spec 14)."""

from fastapi.testclient import TestClient

from tests.helpers import base_config


def test_import_then_read_flow(client: TestClient) -> None:
    r = client.post("/books/import", json=base_config())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "imported"
    book_id = body["book_id"]

    # Same config again -> idempotent 200.
    r = client.post("/books/import", json=base_config())
    assert r.status_code == 200
    assert r.json()["status"] == "unchanged"

    # Changed content -> 409 envelope.
    changed = base_config()
    changed["book"]["title"] = "تغییر"
    r = client.post("/books/import", json=changed)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "book_already_imported"

    # List + detail.
    books = client.get("/books").json()
    assert len(books) == 1
    assert books[0]["active"] is True
    assert books[0]["question_count"] == 3
    detail = client.get(f"/books/{book_id}").json()
    assert detail["subject"]["name"] == "شیمی"

    # Tree.
    tree = client.get(f"/books/{book_id}/nodes").json()
    assert tree["book_id"] == book_id
    assert len(tree["nodes"]) == 1
    ch1 = tree["nodes"][0]
    assert ch1["is_leaf"] is False
    assert [c["code"] for c in ch1["children"]] == ["t1", "t2"]
    assert ch1["children"][0]["test_sets"][0]["question_count"] == 2

    # Children.
    kids = client.get(f"/nodes/{ch1['id']}/children").json()
    assert len(kids["children"]) == 2


def test_import_invalid_config(client: TestClient) -> None:
    r = client.post("/books/import", json={"book": {}})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "invalid_book_config"
    assert len(body["error"]["details"]["issues"]) > 0


def test_import_non_object_body(client: TestClient) -> None:
    r = client.post("/books/import", json=[1, 2])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_activation_endpoints(client: TestClient) -> None:
    book_id = client.post("/books/import", json=base_config()).json()["book_id"]

    r = client.delete(f"/users/me/books/{book_id}/activate")
    assert r.status_code == 200
    assert r.json()["active"] is False
    assert client.get("/books").json()[0]["active"] is False

    r = client.post(f"/users/me/books/{book_id}/activate")
    assert r.status_code == 200
    assert r.json()["active"] is True
    assert client.get("/books").json()[0]["active"] is True


def test_not_found_envelopes(client: TestClient) -> None:
    assert client.get("/books/999").json()["error"]["code"] == "book_not_found"
    assert client.get("/books/999").status_code == 404
    assert client.get("/books/999/nodes").status_code == 404
    assert client.get("/nodes/999/children").json()["error"]["code"] == "node_not_found"
    assert client.post("/users/me/books/999/activate").status_code == 404
    assert client.delete("/users/me/books/999/activate").status_code == 404
