"""HTTP route table for the multi-tenant Lily backend.

Birth-scoped routes pass through `BirthAccess` (parents only in PR 2).
Public read-only routes (`/b/{slug}*`) require no auth at all — they
serve the keepsake page. SSE lives at `/birth/{id}/stream` for parents
and `/b/{slug}/stream` for the public view.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, AsyncIterator, Literal, Union

from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Header,
    Path as PathParam,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import (
    get_current_user,
    get_current_user_stream,
    get_optional_current_user,
    request_challenge,
    verify_challenge,
    FRONTEND_URL,
)
from db import get_db
from events import (
    broker,
    publish_comment_change,
    publish_event_change,
    publish_event_deleted,
    publish_reaction_change,
    serialize_event,
)
from models import (
    AudienceScope,
    Birth,
    Family,
    FamilyMembership,
    FamilyRole,
    MediaAsset,
    MediaKind,
    ReactionKind,
    TimelineEvent,
    TimelineEventType,
    User,
    ViewerInvitation,
)
from repositories import births as births_repo
from repositories import comments as comments_repo
from repositories import families as families_repo
from repositories import invitations as invitations_repo
from repositories import media as media_repo
from repositories import reactions as reactions_repo
from repositories import timeline as timeline_repo
from repositories import users as users_repo
from storage import ensure_bucket, presigned_get_url, put_object
from schemas import (
    AuthRequestIn,
    AuthRequestOut,
    AuthVerifyIn,
    BirthCreateIn,
    BirthOut,
    BirthUpdateIn,
    SlugAvailableOut,
    CommentCreateIn,
    CommentEditIn,
    CommentOut,
    CoParentInviteCreateIn,
    CoParentMemberOut,
    CoParentsOut,
    CreateMilestoneIn,
    CreateTextNoteIn,
    EditEventIn,
    FamilyMembershipOut,
    FamilyWithBirthsOut,
    InvitationContextOut,
    InvitationCreateIn,
    InvitationCreatedOut,
    InvitationOut,
    MeOut,
    PendingCoParentInviteOut,
    ReactionCountOut,
    ReactionToggleIn,
    StartContractionIn,
    StopContractionIn,
    TimelineEventOut,
    TokenOut,
    UserOut,
)


UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

SSE_HEARTBEAT_SECONDS = 15


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_bucket()
    yield


app = FastAPI(title="Lily", lifespan=lifespan)
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
def auth_request(payload: AuthRequestIn, db: Session = Depends(get_db)) -> AuthRequestOut:
    return request_challenge(payload, db)


@app.post("/auth/verify", response_model=TokenOut)
def auth_verify(payload: AuthVerifyIn, db: Session = Depends(get_db)) -> TokenOut:
    return verify_challenge(payload, db)


@app.get("/me", response_model=MeOut)
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    memberships = users_repo.list_memberships(db, current_user.id)

    families: list[FamilyWithBirthsOut] = []
    for membership in memberships:
        family = db.get(Family, membership.family_id)
        if family is None:
            continue
        births = db.scalars(
            select(Birth)
            .where(Birth.family_id == family.id, Birth.deleted_at.is_(None))
            .order_by(Birth.created_at.asc())
        ).all()
        families.append(
            FamilyWithBirthsOut(
                id=family.id,
                display_name=family.display_name,
                role=membership.role,
                births=[BirthOut.model_validate(b) for b in births],
            )
        )

    return MeOut(
        user=UserOut.model_validate(current_user),
        memberships=[FamilyMembershipOut.model_validate(m) for m in memberships],
        families=families,
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


@dataclass
class FamilyAccess:
    family: Family
    membership: FamilyMembership


def require_family_parent(
    family_id: uuid.UUID = PathParam(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FamilyAccess:
    """Family-scoped sibling of `require_parent_access`. Co-parent
    management acts on a whole family (the grant is family-wide), so it
    gates on family membership rather than a single birth.
    """
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    membership = families_repo.get_membership(
        db, family_id=family_id, user_id=current_user.id
    )
    if membership is None or not births_repo.is_parent(membership.role):
        raise HTTPException(status_code=403, detail="Parents only")
    return FamilyAccess(family=family, membership=membership)


# ============ Birth creation ============


def _clean_slug(raw: str) -> str:
    slug = raw.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug.strip("-")


@app.get("/births/slug-available", response_model=SlugAvailableOut)
def check_slug_available(slug: str, db: Session = Depends(get_db)) -> SlugAvailableOut:
    clean = _clean_slug(slug)
    if not clean:
        return SlugAvailableOut(available=False)
    if births_repo.get_birth_by_slug(db, clean) is None:
        return SlugAvailableOut(available=True)
    for n in range(2, 100):
        candidate = f"{clean}-{n}"
        if births_repo.get_birth_by_slug(db, candidate) is None:
            return SlugAvailableOut(available=False, suggestion=candidate)
    return SlugAvailableOut(available=False)


@app.post("/births", response_model=BirthOut)
def create_birth(
    payload: BirthCreateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BirthOut:
    slug = _clean_slug(payload.slug)
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid slug")
    if births_repo.get_birth_by_slug(db, slug) is not None:
        raise HTTPException(status_code=409, detail="Slug already taken")
    family = Family(
        primary_owner_user_id=current_user.id,
        display_name=f"{payload.baby_name} Family",
    )
    db.add(family)
    db.flush()
    db.add(FamilyMembership(
        family_id=family.id,
        user_id=current_user.id,
        role=FamilyRole.owner,
    ))
    db.flush()
    birth = births_repo.create_birth(
        db,
        family_id=family.id,
        child_name=payload.baby_name,
        slug=slug,
        theme=payload.theme,
    )
    db.commit()
    db.refresh(birth)
    return BirthOut.model_validate(birth)


# ============ Birth (authed) ============


@app.get("/birth/{birth_id}", response_model=BirthOut)
def get_birth(access: BirthAccess = Depends(require_birth_access)) -> BirthOut:
    return BirthOut.model_validate(access.birth)


@app.patch("/birth/{birth_id}", response_model=BirthOut)
def update_birth(
    payload: BirthUpdateIn,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> BirthOut:
    births_repo.update_birth(db, birth=access.birth, theme=payload.theme)
    db.commit()
    db.refresh(access.birth)
    return BirthOut.model_validate(access.birth)


@app.get("/birth/{birth_id}/timeline", response_model=list[TimelineEventOut])
def list_timeline(
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    after_sequence_id: int | None = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
) -> list[TimelineEventOut]:
    visible = births_repo.visible_scopes_for_role(access.role)
    events = timeline_repo.list_events(
        db,
        birth_id=access.birth.id,
        after_sequence_id=after_sequence_id,
        limit=limit,
        audience_scopes=visible,
    )
    return _serialize_events_with_engagement(
        db, events, requester_user_id=current_user.id
    )


# ============ Public birth (no auth) ============


def _resolve_public_birth(db: Session, slug: str) -> Birth:
    birth = births_repo.get_birth_by_slug(db, slug)
    if birth is None or birth.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Birth not found")
    if birth.is_locked_to_invited:
        # PR 2 has no viewer-token mechanism; locked births are unreachable
        # publicly until PR 3 lands viewer invitations.
        raise HTTPException(status_code=403, detail="This birth is invited-only")
    return birth


def _scope_set_for_visitor(
    db: Session, birth: Birth, user: User | None
) -> frozenset[AudienceScope]:
    """Widen audience scopes if the public-route visitor turns out to be
    a member of the family.
    """
    if user is None:
        return frozenset({AudienceScope.public})
    role = births_repo.user_role_for_birth(db, user_id=user.id, birth=birth)
    return births_repo.visible_scopes_for_role(role)


@app.get("/b/{slug}", response_model=BirthOut)
def public_birth(slug: str, db: Session = Depends(get_db)) -> BirthOut:
    return BirthOut.model_validate(_resolve_public_birth(db, slug))


@app.get("/b/{slug}/timeline", response_model=list[TimelineEventOut])
def public_timeline(
    slug: str,
    after_sequence_id: int | None = None,
    limit: int = 1000,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> list[TimelineEventOut]:
    birth = _resolve_public_birth(db, slug)
    visible = _scope_set_for_visitor(db, birth, current_user)
    events = timeline_repo.list_events(
        db,
        birth_id=birth.id,
        after_sequence_id=after_sequence_id,
        limit=limit,
        audience_scopes=visible,
    )
    return _serialize_events_with_engagement(
        db,
        events,
        requester_user_id=current_user.id if current_user else None,
    )


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
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "appended", event)
    return _serialize_event_out(event)


@app.post("/birth/{birth_id}/contraction/start", response_model=TimelineEventOut)
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
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "appended", event)
    return _serialize_event_out(event)


@app.post(
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
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "updated", event)
    return _serialize_event_with_engagement(
        db, event, requester_user_id=current_user.id
    )


@app.patch("/birth/{birth_id}/event/{event_id}", response_model=TimelineEventOut)
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
    if not patch:
        return _serialize_event_with_engagement(
            db, event, requester_user_id=current_user.id
        )
    timeline_repo.update_payload(db, event, patch)
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "updated", event)
    return _serialize_event_with_engagement(
        db, event, requester_user_id=current_user.id
    )


@app.delete("/birth/{birth_id}/event/{event_id}", status_code=204)
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
    db.commit()
    await publish_event_deleted(access.birth.id, event.sequence_id, event.id)
    return Response(status_code=204)


@app.post(
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
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "updated", event)
    return _serialize_event_with_engagement(
        db, event, requester_user_id=current_user.id
    )


# ============ Reactions ============


def _require_visible_event(
    db: Session,
    event_id: uuid.UUID,
    *,
    birth: Birth,
    role: FamilyRole | None,
) -> TimelineEvent:
    """Resolve a timeline event the caller is allowed to engage with.

    A reaction or comment on an event the caller can't see is meaningless
    (and would leak audience info via the existence-check). 404 keeps the
    audience scope opaque.

    `role=None` means an authed stranger who found the page via QR card
    or shared link — they get public-scope visibility only.
    """
    event = timeline_repo.get_event(db, event_id)
    if (
        event is None
        or event.birth_id != birth.id
        or event.deleted_at is not None
    ):
        raise HTTPException(status_code=404, detail="Event not found")
    visible = births_repo.visible_scopes_for_role(role)
    if event.audience_scope not in visible:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@dataclass
class PublicEngagementAccess:
    """Auth context for engagement on the public-shaped surface.

    Anyone authed can interact, even if they aren't a family member —
    Aunt Linda scans a QR card from a printed announcement, signs in
    with her phone number, and leaves a comment. The brand depends on
    that being possible (see Persona 1 Stage 9: "she wasn't even invited
    to the page originally").
    """

    birth: Birth
    user: User
    role: FamilyRole | None  # None when the user isn't a family member


def require_public_engagement(
    slug: str = PathParam(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicEngagementAccess:
    birth = _resolve_public_birth(db, slug)
    role = births_repo.user_role_for_birth(db, user_id=current_user.id, birth=birth)
    return PublicEngagementAccess(birth=birth, user=current_user, role=role)


async def _do_add_reaction(
    db: Session,
    *,
    birth: Birth,
    role: FamilyRole | None,
    user: User,
    event_id: uuid.UUID,
    kind: ReactionKind,
) -> dict[ReactionKind, ReactionCountOut]:
    event = _require_visible_event(db, event_id, birth=birth, role=role)
    added = reactions_repo.add_reaction(
        db, event_id=event.id, user_id=user.id, kind=kind
    )
    db.commit()
    if added:
        await publish_reaction_change(
            birth.id,
            kind="reaction_added",
            event_id=event.id,
            reaction_kind=kind.value,
            user_id=user.id,
        )
    summary = reactions_repo.summarize_event(
        db, event_id=event.id, requester_user_id=user.id
    )
    return {
        k: ReactionCountOut(count=s.count, mine=s.mine)
        for k, s in summary.items()
    }


async def _do_remove_reaction(
    db: Session,
    *,
    birth: Birth,
    role: FamilyRole | None,
    user: User,
    event_id: uuid.UUID,
    kind: ReactionKind,
) -> dict[ReactionKind, ReactionCountOut]:
    event = _require_visible_event(db, event_id, birth=birth, role=role)
    removed = reactions_repo.remove_reaction(
        db, event_id=event.id, user_id=user.id, kind=kind
    )
    db.commit()
    if removed:
        await publish_reaction_change(
            birth.id,
            kind="reaction_removed",
            event_id=event.id,
            reaction_kind=kind.value,
            user_id=user.id,
        )
    summary = reactions_repo.summarize_event(
        db, event_id=event.id, requester_user_id=user.id
    )
    return {
        k: ReactionCountOut(count=s.count, mine=s.mine)
        for k, s in summary.items()
    }


@app.post(
    "/birth/{birth_id}/event/{event_id}/reactions",
    response_model=dict[ReactionKind, ReactionCountOut],
)
async def add_reaction(
    event_id: uuid.UUID,
    payload: ReactionToggleIn = Body(...),
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[ReactionKind, ReactionCountOut]:
    return await _do_add_reaction(
        db,
        birth=access.birth,
        role=access.role,
        user=current_user,
        event_id=event_id,
        kind=payload.kind,
    )


@app.delete(
    "/birth/{birth_id}/event/{event_id}/reactions/{kind}",
    response_model=dict[ReactionKind, ReactionCountOut],
)
async def remove_reaction(
    event_id: uuid.UUID,
    kind: ReactionKind,
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[ReactionKind, ReactionCountOut]:
    return await _do_remove_reaction(
        db,
        birth=access.birth,
        role=access.role,
        user=current_user,
        event_id=event_id,
        kind=kind,
    )


@app.post(
    "/b/{slug}/event/{event_id}/reactions",
    response_model=dict[ReactionKind, ReactionCountOut],
)
async def public_add_reaction(
    event_id: uuid.UUID,
    payload: ReactionToggleIn = Body(...),
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> dict[ReactionKind, ReactionCountOut]:
    return await _do_add_reaction(
        db,
        birth=access.birth,
        role=access.role,
        user=access.user,
        event_id=event_id,
        kind=payload.kind,
    )


@app.delete(
    "/b/{slug}/event/{event_id}/reactions/{kind}",
    response_model=dict[ReactionKind, ReactionCountOut],
)
async def public_remove_reaction(
    event_id: uuid.UUID,
    kind: ReactionKind,
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> dict[ReactionKind, ReactionCountOut]:
    return await _do_remove_reaction(
        db,
        birth=access.birth,
        role=access.role,
        user=access.user,
        event_id=event_id,
        kind=kind,
    )


# ============ Comments ============


def _comment_locked_response(birth: Birth) -> HTTPException:
    """Standard 402 used everywhere we gate on the unlock. The body has
    everything the frontend needs to render the dignified $12 prompt
    from the spec — copy lives client-side.
    """
    return HTTPException(
        status_code=402,
        detail={
            "code": "comments_locked",
            "birth_id": str(birth.id),
            "child_name": birth.child_name,
        },
    )


async def _do_create_comment(
    db: Session,
    *,
    birth: Birth,
    role: FamilyRole | None,
    user: User,
    event_id: uuid.UUID,
    body: str,
) -> CommentOut:
    event = _require_visible_event(db, event_id, birth=birth, role=role)
    # Parents own the page and can post even before the unlock is paid.
    # Everyone else waits until someone in the family unlocks comments.
    if not birth.is_unlocked and not births_repo.is_parent(role):
        raise _comment_locked_response(birth)
    comment = comments_repo.create_comment(
        db, event_id=event.id, user_id=user.id, body=body.strip()
    )
    db.commit()
    db.refresh(comment)
    await publish_comment_change(
        birth.id,
        kind="comment_added",
        event_id=event.id,
        comment_id=comment.id,
        body=comment.body,
        user_id=user.id,
    )
    return CommentOut.model_validate(comment)


async def _do_edit_comment(
    db: Session,
    *,
    birth: Birth,
    user: User,
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: str,
) -> CommentOut:
    comment = comments_repo.get_comment(db, comment_id)
    if (
        comment is None
        or comment.event_id != event_id
        or comment.deleted_at is not None
    ):
        raise HTTPException(status_code=404, detail="Comment not found")
    # Only the author can edit. Parents can delete but not rewrite words.
    if comment.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the author can edit")
    comments_repo.edit_body(db, comment, body.strip())
    db.commit()
    db.refresh(comment)
    await publish_comment_change(
        birth.id,
        kind="comment_updated",
        event_id=event_id,
        comment_id=comment.id,
        body=comment.body,
    )
    return CommentOut.model_validate(comment)


async def _do_delete_comment(
    db: Session,
    *,
    birth: Birth,
    role: FamilyRole | None,
    user: User,
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> Response:
    comment = comments_repo.get_comment(db, comment_id)
    if comment is None or comment.event_id != event_id:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.deleted_at is not None:
        return Response(status_code=204)
    # Authors can delete their own. Parents can moderate anyone's.
    is_author = comment.user_id == user.id
    if not (is_author or births_repo.is_parent(role)):
        raise HTTPException(status_code=403, detail="Not allowed")
    comments_repo.soft_delete(db, comment)
    db.commit()
    await publish_comment_change(
        birth.id,
        kind="comment_deleted",
        event_id=event_id,
        comment_id=comment.id,
    )
    return Response(status_code=204)


@app.get(
    "/birth/{birth_id}/event/{event_id}/comments",
    response_model=list[CommentOut],
)
def list_event_comments(
    event_id: uuid.UUID,
    access: BirthAccess = Depends(require_birth_access),
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    event = _require_visible_event(
        db, event_id, birth=access.birth, role=access.role
    )
    rows = comments_repo.list_for_event(db, event_id=event.id)
    return [CommentOut.model_validate(r) for r in rows]


@app.get(
    "/b/{slug}/event/{event_id}/comments",
    response_model=list[CommentOut],
)
def public_list_event_comments(
    slug: str,
    event_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    """Anonymous readers see comments — they're the heart of the
    keepsake. Posting is gated below."""
    birth = _resolve_public_birth(db, slug)
    visible = _scope_set_for_visitor(db, birth, current_user)
    event = timeline_repo.get_event(db, event_id)
    if (
        event is None
        or event.birth_id != birth.id
        or event.deleted_at is not None
        or event.audience_scope not in visible
    ):
        raise HTTPException(status_code=404, detail="Event not found")
    rows = comments_repo.list_for_event(db, event_id=event.id)
    return [CommentOut.model_validate(r) for r in rows]


@app.post(
    "/birth/{birth_id}/event/{event_id}/comments",
    response_model=CommentOut,
)
async def create_event_comment(
    event_id: uuid.UUID,
    payload: CommentCreateIn = Body(...),
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    return await _do_create_comment(
        db,
        birth=access.birth,
        role=access.role,
        user=current_user,
        event_id=event_id,
        body=payload.body,
    )


@app.post(
    "/b/{slug}/event/{event_id}/comments",
    response_model=CommentOut,
)
async def public_create_event_comment(
    event_id: uuid.UUID,
    payload: CommentCreateIn = Body(...),
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> CommentOut:
    return await _do_create_comment(
        db,
        birth=access.birth,
        role=access.role,
        user=access.user,
        event_id=event_id,
        body=payload.body,
    )


@app.patch(
    "/birth/{birth_id}/event/{event_id}/comments/{comment_id}",
    response_model=CommentOut,
)
async def edit_event_comment(
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentEditIn = Body(...),
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    return await _do_edit_comment(
        db,
        birth=access.birth,
        user=current_user,
        event_id=event_id,
        comment_id=comment_id,
        body=payload.body,
    )


@app.patch(
    "/b/{slug}/event/{event_id}/comments/{comment_id}",
    response_model=CommentOut,
)
async def public_edit_event_comment(
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentEditIn = Body(...),
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> CommentOut:
    return await _do_edit_comment(
        db,
        birth=access.birth,
        user=access.user,
        event_id=event_id,
        comment_id=comment_id,
        body=payload.body,
    )


@app.delete(
    "/birth/{birth_id}/event/{event_id}/comments/{comment_id}",
    status_code=204,
)
async def delete_event_comment(
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    return await _do_delete_comment(
        db,
        birth=access.birth,
        role=access.role,
        user=current_user,
        event_id=event_id,
        comment_id=comment_id,
    )


@app.delete(
    "/b/{slug}/event/{event_id}/comments/{comment_id}",
    status_code=204,
)
async def public_delete_event_comment(
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> Response:
    return await _do_delete_comment(
        db,
        birth=access.birth,
        role=access.role,
        user=access.user,
        event_id=event_id,
        comment_id=comment_id,
    )


# ============ Media ============


@app.post("/birth/{birth_id}/media", response_model=TimelineEventOut)
async def upload_media(
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    kind: MediaKind = Form(...),
    audience_scope: AudienceScope = Form(AudienceScope.public),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineEventOut:
    extension = Path(file.filename or "").suffix or _default_extension(kind)
    filename = f"{uuid.uuid4()}{extension}"
    content = await file.read()
    key = media_repo.media_object_key(
        family_id=access.birth.family_id,
        birth_id=access.birth.id,
        filename=filename,
    )
    put_object(
        key=key,
        body=content,
        content_type=file.content_type,
    )

    asset = media_repo.create_media_asset(
        db,
        family_id=access.birth.family_id,
        birth_id=access.birth.id,
        uploaded_by_user_id=current_user.id,
        kind=kind,
        original_s3_key=key,
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
        audience_scope=audience_scope,
    )
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "appended", event)
    return _serialize_event_out(event)


def _media_visible_to(
    db: Session, asset: MediaAsset, user: User | None
) -> bool:
    """Resolve the audience scopes of every event referencing this asset
    and check whether the requester is allowed to see any of them.

    Anonymous requesters get the public scope only. Authenticated users
    inherit their role on the asset's family (or anonymous-equivalent if
    they have no membership there).
    """
    role: FamilyRole | None = None
    if user is not None:
        membership = db.scalars(
            select(FamilyMembership).where(
                FamilyMembership.family_id == asset.family_id,
                FamilyMembership.user_id == user.id,
            )
        ).first()
        if membership is not None:
            role = membership.role
    visible = births_repo.visible_scopes_for_role(role)

    referencing_scopes = set(
        db.scalars(
            select(TimelineEvent.audience_scope)
            .where(
                TimelineEvent.birth_id == asset.birth_id,
                TimelineEvent.deleted_at.is_(None),
                TimelineEvent.payload["media_id"].astext == str(asset.id),
            )
        ).all()
    )
    if not referencing_scopes:
        # Orphan asset with no event — treat as parent-only, since only
        # the original uploader could possibly need it.
        return role in births_repo.PARENT_ROLES
    return bool(visible & referencing_scopes)


# ============ Invitations ============


def _invitation_url(plaintext_token: str) -> str:
    return f"{FRONTEND_URL}/invite/{plaintext_token}"


@app.post(
    "/birth/{birth_id}/invitations",
    response_model=InvitationCreatedOut,
)
def create_invitation(
    payload: InvitationCreateIn = Body(default=InvitationCreateIn()),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationCreatedOut:
    invitation, plaintext_token = invitations_repo.create_invitation(
        db,
        family_id=access.birth.family_id,
        birth_id=access.birth.id,
        invited_by_user_id=current_user.id,
        display_name_hint=payload.display_name_hint,
        email_hint=payload.email_hint,
        phone_hint=payload.phone_hint,
    )
    db.commit()
    db.refresh(invitation)
    return InvitationCreatedOut(
        **InvitationOut.model_validate(invitation).model_dump(),
        token=plaintext_token,
        invite_url=_invitation_url(plaintext_token),
    )


@app.get(
    "/birth/{birth_id}/invitations",
    response_model=list[InvitationOut],
)
def list_invitations(
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> list[InvitationOut]:
    rows = invitations_repo.list_for_birth(db, birth_id=access.birth.id)
    return [InvitationOut.model_validate(r) for r in rows]


@app.delete("/birth/{birth_id}/invitations/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: uuid.UUID,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> Response:
    invitation = db.get(ViewerInvitation, invitation_id)
    if invitation is None or invitation.birth_id != access.birth.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitations_repo.revoke(db, invitation)
    db.commit()
    return Response(status_code=204)


@app.get("/invite/{token}", response_model=InvitationContextOut)
def lookup_invitation(token: str, db: Session = Depends(get_db)) -> InvitationContextOut:
    invitation = invitations_repo.lookup_by_token(db, token)
    if invitation is None or not invitations_repo.is_redeemable(invitation):
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    family = db.get(Family, invitation.family_id)
    birth = db.get(Birth, invitation.birth_id)
    if family is None or birth is None:
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    return InvitationContextOut(
        family_display_name=family.display_name,
        birth_id=birth.id,
        birth_slug=birth.slug,
        birth_child_name=birth.child_name,
        display_name_hint=invitation.display_name_hint,
        email_hint=invitation.email_hint,
        phone_hint=invitation.phone_hint,
        expires_at=invitation.expires_at,
        role=invitation.role,
    )


@app.post("/invite/{token}/redeem", status_code=204)
def redeem_invitation_authed(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """For users who are already signed in. The new-user flow goes
    through `/auth/verify` with `invite_token` instead.
    """
    invitation = invitations_repo.lookup_by_token(db, token)
    if invitation is None or not invitations_repo.is_redeemable(invitation):
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    invitations_repo.redeem(db, invitation=invitation, user_id=current_user.id)
    db.commit()
    return Response(status_code=204)


# ============ Co-parents (family-scoped) ============


@app.get("/family/{family_id}/co-parents", response_model=CoParentsOut)
def list_co_parents(
    access: FamilyAccess = Depends(require_family_parent),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CoParentsOut:
    parents = families_repo.list_parents(db, family_id=access.family.id)
    members = [
        CoParentMemberOut(
            user_id=user.id,
            display_name=user.display_name,
            contact=user.email or user.phone,
            role=membership.role,
            is_self=user.id == current_user.id,
        )
        for membership, user in parents
    ]
    now = datetime.now(timezone.utc)
    pending = [
        PendingCoParentInviteOut.model_validate(inv)
        for inv in invitations_repo.list_for_family(
            db, family_id=access.family.id, role=FamilyRole.co_parent
        )
        if inv.revoked_at is None and inv.expires_at > now
    ]
    return CoParentsOut(members=members, pending=pending)


@app.post(
    "/family/{family_id}/co-parents/invitations",
    response_model=InvitationCreatedOut,
)
def invite_co_parent(
    payload: CoParentInviteCreateIn = Body(default=CoParentInviteCreateIn()),
    access: FamilyAccess = Depends(require_family_parent),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationCreatedOut:
    birth = births_repo.primary_birth_for_family(db, access.family.id)
    if birth is None:
        raise HTTPException(
            status_code=400,
            detail="Add a birth before inviting a co-parent",
        )
    invitation, plaintext_token = invitations_repo.create_invitation(
        db,
        family_id=access.family.id,
        birth_id=birth.id,
        invited_by_user_id=current_user.id,
        display_name_hint=payload.display_name_hint,
        email_hint=payload.email_hint,
        phone_hint=payload.phone_hint,
        role=FamilyRole.co_parent,
    )
    db.commit()
    db.refresh(invitation)
    return InvitationCreatedOut(
        **InvitationOut.model_validate(invitation).model_dump(),
        token=plaintext_token,
        invite_url=_invitation_url(plaintext_token),
    )


@app.delete(
    "/family/{family_id}/co-parents/invitations/{invitation_id}",
    status_code=204,
)
def revoke_co_parent_invitation(
    invitation_id: uuid.UUID,
    access: FamilyAccess = Depends(require_family_parent),
    db: Session = Depends(get_db),
) -> Response:
    invitation = db.get(ViewerInvitation, invitation_id)
    if (
        invitation is None
        or invitation.family_id != access.family.id
        or invitation.role != FamilyRole.co_parent
    ):
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitations_repo.revoke(db, invitation)
    db.commit()
    return Response(status_code=204)


@app.get("/media/{media_id}", response_model=None)
def get_media(
    media_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> FileResponse | RedirectResponse:
    asset = media_repo.get_media_asset(db, media_id)
    if asset is None or not asset.is_visible_to_viewers:
        raise HTTPException(status_code=404, detail="Media not found")
    if not _media_visible_to(db, asset, current_user):
        raise HTTPException(status_code=404, detail="Media not found")

    if media_repo.is_local_key(asset.original_s3_key):
        rel = media_repo.local_path(asset.original_s3_key)
        path = (Path(__file__).parent / rel).resolve()
        upload_root = UPLOAD_DIR.resolve()
        if not path.is_file() or upload_root not in path.parents:
            raise HTTPException(status_code=404, detail="Media file missing")
        media_type = (
            asset.mime_type
            or mimetypes.guess_type(str(path))[0]
            or "application/octet-stream"
        )
        return FileResponse(path, media_type=media_type)

    url = presigned_get_url(asset.original_s3_key)
    return RedirectResponse(url, status_code=307)


# ============ SSE ============


@app.get("/birth/{birth_id}/stream")
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


@app.get("/b/{slug}/stream")
async def stream_public(
    request: Request,
    slug: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    birth = _resolve_public_birth(db, slug)
    visible = _scope_set_for_visitor(db, birth, current_user)
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


# ============ helpers ============


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


def _serialize_event_out(
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


def _serialize_events_with_engagement(
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
        _serialize_event_out(
            e,
            reactions=reactions_map.get(e.id),
            comment_count=comment_counts.get(e.id, 0),
        )
        for e in events
    ]


def _serialize_event_with_engagement(
    db: Session,
    event: TimelineEvent,
    *,
    requester_user_id: uuid.UUID | None,
) -> TimelineEventOut:
    return _serialize_events_with_engagement(
        db, [event], requester_user_id=requester_user_id
    )[0]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
