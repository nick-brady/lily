"""HTTP route table for the multi-tenant Lily backend.

All birth-scoped routes pass through `BirthAccess`, which resolves the
caller's `FamilyRole` for the requested birth. PR 1 only admits `owner`
and `co_parent`; the `family_viewer` flow lands in PR 3.

The `/ws` WebSocket route from the single-tenant build is gone; SSE
replaces it in PR 2. Live updates are intentionally broken between PR 1
and PR 2.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal, Union

from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Path as PathParam,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user, request_challenge, verify_challenge
from db import get_db
from models import (
    AudienceScope,
    Birth,
    FamilyRole,
    MediaKind,
    TimelineEvent,
    TimelineEventType,
    User,
)
from repositories import births as births_repo
from repositories import media as media_repo
from repositories import timeline as timeline_repo
from repositories import users as users_repo
from schemas import (
    AuthRequestIn,
    AuthRequestOut,
    AuthVerifyIn,
    BirthOut,
    CreateMilestoneIn,
    CreateTextNoteIn,
    FamilyMembershipOut,
    MeOut,
    StartContractionIn,
    StopContractionIn,
    TimelineEventOut,
    TokenOut,
    UserOut,
)


UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


app = FastAPI(title="Lily")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    return {"name": "lily", "status": "running"}


# ============ Auth ============


@app.post("/auth/request", response_model=AuthRequestOut)
def auth_request(
    payload: AuthRequestIn,
    db: Session = Depends(get_db),
) -> AuthRequestOut:
    return request_challenge(payload, db)


@app.post("/auth/verify", response_model=TokenOut)
def auth_verify(
    payload: AuthVerifyIn,
    db: Session = Depends(get_db),
) -> TokenOut:
    return verify_challenge(payload, db)


@app.get("/me", response_model=MeOut)
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    memberships = users_repo.list_memberships(db, current_user.id)
    return MeOut(
        user=UserOut.model_validate(current_user),
        memberships=[FamilyMembershipOut.model_validate(m) for m in memberships],
    )


# ============ Birth access dependency ============


@dataclass
class BirthAccess:
    birth: Birth
    role: FamilyRole


def require_birth_access(
    birth_id: uuid.UUID = PathParam(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BirthAccess:
    birth = births_repo.get_birth(db, birth_id)
    if birth is None or birth.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Birth not found")
    role = births_repo.user_role_for_birth(db, user_id=current_user.id, birth=birth)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this family")
    return BirthAccess(birth=birth, role=role)


def require_parent_access(access: BirthAccess = Depends(require_birth_access)) -> BirthAccess:
    if not births_repo.is_parent(access.role):
        raise HTTPException(status_code=403, detail="Parents only")
    return access


# ============ Birth ============


@app.get("/birth/{birth_id}", response_model=BirthOut)
def get_birth(access: BirthAccess = Depends(require_birth_access)) -> BirthOut:
    return BirthOut.model_validate(access.birth)


@app.get("/birth/{birth_id}/timeline", response_model=list[TimelineEventOut])
def list_timeline(
    access: BirthAccess = Depends(require_birth_access),
    after_sequence_id: int | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
) -> list[TimelineEventOut]:
    events = timeline_repo.list_events(
        db,
        birth_id=access.birth.id,
        after_sequence_id=after_sequence_id,
        limit=limit,
    )
    return [
        TimelineEventOut(
            id=e.id,
            birth_id=e.birth_id,
            event_type=e.event_type,
            sequence_id=e.sequence_id,
            occurred_at=e.occurred_at,
            posted_at=e.posted_at,
            posted_by_user_id=e.posted_by_user_id,
            payload=dict(e.payload),
            audience_scope=e.audience_scope,
        )
        for e in events
    ]


# ============ Timeline event creators ============


class _CreateTextNote(CreateTextNoteIn):
    type: Literal["text_note"] = "text_note"


class _CreateMilestone(CreateMilestoneIn):
    type: Literal["milestone"] = "milestone"


CreateEventIn = Annotated[
    Union[_CreateTextNote, _CreateMilestone],
    Field(discriminator="type"),
]


@app.post("/birth/{birth_id}/event", response_model=TimelineEventOut)
def create_event(
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
    db.commit()
    return _serialize_event(event)


@app.post("/birth/{birth_id}/contraction/start", response_model=TimelineEventOut)
def start_contraction(
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
        audience_scope=AudienceScope.public,
    )
    db.commit()
    return _serialize_event(event)


@app.post(
    "/birth/{birth_id}/contraction/{event_id}/stop",
    response_model=TimelineEventOut,
)
def stop_contraction(
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
    db.commit()
    return _serialize_event(event)


# ============ Media ============


@app.post("/birth/{birth_id}/media", response_model=TimelineEventOut)
async def upload_media(
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    kind: MediaKind = Form(...),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineEventOut:
    extension = Path(file.filename or "").suffix or _default_extension(kind)
    filename = f"{uuid.uuid4()}{extension}"
    filepath = UPLOAD_DIR / filename
    content = await file.read()
    filepath.write_bytes(content)

    asset = media_repo.create_media_asset(
        db,
        family_id=access.birth.family_id,
        birth_id=access.birth.id,
        uploaded_by_user_id=current_user.id,
        kind=kind,
        original_s3_key=media_repo.local_key(filename),
        mime_type=file.content_type,
        bytes_=len(content),
    )

    event_type = {
        MediaKind.photo: TimelineEventType.photo,
        MediaKind.video: TimelineEventType.video,
        MediaKind.voice_memo: TimelineEventType.voice_memo,
    }[kind]
    event_payload = {
        "type": event_type.value,
        "media_id": str(asset.id),
        "caption": caption,
    }
    event = timeline_repo.append_event(
        db,
        birth_id=access.birth.id,
        event_type=event_type,
        payload=event_payload,
        posted_by_user_id=current_user.id,
        audience_scope=AudienceScope.public,
    )
    db.commit()
    return _serialize_event(event)


# ============ helpers ============


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


def _default_extension(kind: MediaKind) -> str:
    return {
        MediaKind.photo: ".jpg",
        MediaKind.video: ".mp4",
        MediaKind.voice_memo: ".webm",
    }[kind]


def _serialize_event(e) -> TimelineEventOut:
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
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
