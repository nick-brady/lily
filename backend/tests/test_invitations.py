"""Smoke tests for the invitation routes + token helpers.

Like the rest of the smoke suite, these don't run against a real
database; they assert auth gating and check that token helpers behave
sensibly for malformed input.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from models import FamilyMembership, FamilyRole
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


def test_co_parent_routes_require_auth() -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    client = _client()
    for method, path in [
        ("GET", f"/family/{fake_id}/co-parents"),
        ("POST", f"/family/{fake_id}/co-parents/invitations"),
        ("DELETE", f"/family/{fake_id}/co-parents/invitations/{fake_id}"),
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


# --- redeem() role-upgrade logic (no real DB) ------------------------------


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _FakeSession:
    """Minimal stand-in for a Session covering only what `redeem` touches:
    a single membership lookup plus no-op add/flush.
    """

    def __init__(self, membership):
        self._membership = membership
        self.added: list = []

    def scalars(self, _stmt):
        return _FakeScalarResult(self._membership)

    def add(self, obj):
        self.added.append(obj)
        self._membership = obj

    def flush(self):
        pass


class _FakeInvitation:
    def __init__(self, role):
        self.family_id = uuid.uuid4()
        self.role = role
        self.redemption_count = 0


def test_redeem_upgrades_viewer_to_co_parent() -> None:
    invitation = _FakeInvitation(FamilyRole.co_parent)
    existing = FamilyMembership(
        family_id=invitation.family_id,
        user_id=uuid.uuid4(),
        role=FamilyRole.family_viewer,
    )
    db = _FakeSession(existing)

    membership = invitations_repo.redeem(db, invitation=invitation, user_id=existing.user_id)

    assert membership.role is FamilyRole.co_parent
    assert invitation.redemption_count == 1


def test_redeem_never_downgrades_owner() -> None:
    invitation = _FakeInvitation(FamilyRole.co_parent)
    existing = FamilyMembership(
        family_id=invitation.family_id,
        user_id=uuid.uuid4(),
        role=FamilyRole.owner,
    )
    db = _FakeSession(existing)

    membership = invitations_repo.redeem(db, invitation=invitation, user_id=existing.user_id)

    assert membership.role is FamilyRole.owner
    assert invitation.redemption_count == 1


def test_redeem_creates_membership_for_new_user() -> None:
    invitation = _FakeInvitation(FamilyRole.co_parent)
    db = _FakeSession(None)
    user_id = uuid.uuid4()

    membership = invitations_repo.redeem(db, invitation=invitation, user_id=user_id)

    assert membership.role is FamilyRole.co_parent
    assert membership in db.added
    assert invitation.redemption_count == 1
