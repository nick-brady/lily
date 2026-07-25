"""Pure-function tests for auth helpers.

Anything that touches the database is exercised manually per the README's
auth-flow walk-through. These tests cover the bits that are easy to unit
test in isolation: identifier normalization, hashing determinism, and JWT
round-trips.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import auth
from models import AuthIdentifierKind


def test_normalize_email_lowercases_and_strips() -> None:
    identifier, kind = auth.normalize_identifier("  Nick@Example.COM ")
    assert identifier == "nick@example.com"
    assert kind is AuthIdentifierKind.email


def test_normalize_invalid_email_raises_400() -> None:
    with pytest.raises(HTTPException) as excinfo:
        auth.normalize_identifier("not-an-email@")
    assert excinfo.value.status_code == 400


def test_normalize_us_phone_10_digits_gets_country_code() -> None:
    identifier, kind = auth.normalize_identifier("(555) 123-4567")
    assert identifier == "+15551234567"
    assert kind is AuthIdentifierKind.phone


def test_normalize_us_phone_with_leading_1() -> None:
    identifier, kind = auth.normalize_identifier("1-555-123-4567")
    assert identifier == "+15551234567"
    assert kind is AuthIdentifierKind.phone


def test_normalize_international_phone_with_plus() -> None:
    identifier, kind = auth.normalize_identifier("+44 7700 900123")
    assert identifier == "+447700900123"
    assert kind is AuthIdentifierKind.phone


def test_normalize_garbage_raises_400() -> None:
    with pytest.raises(HTTPException) as excinfo:
        auth.normalize_identifier("abc")
    assert excinfo.value.status_code == 400


def test_hash_is_deterministic_with_salt() -> None:
    assert auth._hash("salt-x", "value") == auth._hash("salt-x", "value")
    assert auth._hash("salt-x", "value") != auth._hash("salt-y", "value")


def test_random_code_is_six_digits() -> None:
    for _ in range(50):
        code = auth._random_code()
        assert len(code) == 6
        assert code.isdigit()


def test_jwt_round_trip() -> None:
    import uuid

    user_id = uuid.uuid4()
    token = auth._create_access_token(user_id)
    decoded = auth._decode_access_token(token)
    assert decoded == user_id


def test_jwt_invalid_signature_returns_none() -> None:
    assert auth._decode_access_token("not.a.token") is None
    assert auth._decode_access_token("") is None

# ── Cookie sessions (2026-07-23 auth decision) ────────────────────────────


def test_session_cookie_is_httponly_lax_and_long_lived() -> None:
    from fastapi import Response

    response = Response()
    auth.apply_session_cookie(response, "token-value")
    header = response.headers["set-cookie"]
    assert f"{auth.SESSION_COOKIE_NAME}=token-value" in header
    # httpOnly is the point: Safari's ITP purges script-writable storage
    # after ~7 days; httpOnly cookies survive.
    assert "HttpOnly" in header
    assert "SameSite=lax" in header.replace("samesite", "SameSite")
    assert f"Max-Age={int(auth.SESSION_TTL.total_seconds())}" in header


def test_clear_session_cookie_expires_it() -> None:
    from fastapi import Response

    response = Response()
    auth.clear_session_cookie(response)
    header = response.headers["set-cookie"]
    assert f'{auth.SESSION_COOKIE_NAME}=""' in header


def test_refreshed_session_token_slides_old_sessions() -> None:
    import uuid
    from datetime import datetime, timedelta, timezone

    from jose import jwt as jose_jwt

    user_id = uuid.uuid4()
    old_iat = datetime.now(timezone.utc) - auth.SESSION_REFRESH_AFTER - timedelta(hours=1)
    stale = jose_jwt.encode(
        {"sub": str(user_id), "iat": old_iat, "exp": old_iat + auth.SESSION_TTL},
        auth.JWT_SECRET_KEY,
        algorithm=auth.JWT_ALGORITHM,
    )
    fresh = auth.refreshed_session_token(stale)
    assert fresh is not None
    assert auth._decode_access_token(fresh) == user_id


def test_refreshed_session_token_leaves_recent_sessions_alone() -> None:
    import uuid

    token = auth._create_access_token(uuid.uuid4())
    assert auth.refreshed_session_token(token) is None


def test_refreshed_session_token_rejects_garbage() -> None:
    assert auth.refreshed_session_token("not.a.token") is None
    assert auth.refreshed_session_token("") is None


def test_request_challenge_rejects_phone_identifiers() -> None:
    # Identity is email; the rejection happens before any DB access.
    from schemas import AuthRequestIn

    with pytest.raises(HTTPException) as excinfo:
        auth.request_challenge(AuthRequestIn(identifier="(555) 123-4567"), db=None)
    assert excinfo.value.status_code == 400
    assert "email" in excinfo.value.detail.lower()
