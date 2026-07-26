"""Timeline-event serialization shared by the timeline and engagement routes."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from models import ReactionKind, TimelineEvent
from repositories import comments as comments_repo
from repositories import reactions as reactions_repo
from schemas import ReactionCountOut, TimelineEventOut


def serialize_event_out(
    e: TimelineEvent,
    *,
    reactions: dict[ReactionKind, reactions_repo.ReactionCount] | None = None,
    comment_count: int = 0,
) -> TimelineEventOut:
    reactions_out: dict[ReactionKind, ReactionCountOut] = {}
    if reactions:
        reactions_out = {
            kind: ReactionCountOut(count=summary.count, mine=summary.mine)
            for kind, summary in reactions.items()
        }
    return TimelineEventOut(
        id=e.id,
        birth_id=e.birth_id,
        event_type=e.event_type,
        sequence_id=e.sequence_id,
        occurred_at=e.occurred_at,
        posted_at=e.posted_at,
        posted_by_user_id=e.posted_by_user_id,
        payload=dict(e.payload),
        audience_scope=e.audience_scope,
        reactions=reactions_out,
        comment_count=comment_count,
    )


def serialize_events_with_engagement(
    db: Session,
    events: list[TimelineEvent],
    *,
    requester_user_id: uuid.UUID | None,
) -> list[TimelineEventOut]:
    """Two bulk queries (reactions + comment counts) decorate the whole
    page. Constant query count regardless of how many events are listed.
    """
    if not events:
        return []
    event_ids = [e.id for e in events]
    reactions_map = reactions_repo.summarize_events(
        db, event_ids=event_ids, requester_user_id=requester_user_id
    )
    comment_counts = comments_repo.counts_for_events(db, event_ids=event_ids)
    return [
        serialize_event_out(
            e,
            reactions=reactions_map.get(e.id),
            comment_count=comment_counts.get(e.id, 0),
        )
        for e in events
    ]


def serialize_event_with_engagement(
    db: Session,
    event: TimelineEvent,
    *,
    requester_user_id: uuid.UUID | None,
) -> TimelineEventOut:
    return serialize_events_with_engagement(
        db, [event], requester_user_id=requester_user_id
    )[0]
