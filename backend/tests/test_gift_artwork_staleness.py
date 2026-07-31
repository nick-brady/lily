"""The artwork's two timing rules.

Nothing renders until the story has had a few hours to settle, and anything
that changes what the artwork draws marks it stale so the next gallery view
re-renders it. Both exist because the birth time is posted once someone has a
free hand and is then corrected — and the measurements arrive later still.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from models import BirthStatus, GiftRenderingStatus
from repositories import gifts as gifts_repo


def _birth(*, status=BirthStatus.born, completed_at=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        birth_completed_at=completed_at,
    )


# ── the grace period ──────────────────────────────────────────────────────


def test_no_artwork_before_the_birth() -> None:
    birth = _birth(status=BirthStatus.preparing)
    assert gifts_repo.artwork_ready_at(birth) is None
    assert not gifts_repo.artwork_window_open(birth)


def test_no_artwork_in_the_hours_right_after_the_birth() -> None:
    """The regression: rendering fired at the Baby Born tap, so the keepsake
    captured the provisional arrival time and no measurements."""
    just_born = _birth(completed_at=datetime.now(timezone.utc) - timedelta(minutes=20))
    assert not gifts_repo.artwork_window_open(just_born)


def test_artwork_opens_once_the_grace_period_passes() -> None:
    settled = _birth(
        completed_at=datetime.now(timezone.utc)
        - gifts_repo.ARTWORK_GRACE_PERIOD
        - timedelta(minutes=1)
    )
    assert gifts_repo.artwork_window_open(settled)


def test_ready_at_is_the_arrival_plus_the_grace_period() -> None:
    completed = datetime(2026, 7, 30, 14, 38, tzinfo=timezone.utc)
    birth = _birth(completed_at=completed)
    assert gifts_repo.artwork_ready_at(birth) == completed + gifts_repo.ARTWORK_GRACE_PERIOD


def test_born_without_an_arrival_time_never_opens() -> None:
    """Defensive: mark_born always sets it, but a null must not be read as
    "the epoch", which would open the window immediately."""
    assert gifts_repo.artwork_ready_at(_birth(completed_at=None)) is None


# ── staleness ─────────────────────────────────────────────────────────────


class _FakeSession:
    """Just enough Session for mark_stale / ids_needing_render."""

    def __init__(self, rows):
        self._rows = rows
        self.committed = False

    def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: list(self._rows))

    def commit(self):
        self.committed = True


def _rendering(status):
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        failure_reason="boom" if status is GiftRenderingStatus.failed else None,
        artwork_s3_key="gifts/old.png",
        deleted_at=None,
    )


def test_mark_stale_flips_finished_rows_and_keeps_the_old_artwork() -> None:
    ready = _rendering(GiftRenderingStatus.ready)
    failed = _rendering(GiftRenderingStatus.failed)
    db = _FakeSession([ready, failed])

    assert gifts_repo.mark_stale(db, birth_id=uuid.uuid4()) == 2
    assert ready.status is GiftRenderingStatus.pending
    assert failed.status is GiftRenderingStatus.pending
    assert failed.failure_reason is None
    # The previous design stays visible, and a purchased order keeps a valid
    # print file, until the new render lands.
    assert ready.artwork_s3_key == "gifts/old.png"


def test_mark_stale_does_not_commit() -> None:
    """It composes into the caller's transaction — half-committing an edit
    that then fails would leave the artwork queued for a change that never
    happened."""
    db = _FakeSession([_rendering(GiftRenderingStatus.ready)])
    gifts_repo.mark_stale(db, birth_id=uuid.uuid4())
    assert db.committed is False


def test_mark_stale_leaves_in_flight_rows_alone() -> None:
    """An already-pending row is queued or rendering; re-flagging it would
    only make ids_needing_render hand it out twice."""
    pending = _rendering(GiftRenderingStatus.pending)
    db = _FakeSession([pending])
    assert gifts_repo.mark_stale(db, birth_id=uuid.uuid4()) == 0


def test_mark_stale_is_a_noop_with_no_renderings() -> None:
    """Which is what makes it safe to call from every timeline mutation,
    including all the pre-birth ones."""
    assert gifts_repo.mark_stale(_FakeSession([]), birth_id=uuid.uuid4()) == 0


def test_ids_needing_render_returns_only_pending() -> None:
    pending = _rendering(GiftRenderingStatus.pending)
    db = _FakeSession([pending, _rendering(GiftRenderingStatus.ready)])
    assert gifts_repo.ids_needing_render(db, birth_id=uuid.uuid4()) == [pending.id]


# ── the in-flight claim ───────────────────────────────────────────────────


def test_claim_renders_hands_out_each_id_once() -> None:
    """The gallery polls every 2.5s while anything is pending, so without this
    a slow render gets a second one started on top of it."""
    a, b = uuid.uuid4(), uuid.uuid4()
    try:
        assert gifts_repo.claim_renders([a, b]) == [a, b]
        assert gifts_repo.claim_renders([a, b]) == []
    finally:
        gifts_repo._release_render(a)
        gifts_repo._release_render(b)


def test_releasing_allows_a_later_re_render() -> None:
    rid = uuid.uuid4()
    assert gifts_repo.claim_renders([rid]) == [rid]
    gifts_repo._release_render(rid)
    try:
        assert gifts_repo.claim_renders([rid]) == [rid]
    finally:
        gifts_repo._release_render(rid)


def test_release_is_idempotent() -> None:
    """render_rendering releases in `finally`, which can run after an early
    return that never claimed."""
    gifts_repo._release_render(uuid.uuid4())
