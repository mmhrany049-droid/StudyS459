"""API tests: user profile (Phase 8 settings)."""

from fastapi.testclient import TestClient


def test_get_me_defaults(client: TestClient) -> None:
    me = client.get("/users/me").json()
    assert me["id"] == 1
    assert me["timezone"] == "Asia/Tehran"
    assert me["display_name"] != ""


def test_patch_me(client: TestClient) -> None:
    me = client.patch("/users/me", json={
        "display_name": "علی", "timezone": "UTC"}).json()
    assert (me["display_name"], me["timezone"]) == ("علی", "UTC")
    again = client.get("/users/me").json()
    assert again["timezone"] == "UTC"

    r = client.patch("/users/me", json={"timezone": "Mars/Olympus"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_timezone"
