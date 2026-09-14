"""Foundation acceptance: health endpoints."""

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["timezone"] == "Asia/Tehran"
    assert "X-Request-ID" in r.headers


def test_health_db_reachable(client: TestClient) -> None:
    r = client.get("/health/db")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "reachable"}
