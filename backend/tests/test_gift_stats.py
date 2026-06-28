"""Pin the Python contraction-stats port against a known fixture.

The port (gift_stats.py) mirrors a subset of frontend/src/utils/statistics.js;
this is the test that catches drift between the two.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import gift_stats
from models import TimelineEventType

T0 = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)


def _contraction(minutes_after: float, duration: int | None, *, ignore=False):
    return SimpleNamespace(
        event_type=TimelineEventType.contraction,
        occurred_at=T0 + timedelta(minutes=minutes_after),
        payload={
            "duration_seconds": duration,
            "ignore_interval_before": ignore,
        },
    )


def _birth(started, completed):
    return SimpleNamespace(birth_started_at=started, birth_completed_at=completed)


def test_basic_stats():
    events = [
        _contraction(0, 60),
        _contraction(5, 70),
        _contraction(10, 50),
    ]
    birth = _birth(T0, T0 + timedelta(hours=1))
    s = gift_stats.compute(birth, events)

    assert s.contraction_count == 3
    assert s.durations == [60, 70, 50]
    assert s.avg_contraction_seconds == 60
    # two 5-minute intervals
    assert s.avg_interval_seconds == 300
    assert s.labor_duration_seconds == 3600


def test_excludes_big_gaps_and_ignored_intervals():
    events = [
        _contraction(0, 60),
        _contraction(5, 60),  # +5 min  -> 300s interval (kept)
        _contraction(45, 60),  # +40 min -> gap > 30 min (excluded)
        _contraction(50, 60, ignore=True),  # ignore_interval_before (excluded)
    ]
    birth = _birth(T0, T0 + timedelta(hours=2))
    s = gift_stats.compute(birth, events)

    assert s.contraction_count == 4
    # only the single 300s interval survives the filters
    assert s.avg_interval_seconds == 300


def test_incomplete_contractions_and_unsorted_input():
    events = [
        _contraction(10, 50),  # out of order on purpose
        _contraction(0, 60),
        _contraction(5, None),  # no duration -> not "completed"
    ]
    birth = _birth(None, None)  # labor times missing
    s = gift_stats.compute(birth, events)

    # the duration-less contraction is excluded from completed/durations
    assert s.contraction_count == 2
    assert s.durations == [60, 50]  # sorted by occurred_at
    assert s.labor_duration_seconds is None


def test_no_contractions():
    s = gift_stats.compute(_birth(T0, T0 + timedelta(hours=1)), [])
    assert s.contraction_count == 0
    assert s.durations == []
    assert s.avg_contraction_seconds is None
    assert s.avg_interval_seconds is None
