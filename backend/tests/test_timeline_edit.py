"""Editing timeline events: the payload patch plus the occurred_at column.

Unit-level like the rest of the suite — schema shape and route auth gating;
the occurred_at handling itself is exercised against the schema contract.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
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


# ── the future bound ──────────────────────────────────────────────────────
# Backdating is the whole point of the feature; forward-dating is never
# legitimate, and a future-stamped event pins itself above the story forever.


def _future(**kwargs) -> str:
    return (datetime.now(timezone.utc) + timedelta(**kwargs)).isoformat()


def _past(**kwargs) -> str:
    return (datetime.now(timezone.utc) - timedelta(**kwargs)).isoformat()


def test_edit_event_in_rejects_a_future_time() -> None:
    with pytest.raises(ValueError):
        EditEventIn.model_validate({"occurred_at": _future(days=148)})


def test_occurred_at_bound_covers_every_creator() -> None:
    """One validator on the shared type, so no creator can drift out of it."""
    from schemas import (
        BabyBornIn,
        CreateMilestoneIn,
        CreateTextNoteIn,
        StartContractionIn,
        StopContractionIn,
    )

    cases = [
        (CreateTextNoteIn, {"body": "hi"}, "occurred_at"),
        (CreateMilestoneIn, {"kind": "arrived"}, "occurred_at"),
        (StartContractionIn, {}, "occurred_at"),
        (BabyBornIn, {}, "occurred_at"),
        # a contraction that ends in the future would over-report its duration
        (StopContractionIn, {}, "end_time"),
    ]
    for model, base, field in cases:
        with pytest.raises(ValueError):
            model.model_validate({**base, field: _future(hours=3)})
        # the same shape an hour ago is fine
        model.model_validate({**base, field: _past(hours=1)})


def test_clock_skew_is_tolerated() -> None:
    """A client clock a minute fast must not have its own "now" rejected."""
    EditEventIn.model_validate({"occurred_at": _future(seconds=45)})


def test_naive_datetime_is_treated_as_utc() -> None:
    """Comparing naive against aware raises, so the validator normalises
    rather than blowing up with a TypeError."""
    naive_future = (datetime.now(timezone.utc) + timedelta(days=2)).replace(tzinfo=None)
    with pytest.raises(ValueError):
        EditEventIn.model_validate({"occurred_at": naive_future.isoformat()})


# ── the Born milestone's clocks ───────────────────────────────────────────


def _born_event(birth_id: uuid.UUID, occurred_at: datetime):
    from models import TimelineEventType

    return SimpleNamespace(
        id=uuid.uuid4(),
        birth_id=birth_id,
        event_type=TimelineEventType.milestone,
        payload={"type": "milestone", "kind": "born"},
        occurred_at=occurred_at,
        deleted_at=None,
    )


async def _edit(monkeypatch, *, birth, event, new_time):
    """Drive edit_event with the repo, broker and serializer stubbed out."""
    from routes import timeline

    monkeypatch.setattr(timeline.timeline_repo, "get_event", lambda db, _id: event)
    monkeypatch.setattr(timeline, "serialize_event_with_engagement", lambda *a, **k: None)
    # Editing marks the birth's gift artwork stale; that's covered in
    # test_gift_artwork_staleness, and it needs a real session.
    monkeypatch.setattr(timeline.gifts_repo, "mark_stale", lambda db, **kw: 0)

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(timeline, "publish_event_change", noop)
    monkeypatch.setattr(timeline, "publish_birth_update", noop)

    db = SimpleNamespace(commit=lambda: None, refresh=lambda _obj: None)
    access = SimpleNamespace(birth=birth, role=None, user=None)
    await timeline.edit_event(
        event_id=event.id,
        payload=EditEventIn(occurred_at=new_time),
        access=access,
        current_user=SimpleNamespace(id=uuid.uuid4()),
        db=db,
    )


def test_born_edit_moves_completed_but_never_labor_start(monkeypatch) -> None:
    """The regression this replaces: dragging birth_started_at back to equal
    the new arrival time reported a 0-minute labor and destroyed the recorded
    first-contraction time, with no undo."""
    labor_start = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)
    birth = SimpleNamespace(
        id=uuid.uuid4(),
        birth_started_at=labor_start,
        birth_completed_at=datetime(2026, 7, 30, 14, 54, tzinfo=timezone.utc),
    )
    event = _born_event(birth.id, birth.birth_completed_at)

    # the normal correction: posted at 14:54, actually arrived 14:38
    corrected = datetime(2026, 7, 30, 14, 38, tzinfo=timezone.utc)
    asyncio.run(_edit(monkeypatch, birth=birth, event=event, new_time=corrected))
    assert birth.birth_completed_at == corrected
    assert birth.birth_started_at == labor_start

    # and the nonsense one: an arrival before labor began leaves the real
    # labor start intact rather than collapsing the interval to zero
    bogus = datetime(2026, 7, 30, 6, 0, tzinfo=timezone.utc)
    asyncio.run(_edit(monkeypatch, birth=birth, event=event, new_time=bogus))
    assert birth.birth_completed_at == bogus
    assert birth.birth_started_at == labor_start


def test_labor_duration_reads_unknown_not_zero() -> None:
    """Downstream consequence of leaving birth_started_at alone: a negative
    interval is already filtered to None, so a wrong arrival time yields
    "unknown" rather than a confident, wrong "0m of labor"."""
    from gift_stats import _labor_duration_seconds

    birth = SimpleNamespace(
        birth_started_at=datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc),
        birth_completed_at=datetime(2026, 7, 30, 6, 0, tzinfo=timezone.utc),
    )
    assert _labor_duration_seconds(birth) is None
