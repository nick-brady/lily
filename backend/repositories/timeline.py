"""Timeline event reads + appends.

`sequence_id` is computed inside the same transaction as the insert using
`MAX(sequence_id) + 1 WHERE birth_id = :id`. The unique index on
(birth_id, sequence_id) protects against concurrent inserts at the cost of
forcing one writer to retry — acceptable for the v1 traffic shape.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AudienceScope, TimelineEvent, TimelineEventType


def next_sequence_id(db: Session, birth_id: uuid.UUID) -> int:
    current = db.scalar(
        select(func.coalesce(func.max(TimelineEvent.sequence_id), 0)).where(
            TimelineEvent.birth_id == birth_id
        )
    )
    return int(current) + 1


def append_event(
    db: Session,
    *,
    birth_id: uuid.UUID,
    event_type: TimelineEventType,
    payload: dict[str, Any],
    posted_by_user_id: uuid.UUID,
    occurred_at: datetime | None = None,
    audience_scope: AudienceScope = AudienceScope.group_targeted,
    sequence_id: int | None = None,
) -> TimelineEvent:
    now = datetime.now(timezone.utc)
    event = TimelineEvent(
        birth_id=birth_id,
        event_type=event_type,
        sequence_id=sequence_id if sequence_id is not None else next_sequence_id(db, birth_id),
        occurred_at=occurred_at or now,
        posted_at=now,
        posted_by_user_id=posted_by_user_id,
        payload=payload,
        audience_scope=audience_scope,
    )
    db.add(event)
    db.flush()
    return event


def get_event(db: Session, event_id: uuid.UUID) -> TimelineEvent | None:
    return db.get(TimelineEvent, event_id)


def list_events(
    db: Session,
    *,
    birth_id: uuid.UUID,
    after_sequence_id: int | None = None,
    limit: int = 500,
    audience_scopes: "frozenset[AudienceScope] | set[AudienceScope] | None" = None,
) -> list[TimelineEvent]:
    stmt = (
        select(TimelineEvent)
        .where(
            TimelineEvent.birth_id == birth_id,
            TimelineEvent.deleted_at.is_(None),
        )
        .order_by(TimelineEvent.sequence_id.asc())
        .limit(limit)
    )
    if after_sequence_id is not None:
        stmt = stmt.where(TimelineEvent.sequence_id > after_sequence_id)
    if audience_scopes is not None:
        stmt = stmt.where(TimelineEvent.audience_scope.in_(audience_scopes))
    return list(db.scalars(stmt).all())


def update_payload(
    db: Session, event: TimelineEvent, patch: dict[str, Any]
) -> TimelineEvent:
    merged = {**event.payload, **patch}
    event.payload = merged
    db.flush()
    return event
