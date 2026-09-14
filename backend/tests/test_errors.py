"""Foundation acceptance: every error uses the standard envelope."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import AppError
from app.main import create_app


def test_404_uses_envelope(client: TestClient) -> None:
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert set(body.keys()) == {"error"}
    assert body["error"]["code"] == "not_found"
    assert isinstance(body["error"]["message"], str)


def test_app_error_uses_envelope() -> None:
    app: FastAPI = create_app()

    @app.get("/_boom")
    def _boom() -> None:
        raise AppError("demo_failure", "boom happened", status_code=418, details={"n": 1})

    r = TestClient(app).get("/_boom")
    assert r.status_code == 418
    assert r.json() == {"error": {"code": "demo_failure", "message": "boom happened", "details": {"n": 1}}}


def test_unexpected_error_is_500_envelope_without_leak() -> None:
    app: FastAPI = create_app()

    @app.get("/_kaboom")
    def _kaboom() -> None:
        raise RuntimeError("secret internals")

    r = TestClient(app, raise_server_exceptions=False).get("/_kaboom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "internal_error"
    # DEBUG=false by default -> internals must not leak to the client.
    assert body["error"]["details"] is None
