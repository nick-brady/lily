"""Pydantic schemas for API boundaries.

`TimelineEventPayload` uses a discriminated union keyed on `type`, so each
event variant is fully parsed once at the boundary. After parsing, internal
code can trust the types without further checks (parse, don't validate).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models import (
    AudienceScope,
    AuthIdentifierKind,
    BirthStatus,
    FamilyRole,
    GiftKind,
    GiftRenderingStatus,
    MediaKind,
    ReactionKind,
    TimelineEventType,
)


class ContractionPayload(BaseModel):
    type: Literal["contraction"] = "contraction"
    duration_seconds: Optional[int] = None
    end_time: Optional[datetime] = None
    gap_before_seconds: Optional[int] = None


class MilestonePayload(BaseModel):
    type: Literal["milestone"] = "milestone"
    kind: str
    title: Optional[str] = None
    body: Optional[str] = None


class TextNotePayload(BaseModel):
    type: Literal["text_note"] = "text_note"
    body: str


class PhotoPayload(BaseModel):
    type: Literal["photo"] = "photo"
    media_id: uuid.UUID
    caption: Optional[str] = None


class VideoPayload(BaseModel):
    type: Literal["video"] = "video"
    media_id: uuid.UUID
    caption: Optional[str] = None


class VoiceMemoPayload(BaseModel):
    type: Literal["voice_memo"] = "voice_memo"
    media_id: uuid.UUID
    duration_seconds: Optional[int] = None
    transcript_optional: Optional[str] = None


TimelineEventPayload = Annotated[
    Union[
        ContractionPayload,
        MilestonePayload,
        TextNotePayload,
        PhotoPayload,
        VideoPayload,
        VoiceMemoPayload,
    ],
    Field(discriminator="type"),
]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: Optional[str] = None
    phone: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class FamilyMembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    role: FamilyRole


class MeUpdateIn(BaseModel):
    """Edit your own profile. Today just the display name family sees on
    comments; room to grow (avatar, contact prefs).
    """

    display_name: str = Field(..., min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name can't be blank")
        return cleaned


class MeOut(BaseModel):
    user: UserOut
    memberships: list[FamilyMembershipOut]
    families: list["FamilyWithBirthsOut"]


class FamilyWithBirthsOut(BaseModel):
    id: uuid.UUID
    display_name: str
    role: FamilyRole
    births: list["BirthOut"]


class BirthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    child_name: Optional[str] = None
    child_dob: Optional[datetime] = None
    slug: str
    status: BirthStatus
    birth_started_at: Optional[datetime] = None
    birth_completed_at: Optional[datetime] = None
    is_unlocked: bool
    is_locked_to_invited: bool
    theme: str = "lily"


class ReactionCountOut(BaseModel):
    """Per-kind reaction summary on an event.

    `mine: false` is also returned for anonymous viewers — anon users
    can't react, but they still see counts (this is core to the brand;
    Aunt Linda scanning a QR card 18 years from now should feel the
    love poured in).
    """

    count: int
    mine: bool


class TimelineEventOut(BaseModel):
    id: uuid.UUID
    birth_id: uuid.UUID
    event_type: TimelineEventType
    sequence_id: int
    occurred_at: datetime
    posted_at: datetime
    posted_by_user_id: uuid.UUID
    payload: dict
    audience_scope: AudienceScope
    reactions: dict[ReactionKind, ReactionCountOut] = Field(default_factory=dict)
    comment_count: int = 0


class ReactionToggleIn(BaseModel):
    kind: ReactionKind


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    user_id: uuid.UUID
    author_name: Optional[str] = None
    body: str
    created_at: datetime
    updated_at: datetime


class CommentCreateIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class CommentEditIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class MediaAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    birth_id: uuid.UUID
    kind: MediaKind
    original_s3_key: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[int] = None
    mime_type: Optional[str] = None


class AuthRequestIn(BaseModel):
    identifier: str = Field(..., description="email address or phone number")


class AuthRequestOut(BaseModel):
    identifier_kind: AuthIdentifierKind
    expires_in_seconds: int


class AuthVerifyIn(BaseModel):
    """Either {identifier, code} (OTP) or {token} (magic link).

    An optional `invite_token` redeems a viewer invitation atomically with
    the auth — saves a round trip during the invite flow.
    """

    identifier: Optional[str] = None
    code: Optional[str] = None
    token: Optional[str] = None
    invite_token: Optional[str] = None


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


class CreateTextNoteIn(BaseModel):
    body: str
    occurred_at: Optional[datetime] = None
    audience_scope: AudienceScope = AudienceScope.public


class CreateMilestoneIn(BaseModel):
    kind: str
    title: Optional[str] = None
    body: Optional[str] = None
    occurred_at: Optional[datetime] = None
    audience_scope: AudienceScope = AudienceScope.public


class StartContractionIn(BaseModel):
    occurred_at: Optional[datetime] = None
    audience_scope: AudienceScope = AudienceScope.public


class StopContractionIn(BaseModel):
    end_time: datetime


class InvitationCreateIn(BaseModel):
    display_name_hint: Optional[str] = None
    email_hint: Optional[str] = None
    phone_hint: Optional[str] = None


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    birth_id: uuid.UUID
    invited_by_user_id: uuid.UUID
    role: FamilyRole
    display_name_hint: Optional[str] = None
    email_hint: Optional[str] = None
    phone_hint: Optional[str] = None
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    redemption_count: int
    created_at: datetime
    # Re-copyable share link, present when the plaintext token was stored.
    invite_url: Optional[str] = None


class InvitationCreatedOut(InvitationOut):
    """One-time payload returned on creation. The plaintext token and URL
    are only available here; subsequent reads return only the hash-side
    metadata.
    """

    token: str
    invite_url: str


class InvitationRedemptionOut(BaseModel):
    """Who joined through an invite link, and when.

    Email and phone are shown in full to the parents managing the link —
    these are family members the parents already know, and the contact
    detail helps them recognise who's behind a name. `role` lets the UI
    only offer "remove" for plain viewers (never for a co-parent/owner who
    happened to follow a viewer link).
    """

    user_id: uuid.UUID
    display_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: FamilyRole
    redeemed_at: datetime


class InvitationContextOut(BaseModel):
    """Public lookup payload for `GET /invite/{token}`. Just enough to
    render a meaningful redeem screen without leaking family internals.
    """

    family_display_name: str
    birth_id: uuid.UUID
    birth_slug: str
    birth_child_name: Optional[str] = None
    display_name_hint: Optional[str] = None
    email_hint: Optional[str] = None
    phone_hint: Optional[str] = None
    expires_at: datetime
    role: FamilyRole


class BabyBornIn(BaseModel):
    """The Baby Born! action. `occurred_at` defaults to now; `body` is an
    optional note that rides along on the milestone (e.g. weight, time).
    """

    occurred_at: Optional[datetime] = None
    body: Optional[str] = None


class CoParentInviteCreateIn(BaseModel):
    """Invite a co-parent to the family. The grant is family-wide; the
    backend attaches it to a representative birth for the welcome screen.
    """

    display_name_hint: Optional[str] = None
    email_hint: Optional[str] = None
    phone_hint: Optional[str] = None


class CoParentMemberOut(BaseModel):
    user_id: uuid.UUID
    display_name: Optional[str] = None
    contact: Optional[str] = None
    role: FamilyRole
    is_self: bool


class PendingCoParentInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name_hint: Optional[str] = None
    email_hint: Optional[str] = None
    phone_hint: Optional[str] = None
    expires_at: datetime
    redemption_count: int


class CoParentsOut(BaseModel):
    members: list[CoParentMemberOut]
    pending: list[PendingCoParentInviteOut]


class InvitationRedeemIn(BaseModel):
    """Used by an already-authenticated user to attach themselves to a
    family via an invite link. The unauthenticated redeem path goes
    through /auth/verify with `invite_token` instead.
    """


class EditEventIn(BaseModel):
    """Patch the editable parts of a timeline event's payload.

    For text_note: `body`. For milestone: `title` / `body`. For photo /
    video / voice_memo: `caption`. Unknown keys are ignored; the
    repository merges the patch into the existing payload.
    """

    body: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    transcript_optional: Optional[str] = None


# Keep in sync with frontend/src/utils/themes.js THEMES (current ids only,
# not the legacy read-side aliases).
ALLOWED_THEMES = frozenset({"lily", "blossom", "dino", "ocean", "golden", "starry"})


class BirthCreateIn(BaseModel):
    baby_name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    theme: str = Field(default="lily", max_length=50)


class BirthUpdateIn(BaseModel):
    theme: Optional[str] = Field(default=None, max_length=50)

    @field_validator("theme")
    @classmethod
    def _validate_theme(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ALLOWED_THEMES:
            raise ValueError("Unknown theme")
        return value


class SlugAvailableOut(BaseModel):
    available: bool
    suggestion: Optional[str] = None


class GiftRenderingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template_id: str
    status: GiftRenderingStatus
    artwork_url: Optional[str] = None
    mockup_url: Optional[str] = None
    mockup_status: str = "none"
    is_visible_to_viewers: bool


class GiftItemOut(BaseModel):
    """A catalog item plus its generated renderings for a birth. Storage
    gifts (no artwork) come back with an empty `renderings` list."""

    id: uuid.UUID
    kind: GiftKind
    product_kind: str
    display_name: str
    base_price_cents: int
    storage_years_granted: Optional[int] = None
    renderings: list[GiftRenderingOut] = []


class GiftRenderingPatchIn(BaseModel):
    is_visible_to_viewers: bool


class ProductMockupOut(BaseModel):
    """One shortlist product for the "see this design on another product"
    picker. `status`: 'none' (never requested) | 'pending' | 'ready' |
    'failed'. `mockup_url` is set only when ready."""

    product_key: str
    display_name: str
    status: str = "none"
    mockup_url: Optional[str] = None


class RenderingProductsOut(BaseModel):
    rendering_id: uuid.UUID
    products: list[ProductMockupOut] = []


# Convenience for tests / fixtures that need to validate an EmailStr-shaped
# value without importing pydantic.EmailStr at call sites.
EmailString = EmailStr

MeOut.model_rebuild()
FamilyWithBirthsOut.model_rebuild()
