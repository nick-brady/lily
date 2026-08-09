"""Birth lifecycle: preparing -> in_labor -> born.

Repo helpers are tested against plain ORM instances (no real DB, matching
the rest of the unit suite); the route is checked for auth gating.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from models import Birth, BirthStatus
from repositories import births as births_repo


class _FlushOnly:
    """A session stand-in for helpers that only mutate-and-flush."""

    def flush(self) -> None:
        pass


def _birth(status: BirthStatus) -> Birth:
    return Birth(
        family_id=uuid.uuid4(),
        child_name="Lily",
        slug="lily",
        status=status,
    )


def test_begin_labor_transitions_from_preparing() -> None:
    birth = _birth(BirthStatus.preparing)
    when = datetime(2026, 4, 8, tzinfo=timezone.utc)

    assert births_repo.begin_labor(_FlushOnly(), birth=birth, when=when) is True
    assert birth.status is BirthStatus.in_labor
    assert birth.birth_started_at == when


def test_begin_labor_is_noop_once_in_labor() -> None:
    birth = _birth(BirthStatus.in_labor)
    started = datetime(2026, 4, 8, tzinfo=timezone.utc)
    birth.birth_started_at = started

    assert births_repo.begin_labor(_FlushOnly(), birth=birth, when=datetime.now(timezone.utc)) is False
    assert birth.status is BirthStatus.in_labor
    assert birth.birth_started_at == started  # unchanged


def test_mark_born_records_arrival_and_backfills_start() -> None:
    birth = _birth(BirthStatus.in_labor)  # never saw a contraction
    when = datetime(2026, 4, 8, 4, 47, tzinfo=timezone.utc)

    births_repo.mark_born(_FlushOnly(), birth=birth, when=when)

    assert birth.status is BirthStatus.born
    assert birth.birth_completed_at == when
    assert birth.birth_started_at == when  # backfilled since none was set


def test_unmark_born_resumes_labor_and_keeps_the_recorded_start() -> None:
    """Labor was really observed, so `in_labor` is where undoing lands and
    the first-contraction time survives — it's an observation, not an
    inference."""
    birth = _birth(BirthStatus.born)
    labor_start = datetime(2026, 4, 8, 1, 10, tzinfo=timezone.utc)
    birth.birth_started_at = labor_start
    birth.birth_completed_at = datetime(2026, 4, 8, 4, 47, tzinfo=timezone.utc)

    births_repo.unmark_born(_FlushOnly(), birth=birth, resume_labor=True)

    assert birth.status is BirthStatus.in_labor
    assert birth.birth_completed_at is None
    assert birth.birth_started_at == labor_start


def test_unmark_born_clears_the_start_mark_born_invented() -> None:
    """No contraction was ever recorded, so `mark_born` backfilled the start
    from the arrival time. Undoing has to take that with it — otherwise the
    page returns to `preparing` claiming a labor that never happened."""
    birth = _birth(BirthStatus.born)
    when = datetime(2026, 4, 8, 4, 47, tzinfo=timezone.utc)
    births_repo.mark_born(_FlushOnly(), birth=birth, when=when)
    assert birth.birth_started_at == when  # the inference we're undoing

    births_repo.unmark_born(_FlushOnly(), birth=birth, resume_labor=False)

    assert birth.status is BirthStatus.preparing
    assert birth.birth_completed_at is None
    assert birth.birth_started_at is None


def test_born_route_requires_auth() -> None:
    from main import app

    fake_id = "00000000-0000-0000-0000-000000000000"
    response = TestClient(app).post(f"/birth/{fake_id}/born")
    assert response.status_code == 401
