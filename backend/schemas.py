"""Pydantic schemas for API boundaries.

`TimelineEventPayload` uses a discriminated union keyed on `type`, so each
event variant is fully parsed once at the boundary. After parsing, internal
code can trust the types without further checks (parse, don't validate).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models import (
    AudienceScope,
    AuthIdentifierKind,
    BirthStatus,
    FamilyRole,
    MediaKind,
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


class MeOut(BaseModel):
    user: UserOut
    memberships: list[FamilyMembershipOut]


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
    """Either {identifier, code} (OTP) or {token} (magic link)."""

    identifier: Optional[str] = None
    code: Optional[str] = None
    token: Optional[str] = None


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


class StopContractionIn(BaseModel):
    end_time: datetime


# Convenience for tests / fixtures that need to validate an EmailStr-shaped
# value without importing pydantic.EmailStr at call sites.
EmailString = EmailStr
