"""Reactions on timeline events.

Toggling is idempotent: POST adds (or no-ops if already present), DELETE
removes (or no-ops if absent). The unique constraint on
(event_id, user_id, kind) does the heavy lifting; this module just wraps
it in a readable API.

The summary helper batches reaction lookups across an entire timeline page
so /timeline stays at a fixed number of queries regardless of event count.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models import ReactionKind, TimelineEventReaction


@dataclass(frozen=True)
class ReactionCount:
    count: int
    mine: bool


# Per-event summary: kind -> ReactionCount
ReactionSummary = dict[ReactionKind, ReactionCount]


def add_reaction(
    db: Session,
    *,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    kind: ReactionKind,
) -> bool:
    """Return True if a new row was inserted, False if it already existed.

    Uses ON CONFLICT DO NOTHING so concurrent toggles can't error.
    """
    stmt = (
        pg_insert(TimelineEventReaction)
        .values(event_id=event_id, user_id=user_id, kind=kind)
        .on_conflict_do_nothing(
            index_elements=["event_id", "user_id", "kind"]
        )
    )
    result = db.execute(stmt)
    db.flush()
    return result.rowcount > 0


def remove_reaction(
    db: Session,
    *,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    kind: ReactionKind,
) -> bool:
    """Return True if a row was removed, False if there was nothing to
    remove. Either way the post-condition (no reaction of this kind for
    this user on this event) holds.
    """
    result = db.execute(
        delete(TimelineEventReaction).where(
            TimelineEventReaction.event_id == event_id,
            TimelineEventReaction.user_id == user_id,
            TimelineEventReaction.kind == kind,
        )
    )
    db.flush()
    return result.rowcount > 0


def summarize_event(
    db: Session,
    *,
    event_id: uuid.UUID,
    requester_user_id: uuid.UUID | None,
) -> ReactionSummary:
    summaries = summarize_events(
        db, event_ids=[event_id], requester_user_id=requester_user_id
    )
    return summaries.get(event_id, {})


def summarize_events(
    db: Session,
    *,
    event_ids: list[uuid.UUID],
    requester_user_id: uuid.UUID | None,
) -> dict[uuid.UUID, ReactionSummary]:
    """Bulk-load reaction summaries keyed by event id.

    A single grouped query gives us count-per-kind; a second short query
    gives us the requester's own reactions so we can flag `mine`. The
    `mine` query is skipped when the requester is anonymous.
    """
    if not event_ids:
        return {}

    counts_rows = db.execute(
        select(
            TimelineEventReaction.event_id,
            TimelineEventReaction.kind,
            func.count().label("count"),
        )
        .where(TimelineEventReaction.event_id.in_(event_ids))
        .group_by(
            TimelineEventReaction.event_id,
            TimelineEventReaction.kind,
        )
    ).all()

    mine_keys: set[tuple[uuid.UUID, ReactionKind]] = set()
    if requester_user_id is not None:
        mine_rows = db.execute(
            select(
                TimelineEventReaction.event_id,
                TimelineEventReaction.kind,
            ).where(
                TimelineEventReaction.event_id.in_(event_ids),
                TimelineEventReaction.user_id == requester_user_id,
            )
        ).all()
        mine_keys = {(eid, kind) for eid, kind in mine_rows}

    result: dict[uuid.UUID, ReactionSummary] = defaultdict(dict)
    for event_id, kind, count in counts_rows:
        result[event_id][kind] = ReactionCount(
            count=int(count),
            mine=(event_id, kind) in mine_keys,
        )
    return dict(result)
