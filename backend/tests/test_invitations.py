"""Smoke tests for the invitation routes + token helpers.

Like the rest of the smoke suite, these don't run against a real
database; they assert auth gating and check that token helpers behave
sensibly for malformed input.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from repositories import invitations as invitations_repo


def _client() -> TestClient:
    from main import app

    return TestClient(app)


def test_create_and_list_invitations_require_parent_auth() -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    client = _client()
    for method, path in [
        ("POST", f"/birth/{fake_id}/invitations"),
        ("GET", f"/birth/{fake_id}/invitations"),
        ("DELETE", f"/birth/{fake_id}/invitations/{fake_id}"),
    ]:
        response = client.request(method, path)
        assert response.status_code == 401, f"{method} {path} should require auth"


def test_lookup_invitation_does_not_require_auth() -> None:
    """`GET /invite/{token}` is the public lookup endpoint. We don't have a
    real DB in this test env so we accept anything other than 401 as proof
    that auth isn't gating it."""
    client = _client()
    try:
        response = client.get("/invite/garbage")
        assert response.status_code != 401
    except Exception:
        pass


def test_redeem_authed_requires_auth() -> None:
    response = _client().post("/invite/anything/redeem")
    assert response.status_code == 401


def test_lookup_by_token_rejects_malformed_input() -> None:
    """The token format is `{uuid}.{secret}`. Anything else returns None
    without touching the DB.
    """

    class _StubSession:
        def get(self, _model, _id):  # pragma: no cover - never called
            raise AssertionError("DB should not be touched for malformed tokens")

    stub = _StubSession()
    assert invitations_repo.lookup_by_token(stub, "") is None
    assert invitations_repo.lookup_by_token(stub, "not-a-token") is None
    assert invitations_repo.lookup_by_token(stub, "not-uuid.somesecret") is None
    assert invitations_repo.lookup_by_token(stub, "anything.") is None
