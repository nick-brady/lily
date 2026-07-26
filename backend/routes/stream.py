"""SSE streams: `/birth/{id}/stream` for members, `/b/{slug}/stream` for
the public page. Replay-then-subscribe with `Last-Event-ID` resume."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user_stream
from db import get_db
from events import broker, serialize_event
from models import AudienceScope, TimelineEvent, User
from repositories import births as births_repo
from routes.deps import resolve_public_birth, scope_set_for_visitor

router = APIRouter()

SSE_HEARTBEAT_SECONDS = 15


@router.get("/birth/{birth_id}/stream")
async def stream_birth(
    request: Request,
    birth_id: uuid.UUID,
    current_user: User = Depends(get_current_user_stream),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    birth = births_repo.get_birth(db, birth_id)
    if birth is None or birth.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Birth not found")
    role = births_repo.user_role_for_birth(db, user_id=current_user.id, birth=birth)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this family")
    visible = births_repo.visible_scopes_for_role(role)
    # Parents see everything, so skip filtering entirely.
    visible_arg = None if visible == frozenset(AudienceScope) else visible
    after = _parse_last_event_id(last_event_id)
    return StreamingResponse(
        _sse_generator(request, birth.id, after, db, visible_arg),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )


@router.get("/b/{slug}/stream")
async def stream_public(
    request: Request,
    slug: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    current_user: User = Depends(get_current_user_stream),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    birth = resolve_public_birth(db, slug)
    visible = scope_set_for_visitor(db, birth, current_user)
    visible_arg = None if visible == frozenset(AudienceScope) else visible
    after = _parse_last_event_id(last_event_id)
    return StreamingResponse(
        _sse_generator(request, birth.id, after, db, visible_arg),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )


def _sse_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }


def _parse_last_event_id(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _format_sse(*, event: str, data: dict, sequence_id: int | None = None) -> bytes:
    lines = []
    if sequence_id is not None:
        lines.append(f"id: {sequence_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, default=str)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


async def _sse_generator(
    request: Request,
    birth_id: uuid.UUID,
    after_sequence_id: int | None,
    db: Session,
    visible_scopes: frozenset[AudienceScope] | None = None,
) -> AsyncIterator[bytes]:
    """Generic SSE stream filtered to a set of audience scopes.

    Passing `visible_scopes=None` means no filter (used by parents who
    can see everything). The replay-then-subscribe pattern lets clients
    resume with `Last-Event-ID`.
    """
    # Replay anything the client missed since `after_sequence_id`.
    stmt = (
        select(TimelineEvent)
        .where(
            TimelineEvent.birth_id == birth_id,
            TimelineEvent.deleted_at.is_(None),
        )
        .order_by(TimelineEvent.sequence_id.asc())
    )
    if after_sequence_id is not None:
        stmt = stmt.where(TimelineEvent.sequence_id > after_sequence_id)
    if visible_scopes is not None:
        stmt = stmt.where(TimelineEvent.audience_scope.in_(visible_scopes))
    for event in db.scalars(stmt).all():
        yield _format_sse(
            event="appended",
            data=serialize_event(event),
            sequence_id=event.sequence_id,
        )

    yield _format_sse(event="open", data={"birth_id": str(birth_id)})

    visible_values: set[str] | None = (
        {s.value for s in visible_scopes} if visible_scopes is not None else None
    )

    async with broker.subscribe(birth_id) as queue:
        while True:
            if await request.is_disconnected():
                return
            try:
                event = await asyncio.wait_for(queue.get(), timeout=SSE_HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield b": heartbeat\n\n"
                continue
            # Audience filtering only applies to event payloads that
            # carry a scope. Deletes and engagement events (reactions,
            # comments) don't — their visibility is already enforced at
            # write-time, and clients that don't have the parent event
            # just no-op on the message.
            if (
                visible_values is not None
                and event.kind in {"appended", "updated"}
                and event.payload.get("audience_scope") not in visible_values
            ):
                continue
            yield _format_sse(
                event=event.kind,
                data=event.payload,
                sequence_id=event.sequence_id if event.sequence_id >= 0 else None,
            )
