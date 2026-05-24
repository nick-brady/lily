"""Comments on timeline events.

Soft-deleted (not hard) — see `Lily-Personas.md` for the principle:
Janet's comment from labor day will be on her granddaughter's page when
she's 18. We never destroy what someone wrote during these hours; the
soft-delete is for recovery and audit, not for hiding family memory.

The unlock gate (`birth.is_unlocked`) is enforced one layer up at the
route. Repositories don't reach across to other entities.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import TimelineEventComment


def create_comment(
    db: Session,
    *,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    body: str,
) -> TimelineEventComment:
    comment = TimelineEventComment(
        event_id=event_id,
        user_id=user_id,
        body=body,
    )
    db.add(comment)
    db.flush()
    return comment


def get_comment(db: Session, comment_id: uuid.UUID) -> TimelineEventComment | None:
    return db.get(TimelineEventComment, comment_id)


def list_for_event(
    db: Session,
    *,
    event_id: uuid.UUID,
    after: datetime | None = None,
    limit: int = 200,
) -> list[TimelineEventComment]:
    stmt = (
        select(TimelineEventComment)
        .where(
            TimelineEventComment.event_id == event_id,
            TimelineEventComment.deleted_at.is_(None),
        )
        .order_by(TimelineEventComment.created_at.asc())
        .limit(limit)
    )
    if after is not None:
        stmt = stmt.where(TimelineEventComment.created_at > after)
    return list(db.scalars(stmt).all())


def edit_body(
    db: Session, comment: TimelineEventComment, body: str
) -> TimelineEventComment:
    comment.body = body
    db.flush()
    return comment


def soft_delete(db: Session, comment: TimelineEventComment) -> None:
    comment.deleted_at = datetime.now(timezone.utc)
    db.flush()


def counts_for_events(
    db: Session, *, event_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not event_ids:
        return {}
    rows = db.execute(
        select(
            TimelineEventComment.event_id,
            func.count().label("count"),
        )
        .where(
            TimelineEventComment.event_id.in_(event_ids),
            TimelineEventComment.deleted_at.is_(None),
        )
        .group_by(TimelineEventComment.event_id)
    ).all()
    return {event_id: int(count) for event_id, count in rows}
