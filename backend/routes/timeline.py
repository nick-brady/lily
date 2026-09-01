"""Timeline event creators and mutations: notes, milestones, contractions,
the Baby Born! flip, edits, deletes, and interval toggles. Parents only."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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


def _is_born_milestone(event: TimelineEvent) -> bool:
    """The single Born milestone — the announcement itself. Both editing it
    and deleting it reach past the event into the birth's own clocks."""
    return (
        event.event_type is TimelineEventType.milestone
        and (event.payload or {}).get("kind") == "born"
    )


def _has_contraction(db: Session, birth_id: uuid.UUID) -> bool:
    """Whether labor was really observed, as opposed to `mark_born` filling
    in a start time it inferred from the arrival. Decides where undoing the
    announcement lands: back in `in_labor`, or all the way to `preparing`."""
    return db.scalars(
        select(TimelineEvent.id)
        .where(
            TimelineEvent.birth_id == birth_id,
            TimelineEvent.event_type == TimelineEventType.contraction,
            TimelineEvent.deleted_at.is_(None),
        )
        .limit(1)
    ).first() is not None


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


# How long a just-started contraction is protected from being stopped.
#
# Both parents watch the same page and neither knows who is going to press the
# button. Under GRACE the tapper cannot have known it had started — their tap
# was for starting, not stopping — so it does nothing at all. Between GRACE
# and CONFIRM a stop is possible but suspicious, and the client asks. Past
# CONFIRM it is simply a stop.
#
# CONFIRM is 10s because the real contractions recorded here run 14–101s, so
# the question can only ever land on a misfire, never on someone genuinely
# ending a short one.
CONTRACTION_GRACE_SECONDS = 5
CONTRACTION_CONFIRM_SECONDS = 10


@router.post("/birth/{birth_id}/contraction/start", response_model=TimelineEventOut)
async def start_contraction(
    payload: StartContractionIn = Body(default=StartContractionIn()),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineEventOut:
    now = datetime.now(timezone.utc)
    occurred_at = payload.occurred_at or now

    # Whoever pressed second joins the contraction already running rather than
    # opening another. No error: from where they are standing they started a
    # contraction, and one is running — which is the truth they wanted.
    running = timeline_repo.running_contraction(db, access.birth.id)
    if running is not None:
        return serialize_event_out(running)

    try:
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
        db.flush()
    except IntegrityError:
        # Both taps got past the check together and the index caught the
        # loser. Hand them the winner's contraction — the same answer they
        # would have had a millisecond earlier.
        db.rollback()
        running = timeline_repo.running_contraction(db, access.birth.id)
        if running is None:
            raise
        return serialize_event_out(running)
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
        # The announcement itself — the widest tier there is.
        audience_scope=AudienceScope.group_targeted,
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
    # A stop that arrives twice — a retry, a second tap, a reconnect — is the
    # same request, not a mistake. It used to answer 400 and put a red banner
    # in front of someone in labour.
    if event.payload.get("end_time") is not None:
        return serialize_event_with_engagement(
            db, event, requester_user_id=current_user.id
        )

    # Both ends of a contraction are stamped here, on one clock. The end time
    # used to come from the phone, so a duration was `their now − our start`:
    # every record carried the skew between two devices, and a phone running
    # behind wrote a negative duration, which goes on to be printed on a
    # keepsake.
    now = datetime.now(timezone.utc)
    age = (now - event.occurred_at).total_seconds()

    if age < CONTRACTION_GRACE_SECONDS:
        # They pressed to start it. Their partner was a moment quicker, and
        # nothing on their screen had said so yet.
        return serialize_event_with_engagement(
            db, event, requester_user_id=current_user.id
        )
    if age < CONTRACTION_CONFIRM_SECONDS:
        raise HTTPException(
            status_code=409,
            detail={"code": "just_started", "started_seconds_ago": int(age)},
        )

    timeline_repo.update_payload(
        db,
        event,
        {
            "end_time": now.isoformat(),
            "duration_seconds": int(age),
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

    # Only a photo has a part worth choosing. Stored to four places — the
    # difference between 0.3712 and 0.3713 of a picture is nothing anyone
    # could see, and short numbers keep the payload readable.
    if "focal" in patch:
        if event.event_type is not TimelineEventType.photo:
            raise HTTPException(
                status_code=400, detail="Only photos have a focal point"
            )
        patch["focal"] = {
            "x": round(patch["focal"]["x"], 4),
            "y": round(patch["focal"]["y"], 4),
        }
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
        if _is_born_milestone(event):
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
    # has to reach the artwork, not just the page. A focal point doesn't: it
    # says how the timeline crops a photo, and the artwork crops its own. On
    # its own it would restage every design, and a book takes six seconds to
    # redraw, so nudging a photo twice would cost a dozen for nothing.
    only_focal = set(patch) <= {"focal"} and new_time is None
    if not only_focal:
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
    # The Born milestone isn't a post about the birth — it *is* the
    # announcement, so removing it has to undo the flip too. Without this the
    # page stays `born` forever with its Baby Born! button gone (it renders
    # only while status isn't `born`) and no handle left to correct the
    # arrival time, since that's edited through this very event. A mistaken
    # tap needs a way back, and this is the one parents reach for.
    unborn = _is_born_milestone(event)
    if unborn:
        births_repo.unmark_born(
            db,
            birth=access.birth,
            resume_labor=_has_contraction(db, access.birth.id),
        )
    gifts_repo.mark_stale(db, birth_id=access.birth.id)
    db.commit()
    await publish_event_deleted(access.birth.id, event.sequence_id, event.id)
    if unborn:
        db.refresh(access.birth)
        await publish_birth_update(access.birth.id, access.birth)
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
