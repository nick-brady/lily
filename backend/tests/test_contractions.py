"""Two parents, one button.

Both of them watch the same page during labour and neither knows who is
going to press it, so sometimes they both do within the same second. These
pin what the server does about that — the rules live in routes/timeline.py
and, for the one that must never be violated, in the partial unique index.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from routes import timeline as timeline_routes


NOW = datetime(2026, 8, 30, 3, 15, tzinfo=timezone.utc)


def _running(started_seconds_ago: float):
    """A contraction that began `started_seconds_ago` before NOW."""
    from types import SimpleNamespace
    from models import TimelineEventType

    return SimpleNamespace(
        id=uuid.uuid4(),
        birth_id=uuid.uuid4(),
        event_type=TimelineEventType.contraction,
        occurred_at=NOW - timedelta(seconds=started_seconds_ago),
        payload={"type": "contraction", "end_time": None, "duration_seconds": None},
    )


# ── the windows ────────────────────────────────────────────────────────────


def test_the_windows_are_ordered_and_clear_the_shortest_real_contraction():
    """The grace window has to be inside the confirm window, and the confirm
    window has to end before any contraction a person actually had. The
    recorded ones here run 14–101 seconds, so 10 leaves room."""
    assert 0 < timeline_routes.CONTRACTION_GRACE_SECONDS
    assert (
        timeline_routes.CONTRACTION_GRACE_SECONDS
        < timeline_routes.CONTRACTION_CONFIRM_SECONDS
    )
    assert timeline_routes.CONTRACTION_CONFIRM_SECONDS < 14


@pytest.mark.parametrize(
    "age, outcome",
    [
        (0.0, "ignore"),   # both thumbs landed together
        (2.0, "ignore"),   # their partner was quicker; nothing said so yet
        (4.9, "ignore"),
        (5.0, "ask"),      # possible, but nobody times a five-second contraction
        (9.9, "ask"),
        (10.0, "stop"),
        (45.0, "stop"),    # an ordinary one
        (101.0, "stop"),   # the longest actually recorded here
    ],
)
def test_what_a_stop_means_at_each_age(age, outcome):
    grace = timeline_routes.CONTRACTION_GRACE_SECONDS
    confirm = timeline_routes.CONTRACTION_CONFIRM_SECONDS
    got = "ignore" if age < grace else "ask" if age < confirm else "stop"
    assert got == outcome


# ── the invariant ──────────────────────────────────────────────────────────


def test_one_open_contraction_per_birth_is_enforced_by_the_database():
    """Not by the route. Two taps can both pass a check; only the index can
    make the outcome singular."""
    from models import TimelineEvent

    index = next(
        arg
        for arg in TimelineEvent.__table_args__
        if getattr(arg, "name", None) == "uq_timeline_events_one_open_contraction"
    )
    assert index.unique
    assert [c.name for c in index.columns] == ["birth_id"]
    where = str(index.dialect_options["postgresql"]["where"])
    # scoped to contractions that are live and unfinished — a stopped one, or
    # a discarded one, must never block the next
    assert "event_type = 'contraction'" in where
    assert "deleted_at IS NULL" in where
    assert "end_time" in where


def test_the_running_contraction_query_ignores_finished_and_discarded_ones():
    import inspect

    from repositories import timeline as timeline_repo

    src = inspect.getsource(timeline_repo.running_contraction)
    assert "deleted_at" in src and "end_time" in src
    assert "TimelineEventType.contraction" in src


# ── the shape of the refusal ───────────────────────────────────────────────


def test_the_refusal_tells_the_client_what_to_say():
    """The dialog needs to name the number of seconds, so the code carries it
    rather than the client guessing from its own clock."""
    import inspect

    src = inspect.getsource(timeline_routes.stop_contraction)
    assert '"code": "just_started"' in src
    assert '"started_seconds_ago"' in src
    assert "status_code=409" in src


def test_a_repeated_stop_is_the_same_request_not_an_error():
    """A retry, a second tap, a reconnect. It used to answer 400 and put a red
    banner in front of someone in labour."""
    import inspect

    src = inspect.getsource(timeline_routes.stop_contraction)
    assert "Contraction already stopped" not in src


def test_both_ends_of_a_contraction_are_stamped_on_one_clock():
    """The end time used to come from the phone, so a duration was `their now
    minus our start` — every record carried the skew between two devices, and
    a phone running behind wrote a negative duration onto a keepsake."""
    import inspect

    src = inspect.getsource(timeline_routes.stop_contraction)
    assert "now = datetime.now(timezone.utc)" in src
    assert '"end_time": now.isoformat()' in src
    assert "payload.end_time" not in src


def test_a_second_start_joins_the_running_one_and_never_inserts():
    import inspect

    src = inspect.getsource(timeline_routes.start_contraction)
    # asked before anything is written
    assert src.index("running_contraction") < src.index("append_event")
    # and the losing side of a genuine race is handed the winner's
    assert "IntegrityError" in src
    assert src.count("serialize_event_out(running)") == 2
