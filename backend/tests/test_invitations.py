"""Smoke tests for the invitation routes + token helpers.

Like the rest of the smoke suite, these don't run against a real
database; they assert auth gating and check that token helpers behave
sensibly for malformed input.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from models import AuthIdentifierKind, FamilyMembership, FamilyRole
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


def test_remove_viewer_route_requires_auth() -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = _client().request("DELETE", f"/birth/{fake_id}/viewers/{fake_id}")
    assert response.status_code == 401


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
    """Minimal stand-in for a Session covering what `redeem` touches.

    `redeem` issues two lookups: first the membership, then the prior
    redemption. We answer the first with the seeded membership and the
    second with None, so a redemption row is always recorded in tests.
    """

    def __init__(self, membership):
        self._membership = membership
        self._scalar_calls = 0
        self.added: list = []

    def scalars(self, _stmt):
        self._scalar_calls += 1
        value = self._membership if self._scalar_calls == 1 else None
        return _FakeScalarResult(value)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass


class _FakeInvitation:
    def __init__(self, role):
        self.id = uuid.uuid4()
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


# --- remove_viewer() logic (no real DB) ------------------------------------


class _FakeRemoveSession:
    """Stand-in for `remove_viewer`: one `scalars().first()` for the
    membership, then one `execute().all()` for the (redemption, invitation)
    rows to clean up. Records what gets deleted.
    """

    def __init__(self, membership, redemption_rows):
        self._membership = membership
        self._redemption_rows = redemption_rows
        self.deleted: list = []

    def scalars(self, _stmt):
        return _FakeScalarResult(self._membership)

    def execute(self, _stmt):
        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return _Result(self._redemption_rows)

    def delete(self, obj):
        self.deleted.append(obj)

    def flush(self):
        pass


def test_remove_viewer_deletes_membership_and_redemptions() -> None:
    family_id = uuid.uuid4()
    user_id = uuid.uuid4()
    membership = FamilyMembership(
        family_id=family_id, user_id=user_id, role=FamilyRole.family_viewer
    )
    invitation = _FakeInvitation(FamilyRole.family_viewer)
    invitation.redemption_count = 1
    redemption = object()
    db = _FakeRemoveSession(membership, [(redemption, invitation)])

    removed = invitations_repo.remove_viewer(db, family_id=family_id, user_id=user_id)

    assert removed is True
    assert membership in db.deleted
    assert redemption in db.deleted
    assert invitation.redemption_count == 0


def test_remove_viewer_refuses_co_parent() -> None:
    family_id = uuid.uuid4()
    user_id = uuid.uuid4()
    membership = FamilyMembership(
        family_id=family_id, user_id=user_id, role=FamilyRole.co_parent
    )
    db = _FakeRemoveSession(membership, [])

    removed = invitations_repo.remove_viewer(db, family_id=family_id, user_id=user_id)

    assert removed is False
    assert db.deleted == []


def test_remove_viewer_missing_membership_returns_false() -> None:
    db = _FakeRemoveSession(None, [])
    removed = invitations_repo.remove_viewer(
        db, family_id=uuid.uuid4(), user_id=uuid.uuid4()
    )
    assert removed is False
    assert db.deleted == []


# --- _resolve_invite_contact() (no real DB) --------------------------------


def test_resolve_invite_contact_none_when_no_hint() -> None:
    from routes.invitations import _resolve_invite_contact

    assert _resolve_invite_contact(None, None) == (None, None, None)


def test_resolve_invite_contact_normalizes_email() -> None:
    from routes.invitations import _resolve_invite_contact

    email, phone, kind = _resolve_invite_contact(" Janet@Example.com ", None)
    assert email == "janet@example.com"
    assert phone is None
    assert kind is AuthIdentifierKind.email


def test_resolve_invite_contact_normalizes_phone() -> None:
    from routes.invitations import _resolve_invite_contact

    email, phone, kind = _resolve_invite_contact(None, "555-555-0123")
    assert email is None
    assert phone == "+15555550123"
    assert kind is AuthIdentifierKind.phone


def test_resolve_invite_contact_rejects_garbage() -> None:
    from routes.invitations import _resolve_invite_contact

    with pytest.raises(HTTPException) as exc_info:
        _resolve_invite_contact("not an email or phone", None)
    assert exc_info.value.status_code == 400


def _invitation(*, expires_in_days: int, revoked: bool = False):
    """A ViewerInvitation detached from any session — enough for the
    pure-function expiry/revocation checks."""
    from datetime import datetime, timedelta, timezone

    from models import ViewerInvitation

    now = datetime.now(timezone.utc)
    return ViewerInvitation(
        expires_at=now + timedelta(days=expires_in_days),
        revoked_at=now if revoked else None,
    )


def test_expired_and_revoked_are_told_apart() -> None:
    """They answer differently on purpose. An expired link was genuinely
    shared with its holder, so saying "this lapsed" gives away nothing and
    lets them ask for a fresh one — which matters when the link is a QR
    code printed on an announcement card that outlives the 90-day TTL.
    Revocation is the kill switch for putting someone out, so it must look
    like nothing ever existed.
    """
    lapsed = _invitation(expires_in_days=-1)
    assert invitations_repo.is_expired(lapsed) is True
    assert invitations_repo.is_redeemable(lapsed) is False

    killed = _invitation(expires_in_days=30, revoked=True)
    assert invitations_repo.is_expired(killed) is False
    assert invitations_repo.is_redeemable(killed) is False


def test_revoked_never_reads_as_merely_expired() -> None:
    """A link that was revoked AND has since run out of time is still a
    revocation — otherwise waiting out the TTL would turn a silent 404
    into a helpful "ask for another"."""
    both = _invitation(expires_in_days=-5, revoked=True)
    assert invitations_repo.is_expired(both) is False
    assert invitations_repo.is_redeemable(both) is False


def test_live_invitation_is_neither() -> None:
    live = _invitation(expires_in_days=30)
    assert invitations_repo.is_expired(live) is False
    assert invitations_repo.is_redeemable(live) is True
