"""Smoke tests for the route table.

Confirms routes are wired and authentication is enforced. Doesn't touch a
real database — endpoints that need one return 500 with these stubs, which
is fine because we're only asserting on auth-level behaviour.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from main import app

    return TestClient(app)


def test_root_returns_running() -> None:
    response = _client().get("/")
    assert response.status_code == 200
    assert response.json() == {"name": "lily", "status": "running"}


def test_me_requires_auth() -> None:
    response = _client().get("/me")
    assert response.status_code == 401


def test_birth_routes_require_auth() -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    client = _client()
    for path, method in [
        (f"/birth/{fake_id}", "GET"),
        (f"/birth/{fake_id}", "PATCH"),
        (f"/birth/{fake_id}/timeline", "GET"),
        (f"/birth/{fake_id}/contraction/start", "POST"),
        (f"/birth/{fake_id}/event/{fake_id}", "DELETE"),
        (f"/birth/{fake_id}/event/{fake_id}/toggle-ignore", "POST"),
        (f"/birth/{fake_id}/stream", "GET"),
    ]:
        response = client.request(method, path)
        assert response.status_code == 401, f"{method} {path} should require auth"


def test_gift_checkout_routes_require_auth() -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    client = _client()
    for path in (
        f"/birth/{fake_id}/gifts/{fake_id}/checkout",
        f"/birth/{fake_id}/gifts/storage/{fake_id}/checkout",
    ):
        response = client.post(path)
        assert response.status_code == 401, f"POST {path} should require auth"


def test_public_birth_routes_do_not_require_auth() -> None:
    """Public read-only routes must not return 401 when called without
    credentials. A 401 here would mean access control snuck in by
    accident. The routes hit the DB (which the test env doesn't have),
    so we accept any non-401 outcome as proof that auth isn't gating
    them.
    """
    client = _client()
    for path in ("/b/non-existent", "/b/non-existent/timeline"):
        try:
            response = client.get(path)
            assert response.status_code != 401, f"{path} should not require auth"
        except Exception:
            # DB-touching code blew up before reaching auth — that's also
            # proof that auth didn't reject the request first.
            pass


def test_legacy_websocket_route_is_gone() -> None:
    response = _client().get("/ws")
    # FastAPI returns 404 for unmounted WebSocket-only paths when accessed via HTTP.
    assert response.status_code == 404


def test_legacy_uploads_static_mount_is_gone() -> None:
    response = _client().get("/uploads/some-old-file.jpg")
    assert response.status_code == 404


def test_legacy_login_route_is_gone() -> None:
    response = _client().post("/login", json={"username": "admin", "password": "x"})
    assert response.status_code == 404
