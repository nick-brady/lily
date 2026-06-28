"""Contraction stats for gift artwork — a small Python port of the subset
of `frontend/src/utils/statistics.js` the designs need.

We deliberately port only what the artwork renders (count, labor duration,
averages, and the ordered duration list for the sparkline), not the whole
stats module. The interval logic mirrors `StatsPanel.jsx`: skip a
contraction's interval when `ignore_interval_before` is set, and drop gaps
longer than 30 minutes (a break in labor).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models import Birth, TimelineEvent, TimelineEventType

_GAP_CAP_MINUTES = 30


@dataclass
class GiftStats:
    contraction_count: int
    labor_duration_seconds: int | None
    avg_contraction_seconds: float | None
    avg_interval_seconds: float | None
    durations: list[int] = field(default_factory=list)

    def as_metadata(self) -> dict:
        return {
            "contraction_count": self.contraction_count,
            "labor_duration_seconds": self.labor_duration_seconds,
            "avg_contraction_seconds": self.avg_contraction_seconds,
            "avg_interval_seconds": self.avg_interval_seconds,
            "durations": self.durations,
        }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def compute(birth: Birth, events: list[TimelineEvent]) -> GiftStats:
    """Compute artwork stats from a birth and its timeline events.

    `events` may contain any event type; only contractions are used. They
    are sorted by `occurred_at` so the sparkline and intervals are in
    chronological order regardless of input ordering.
    """
    contractions = sorted(
        (e for e in events if e.event_type == TimelineEventType.contraction),
        key=lambda e: e.occurred_at,
    )

    # Completed contractions = those with a recorded duration. Mirrors the
    # frontend's `c.end_time && c.duration_seconds` filter for stats.
    completed = [
        e for e in contractions if (e.payload or {}).get("duration_seconds")
    ]
    durations = [int((e.payload or {})["duration_seconds"]) for e in completed]

    avg_contraction = _mean([float(d) for d in durations])

    intervals_seconds: list[float] = []
    for prev, curr in zip(completed, completed[1:]):
        if (curr.payload or {}).get("ignore_interval_before"):
            continue
        gap_seconds = (curr.occurred_at - prev.occurred_at).total_seconds()
        if gap_seconds <= _GAP_CAP_MINUTES * 60:
            intervals_seconds.append(gap_seconds)
    avg_interval = _mean(intervals_seconds)

    labor_duration = _labor_duration_seconds(birth)

    return GiftStats(
        contraction_count=len(completed),
        labor_duration_seconds=labor_duration,
        avg_contraction_seconds=avg_contraction,
        avg_interval_seconds=avg_interval,
        durations=durations,
    )


def _labor_duration_seconds(birth: Birth) -> int | None:
    start: datetime | None = birth.birth_started_at
    end: datetime | None = birth.birth_completed_at
    if start is None or end is None:
        return None
    seconds = int((end - start).total_seconds())
    return seconds if seconds >= 0 else None
