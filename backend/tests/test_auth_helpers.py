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
