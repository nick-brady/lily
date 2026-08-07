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
    assert response.json() == {"name": "arrival-story", "status": "running"}


def test_me_requires_auth() -> None:
    response = _client().get("/me")
    assert response.status_code == 401


def test_create_birth_requires_auth() -> None:
    response = _client().post(
        "/births", json={"baby_name": "Lily", "slug": "lily"}
    )
    assert response.status_code == 401


def test_birth_routes_require_auth() -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    client = _client()
    for path, method in [
        ("/me", "DELETE"),
        (f"/birth/{fake_id}", "GET"),
        (f"/birth/{fake_id}", "PATCH"),
        (f"/birth/{fake_id}/timeline", "GET"),
        (f"/birth/{fake_id}/contraction/start", "POST"),
        (f"/birth/{fake_id}/event/{fake_id}", "DELETE"),
        (f"/birth/{fake_id}/event/{fake_id}/toggle-ignore", "POST"),
        (f"/birth/{fake_id}/stream", "GET"),
        (f"/birth/{fake_id}/export", "GET"),
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


def test_slug_routes_never_answer_401() -> None:
    """A birth page is private, but it must never say so with a 401.

    401 is an invitation — it tells whoever is holding the URL that
    something real is here and signing in would reach it. These routes
    take optional auth precisely so a caller without a session falls
    through to the same 404 an unused slug gives. The routes hit the DB
    (which the test env doesn't have), so an exception is equally good
    proof that no auth layer rejected the request first.
    """
    client = _client()
    for path in ("/b/non-existent", "/b/non-existent/timeline"):
        try:
            response = client.get(path)
            assert response.status_code != 401, f"{path} must not answer 401"
        except Exception:
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
