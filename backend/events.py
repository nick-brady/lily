"""In-process pub/sub for SSE fan-out.

Single-process broker — when we scale to multiple backend instances, swap
this for Redis pub/sub (or NATS, etc.) behind the same `broadcast`/
`subscribe` interface. The shape of `BroadcastedEvent` stays the same.

Spec note: messages are notifications-with-payload. The viewer client could
re-fetch via `/birth/{id}/timeline?after_sequence_id=N` if it wanted, but
shipping the event inline keeps the round trips low for the v1 traffic
shape (a few hundred events per birth max).
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator


@dataclass
class BroadcastedEvent:
    sequence_id: int
    kind: str  # "appended" | "updated" | "deleted"
    payload: dict[str, Any]


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, list[asyncio.Queue[BroadcastedEvent]]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, birth_id: uuid.UUID, event: BroadcastedEvent) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(birth_id, ()))
        for queue in queues:
            # Non-blocking put: if a subscriber is too slow we drop their
            # event rather than back up the publisher. Subscribers can
            # reconnect with `Last-Event-ID` to catch up.
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    @asynccontextmanager
    async def subscribe(
        self, birth_id: uuid.UUID
    ) -> AsyncIterator[asyncio.Queue[BroadcastedEvent]]:
        queue: asyncio.Queue[BroadcastedEvent] = asyncio.Queue(maxsize=512)
        async with self._lock:
            self._subscribers.setdefault(birth_id, []).append(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                subscribers = self._subscribers.get(birth_id, [])
                if queue in subscribers:
                    subscribers.remove(queue)
                if not subscribers:
                    self._subscribers.pop(birth_id, None)


broker = EventBroker()


def serialize_event(event) -> dict[str, Any]:
    """Convert a TimelineEvent ORM row into a JSON-serializable dict for
    the SSE payload. Kept here (rather than in schemas.py) so the broker
    module is self-contained.
    """
    return {
        "id": str(event.id),
        "birth_id": str(event.birth_id),
        "event_type": event.event_type.value
        if hasattr(event.event_type, "value")
        else event.event_type,
        "sequence_id": event.sequence_id,
        "occurred_at": event.occurred_at.isoformat(),
        "posted_at": event.posted_at.isoformat(),
        "posted_by_user_id": str(event.posted_by_user_id),
        "payload": dict(event.payload),
        "audience_scope": event.audience_scope.value
        if hasattr(event.audience_scope, "value")
        else event.audience_scope,
    }


async def publish_event_change(birth_id: uuid.UUID, kind: str, event) -> None:
    await broker.publish(
        birth_id,
        BroadcastedEvent(
            sequence_id=event.sequence_id,
            kind=kind,
            payload=serialize_event(event),
        ),
    )


async def publish_event_deleted(birth_id: uuid.UUID, sequence_id: int, event_id: uuid.UUID) -> None:
    await broker.publish(
        birth_id,
        BroadcastedEvent(
            sequence_id=sequence_id,
            kind="deleted",
            payload={"id": str(event_id)},
        ),
    )


async def publish_reaction_change(
    birth_id: uuid.UUID,
    *,
    kind: str,  # "reaction_added" | "reaction_removed"
    event_id: uuid.UUID,
    reaction_kind: str,
    user_id: uuid.UUID,
) -> None:
    """Broadcast a reaction toggle. We don't carry an audience scope on
    these — the subscriber-side filter already ensures viewers won't
    receive reactions for events they couldn't see (because they never
    subscribed to those scopes), and the count refresh is cheap if a
    client misses one.

    `sequence_id` is intentionally negative so engagement events sort
    after timeline events and don't collide on `Last-Event-ID` replay.
    """
    await broker.publish(
        birth_id,
        BroadcastedEvent(
            sequence_id=-1,
            kind=kind,
            payload={
                "event_id": str(event_id),
                "kind": reaction_kind,
                "user_id": str(user_id),
            },
        ),
    )


async def publish_comment_change(
    birth_id: uuid.UUID,
    *,
    kind: str,  # "comment_added" | "comment_updated" | "comment_deleted"
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: str | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    payload: dict[str, Any] = {
        "event_id": str(event_id),
        "comment_id": str(comment_id),
    }
    if body is not None:
        payload["body"] = body
    if user_id is not None:
        payload["user_id"] = str(user_id)
    await broker.publish(
        birth_id,
        BroadcastedEvent(sequence_id=-1, kind=kind, payload=payload),
    )
