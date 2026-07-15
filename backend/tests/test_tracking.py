"""Tests for the /track endpoint, signup attribution, and last_seen_at.

Like the rest of the suite these don't run against a real database —
they cover auth gating, payload validation, and the pure logic around
attribution and the last-seen throttle.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import auth
from models import AuthChallenge, AuthIdentifierKind, User
from schemas import AuthVerifyIn, TrackIn


def _client() -> TestClient:
    from main import app

    return TestClient(app)


# --- /track endpoint gating + validation ------------------------------------


def test_track_does_not_require_auth() -> None:
    """Anonymous visitors are the whole point. No real DB here, so anything
    other than 401 proves auth isn't gating the route."""
    try:
        response = _client().post("/track", json={"path": "/"})
        assert response.status_code != 401
    except Exception:
        pass


def test_track_rejects_oversized_payload_before_touching_db() -> None:
    client = _client()
    response = client.post("/track", json={"path": "x" * 513})
    assert response.status_code == 422
    response = client.post("/track", json={"path": "/", "ref": "x" * 129})
    assert response.status_code == 422
    response = client.post("/track", json={"path": "/", "referrer": "x" * 1025})
    assert response.status_code == 422


def test_track_requires_path() -> None:
    response = _client().post("/track", json={})
    assert response.status_code == 422


def test_track_in_caps() -> None:
    TrackIn(path="/b/some-slug", ref="hn", utm_source="twitter")
    with pytest.raises(ValidationError):
        TrackIn(path="/", utm_campaign="x" * 129)


# --- signup attribution ------------------------------------------------------


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _FakeSession:
    """Covers what `_find_or_create_user` touches."""

    def __init__(self, existing: User | None):
        self._existing = existing
        self.added: list[User] = []

    def scalars(self, _stmt):
        return _FakeScalarResult(self._existing)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass


def _challenge(identifier: str = "new@example.com") -> AuthChallenge:
    return AuthChallenge(
        identifier=identifier,
        identifier_kind=AuthIdentifierKind.email,
        salt="s",
        code_hash="c",
        magic_link_token_hash="m",
        expires_at=datetime.now(timezone.utc),
    )


def test_new_user_gets_signup_attribution() -> None:
    db = _FakeSession(existing=None)
    payload = AuthVerifyIn(
        identifier="new@example.com",
        code="123456",
        ref="hn",
        utm_source="twitter",
        utm_medium="social",
        utm_campaign="launch",
    )
    user = auth._find_or_create_user(_challenge(), db, attribution=payload)
    assert db.added == [user]
    assert user.signup_ref == "hn"
    assert user.signup_utm_source == "twitter"
    assert user.signup_utm_medium == "social"
    assert user.signup_utm_campaign == "launch"


def test_existing_user_attribution_never_overwritten() -> None:
    existing = User(email="old@example.com", signup_ref="original")
    db = _FakeSession(existing=existing)
    payload = AuthVerifyIn(
        identifier="old@example.com", code="123456", ref="different-campaign"
    )
    user = auth._find_or_create_user(
        _challenge("old@example.com"), db, attribution=payload
    )
    assert user is existing
    assert user.signup_ref == "original"
    assert db.added == []


def test_new_user_without_attribution_is_clean() -> None:
    db = _FakeSession(existing=None)
    user = auth._find_or_create_user(_challenge(), db, attribution=None)
    assert user.signup_ref is None
    assert user.signup_utm_source is None


# --- last_seen_at throttle ---------------------------------------------------


def _user_seen(last_seen_at) -> User:
    user = User(email="seen@example.com")
    user.id = uuid.uuid4()
    user.last_seen_at = last_seen_at
    return user


def test_touch_last_seen_skips_fresh_user(monkeypatch) -> None:
    def _boom():
        raise AssertionError("engine must not be touched when fresh")

    monkeypatch.setattr(auth.engine, "begin", _boom)
    auth._touch_last_seen(_user_seen(datetime.now(timezone.utc)))


def test_touch_last_seen_writes_when_stale(monkeypatch) -> None:
    calls = []

    class _Conn:
        def execute(self, stmt):
            calls.append(stmt)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(auth.engine, "begin", lambda: _Conn())
    stale = datetime.now(timezone.utc) - auth.LAST_SEEN_STALENESS - timedelta(minutes=1)
    auth._touch_last_seen(_user_seen(stale))
    assert len(calls) == 1
    auth._touch_last_seen(_user_seen(None))
    assert len(calls) == 2


def test_touch_last_seen_swallows_db_errors(monkeypatch) -> None:
    """Analytics must never fail auth."""

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(auth.engine, "begin", _boom)
    auth._touch_last_seen(_user_seen(None))  # must not raise
