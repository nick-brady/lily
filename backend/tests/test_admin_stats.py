"""Tests for admin authorization and the overview assembly.

No real database (house style): the allowlist dependency is tested
directly, and `overview_stats` is tested with the repository layer
monkeypatched — the SQL itself is exercised in local end-to-end
verification against postgres.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import admin
from models import User
from repositories import stats as stats_repo


def _client() -> TestClient:
    from main import app

    return TestClient(app)


# --- authorization -----------------------------------------------------------


def test_overview_requires_auth() -> None:
    response = _client().get("/admin/stats/overview")
    assert response.status_code == 401


def test_get_admin_user_rejects_non_admin(monkeypatch) -> None:
    monkeypatch.setattr(admin, "ADMIN_EMAILS", {"admin@example.com"})
    with pytest.raises(HTTPException) as exc:
        admin.get_admin_user(User(email="visitor@example.com"))
    assert exc.value.status_code == 403


def test_get_admin_user_rejects_phone_only_user(monkeypatch) -> None:
    monkeypatch.setattr(admin, "ADMIN_EMAILS", {"admin@example.com"})
    with pytest.raises(HTTPException) as exc:
        admin.get_admin_user(User(email=None, phone="+15555550100"))
    assert exc.value.status_code == 403


def test_get_admin_user_accepts_allowlisted(monkeypatch) -> None:
    monkeypatch.setattr(admin, "ADMIN_EMAILS", {"admin@example.com"})
    user = User(email="admin@example.com")
    assert admin.get_admin_user(user) is user


def test_get_admin_user_is_case_insensitive(monkeypatch) -> None:
    monkeypatch.setattr(admin, "ADMIN_EMAILS", {"admin@example.com"})
    user = User(email="Admin@Example.com")
    assert admin.get_admin_user(user) is user


def test_empty_allowlist_rejects_everyone(monkeypatch) -> None:
    monkeypatch.setattr(admin, "ADMIN_EMAILS", set())
    with pytest.raises(HTTPException):
        admin.get_admin_user(User(email="anyone@example.com"))


def test_admin_emails_parsing() -> None:
    parsed = {
        e.strip().lower()
        for e in " Nick@natrx.io , second@example.com ,, ".split(",")
        if e.strip()
    }
    assert parsed == {"nick@natrx.io", "second@example.com"}


# --- overview assembly (repositories monkeypatched) --------------------------


class _Row:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def stubbed_stats(monkeypatch):
    monkeypatch.setattr(
        stats_repo,
        "signups_by_day",
        lambda db, s, e: [_Row(day=date(2026, 7, 14), count=3)],
    )
    monkeypatch.setattr(
        stats_repo,
        "signups_by_source",
        lambda db, s, e: [_Row(source="hn", count=2), _Row(source="direct", count=1)],
    )
    monkeypatch.setattr(
        stats_repo,
        "visits_by_day_by_source",
        lambda db, s, e: [_Row(day=date(2026, 7, 14), source="hn", count=40)],
    )
    monkeypatch.setattr(
        stats_repo,
        "visits_by_source",
        lambda db, s, e: [_Row(source="hn", count=40), _Row(source="direct", count=10)],
    )
    monkeypatch.setattr(stats_repo, "activation", lambda db, s, e: (2, 3))
    monkeypatch.setattr(
        stats_repo,
        "invite_stats",
        lambda db, s, e: {
            "created": 5,
            "redemptions": 9,
            "distinct_redeemers": 7,
            "link_visits": 12,
        },
    )
    monkeypatch.setattr(
        stats_repo, "redeemer_owner_conversion", lambda db: (1, 7)
    )
    monkeypatch.setattr(stats_repo, "active_users", lambda db, now: (4, 11))
    monkeypatch.setattr(
        stats_repo,
        "revenue",
        lambda db, s, e: {
            "unlock_count": 2,
            "unlock_cents": 2400,
            "gift_count": 1,
            "gift_cents": 3500,
        },
    )


def test_overview_assembles_all_blocks(stubbed_stats) -> None:
    out = admin.overview_stats(None, date(2026, 7, 1), date(2026, 7, 14))
    assert out.start_date == date(2026, 7, 1)
    assert out.end_date == date(2026, 7, 14)
    assert out.signups.total == 3
    assert out.signups.by_source[0].source == "hn"
    assert out.visits.total == 50  # summed from by_source
    assert out.activation.rate == pytest.approx(2 / 3)
    assert out.invites.redemptions == 9
    assert out.conversion.rate == pytest.approx(1 / 7)
    assert out.active_users.wau == 11
    assert out.revenue.total_cents == 5900


def test_overview_defaults_to_last_30_days(stubbed_stats) -> None:
    out = admin.overview_stats(None, None, None)
    today = datetime.now(timezone.utc).date()
    assert out.end_date == today
    assert (out.end_date - out.start_date).days == admin.DEFAULT_RANGE_DAYS - 1


def test_overview_rejects_inverted_range(stubbed_stats) -> None:
    with pytest.raises(HTTPException) as exc:
        admin.overview_stats(None, date(2026, 7, 14), date(2026, 7, 1))
    assert exc.value.status_code == 400


def test_zero_denominators_yield_none_rates(stubbed_stats, monkeypatch) -> None:
    monkeypatch.setattr(stats_repo, "activation", lambda db, s, e: (0, 0))
    monkeypatch.setattr(stats_repo, "redeemer_owner_conversion", lambda db: (0, 0))
    out = admin.overview_stats(None, None, None)
    assert out.activation.rate is None
    assert out.conversion.rate is None
