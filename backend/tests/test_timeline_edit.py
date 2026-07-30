"""Editing timeline events: the payload patch plus the occurred_at column.

Unit-level like the rest of the suite — schema shape and route auth gating;
the occurred_at handling itself is exercised against the schema contract.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from schemas import EditEventIn


def test_edit_event_in_accepts_occurred_at() -> None:
    payload = EditEventIn.model_validate(
        {"body": "corrected note", "occurred_at": "2026-04-08T02:14:00Z"}
    )
    assert payload.occurred_at == datetime(2026, 4, 8, 2, 14, tzinfo=timezone.utc)


def test_edit_event_in_occurred_at_defaults_to_absent() -> None:
    payload = EditEventIn.model_validate({"caption": "new caption"})
    # exclude_none is what the route relies on to distinguish "not sent"
    assert "occurred_at" not in payload.model_dump(exclude_none=True)


def test_edit_event_route_requires_auth() -> None:
    from main import app

    fake_id = "00000000-0000-0000-0000-000000000000"
    response = TestClient(app).patch(
        f"/birth/{fake_id}/event/{fake_id}", json={"body": "x"}
    )
    assert response.status_code == 401
