"""Timeline event creators and mutations: notes, milestones, contractions,
the Baby Born! flip, edits, deletes, and interval toggles. Parents only."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from db import get_db
from events import publish_birth_update, publish_event_change, publish_event_deleted
from models import (
    AudienceScope,
    BirthStatus,
    TimelineEvent,
    TimelineEventType,
    User,
)
from repositories import births as births_repo
from repositories import gifts as gifts_repo
from repositories import timeline as timeline_repo
from routes.deps import BirthAccess, require_parent_access
from routes.serializers import serialize_event_out, serialize_event_with_engagement
from schemas import (
    BabyBornIn,
    BirthOut,
    CreateMilestoneIn,
    CreateTextNoteIn,
    EditEventIn,
    StartContractionIn,
    StopContractionIn,
    TimelineEventOut,
)

router = APIRouter()


class _CreateTextNote(CreateTextNoteIn):
    type: Literal["text_note"] = "text_note"


class _CreateMilestone(CreateMilestoneIn):
    type: Literal["milestone"] = "milestone"


CreateEventIn = Annotated[
    Union[_CreateTextNote, _CreateMilestone],
    Field(discriminator="type"),
]


@router.post("/birth/{birth_id}/event", response_model=TimelineEventOut)
async def create_event(
    payload: CreateEventIn = Body(...),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineEventOut:
    if isinstance(payload, _CreateTextNote):
        event_payload = {"type": "text_note", "body": payload.body}
        event_type = TimelineEventType.text_note
    elif isinstance(payload, _CreateMilestone):
        event_payload = {
            "type": "milestone",
            "kind": payload.kind,
            "title": payload.title,
            "body": payload.body,
        }
        event_type = TimelineEventType.milestone
    else:
        raise HTTPException(status_code=400, detail="Unsupported event type")

    event = timeline_repo.append_event(
        db,
        birth_id=access.birth.id,
        event_type=event_type,
        payload=event_payload,
        posted_by_user_id=current_user.id,
        occurred_at=payload.occurred_at,
        audience_scope=payload.audience_scope,
    )
    gifts_repo.mark_stale(db, birth_id=access.birth.id)
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "appended", event)
    return serialize_event_out(event)


def _gap_before_seconds(db: Session, birth_id: uuid.UUID, occurred_at: datetime) -> int | None:
    previous = db.scalars(
        select(TimelineEvent)
        .where(
            TimelineEvent.birth_id == birth_id,
            TimelineEvent.event_type == TimelineEventType.contraction,
            TimelineEvent.deleted_at.is_(None),
        )
        .order_by(TimelineEvent.occurred_at.desc())
        .limit(1)
    ).first()
    if previous is None:
        return None
    return int((occurred_at - previous.occurred_at).total_seconds())


@router.post("/birth/{birth_id}/contraction/start", response_model=TimelineEventOut)
async def start_contraction(
    payload: StartContractionIn = Body(default=StartContractionIn()),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineEventOut:
    now = datetime.now(timezone.utc)
    occurred_at = payload.occurred_at or now
    event = timeline_repo.append_event(
        db,
        birth_id=access.birth.id,
        event_type=TimelineEventType.contraction,
        payload={
            "type": "contraction",
            "duration_seconds": None,
            "end_time": None,
            "gap_before_seconds": _gap_before_seconds(db, access.birth.id, occurred_at),
        },
        posted_by_user_id=current_user.id,
        occurred_at=occurred_at,
        audience_scope=payload.audience_scope,
    )
    # The first contraction is what tips a birth into labor — the gentle
    # "something's happening" signal family viewers see.
    labor_began = births_repo.begin_labor(db, birth=access.birth, when=occurred_at)
    gifts_repo.mark_stale(db, birth_id=access.birth.id)
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "appended", event)
    if labor_began:
        db.refresh(access.birth)
        await publish_birth_update(access.birth.id, access.birth)
    return serialize_event_out(event)


@router.post("/birth/{birth_id}/born", response_model=BirthOut)
async def mark_baby_born(
    payload: BabyBornIn = Body(default=BabyBornIn()),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BirthOut:
    """The Baby Born! moment — the experience the product was built for.
    Flips the birth to `born`, records the arrival time, and drops a
    public `born` milestone onto the timeline so it becomes the story's
    center of gravity. The status broadcast is what triggers the live
    celebration for everyone watching.
    """
    if access.birth.status is BirthStatus.born:
        raise HTTPException(status_code=409, detail="Already marked born")

    when = payload.occurred_at or datetime.now(timezone.utc)
    births_repo.mark_born(db, birth=access.birth, when=when)
    event = timeline_repo.append_event(
        db,
        birth_id=access.birth.id,
        event_type=TimelineEventType.milestone,
        payload={
            "type": "milestone",
            "kind": "born",
            "title": "Baby Born!",
            "body": payload.body,
        },
        posted_by_user_id=current_user.id,
        occurred_at=when,
        audience_scope=AudienceScope.public,
    )
    db.commit()
    db.refresh(event)
    db.refresh(access.birth)
    await publish_event_change(access.birth.id, "appended", event)
    await publish_birth_update(access.birth.id, access.birth)
    return BirthOut.model_validate(access.birth)


@router.post(
    "/birth/{birth_id}/contraction/{event_id}/stop",
    response_model=TimelineEventOut,
)
async def stop_contraction(
    event_id: uuid.UUID,
    payload: StopContractionIn = Body(...),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineEventOut:
    event = timeline_repo.get_event(db, event_id)
    if event is None or event.birth_id != access.birth.id:
        raise HTTPException(status_code=404, detail="Contraction not found")
    if event.event_type is not TimelineEventType.contraction:
        raise HTTPException(status_code=400, detail="Event is not a contraction")
    if event.payload.get("end_time") is not None:
        raise HTTPException(status_code=400, detail="Contraction already stopped")

    duration = int((payload.end_time - event.occurred_at).total_seconds())
    timeline_repo.update_payload(
        db,
        event,
        {
            "end_time": payload.end_time.isoformat(),
            "duration_seconds": duration,
        },
    )
    gifts_repo.mark_stale(db, birth_id=access.birth.id)
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "updated", event)
    return serialize_event_with_engagement(
        db, event, requester_user_id=current_user.id
    )


@router.patch("/birth/{birth_id}/event/{event_id}", response_model=TimelineEventOut)
async def edit_event(
    event_id: uuid.UUID,
    payload: EditEventIn = Body(...),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineEventOut:
    event = timeline_repo.get_event(db, event_id)
    if event is None or event.birth_id != access.birth.id:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.deleted_at is not None:
        raise HTTPException(status_code=410, detail="Event has been deleted")

    patch = payload.model_dump(exclude_none=True)
    new_time = patch.pop("occurred_at", None)
    if not patch and new_time is None:
        return serialize_event_with_engagement(
            db, event, requester_user_id=current_user.id
        )

    # occurred_at is a column, not payload. Contraction times stay fixed —
    # their durations and gap markers are derived from them.
    birth_clocks_moved = False
    if new_time is not None:
        if event.event_type is TimelineEventType.contraction:
            raise HTTPException(
                status_code=400, detail="Contraction times can't be edited"
            )
        event.occurred_at = new_time
        # The Born milestone IS the arrival time — keep the birth's own
        # clocks telling the same story.
        if (
            event.event_type is TimelineEventType.milestone
            and (event.payload or {}).get("kind") == "born"
        ):
            access.birth.birth_completed_at = new_time
            # birth_started_at is deliberately left alone. It's the first
            # contraction — a real recorded observation — and it used to get
            # dragged back to equal the new arrival time, which silently
            # destroyed it and reported a 0-minute labor. A born time earlier
            # than labor began is only reachable by entering a wrong time, and
            # the honest consequence of a wrong time is a wrong-looking record
            # (labor duration reads as unknown, since the negative interval is
            # already filtered out downstream) — not the loss of a correct
            # value with no undo.
            birth_clocks_moved = True

    if patch:
        timeline_repo.update_payload(db, event, patch)
    # The keepsake draws from this event — a corrected arrival time or caption
    # has to reach the artwork, not just the page.
    gifts_repo.mark_stale(db, birth_id=access.birth.id)
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "updated", event)
    if birth_clocks_moved:
        db.refresh(access.birth)
        await publish_birth_update(access.birth.id, access.birth)
    return serialize_event_with_engagement(
        db, event, requester_user_id=current_user.id
    )


@router.delete("/birth/{birth_id}/event/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> Response:
    event = timeline_repo.get_event(db, event_id)
    if event is None or event.birth_id != access.birth.id:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.deleted_at is not None:
        return Response(status_code=204)
    event.deleted_at = datetime.now(timezone.utc)
    gifts_repo.mark_stale(db, birth_id=access.birth.id)
    db.commit()
    await publish_event_deleted(access.birth.id, event.sequence_id, event.id)
    return Response(status_code=204)


@router.post(
    "/birth/{birth_id}/event/{event_id}/toggle-ignore",
    response_model=TimelineEventOut,
)
async def toggle_ignore_interval(
    event_id: uuid.UUID,
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineEventOut:
    event = timeline_repo.get_event(db, event_id)
    if event is None or event.birth_id != access.birth.id:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.event_type is not TimelineEventType.contraction:
        raise HTTPException(status_code=400, detail="Only contractions support ignore-interval")
    current = bool(event.payload.get("ignore_interval_before", False))
    timeline_repo.update_payload(db, event, {"ignore_interval_before": not current})
    gifts_repo.mark_stale(db, birth_id=access.birth.id)
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "updated", event)
    return serialize_event_with_engagement(
        db, event, requester_user_id=current_user.id
    )
