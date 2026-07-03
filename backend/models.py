"""SQLAlchemy ORM models for the multi-tenant Lily domain.

See `Lily-Product-Spec.md` for the canonical schema. Enums are declared as
Postgres native types via `sa.Enum(..., native_enum=True)`.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class FamilyRole(str, enum.Enum):
    owner = "owner"
    co_parent = "co_parent"
    family_viewer = "family_viewer"


class BirthStatus(str, enum.Enum):
    preparing = "preparing"
    in_labor = "in_labor"
    born = "born"
    archived = "archived"


class BirthStorageTier(str, enum.Enum):
    active = "active"
    cold = "cold"
    archived = "archived"


class TimelineEventType(str, enum.Enum):
    contraction = "contraction"
    milestone = "milestone"
    text_note = "text_note"
    photo = "photo"
    video = "video"
    voice_memo = "voice_memo"


class AudienceScope(str, enum.Enum):
    public = "public"
    group_targeted = "group_targeted"
    parents_only = "parents_only"


class MediaKind(str, enum.Enum):
    photo = "photo"
    video = "video"
    voice_memo = "voice_memo"


class MediaStorageTier(str, enum.Enum):
    hot = "hot"
    cold = "cold"


class AuthIdentifierKind(str, enum.Enum):
    email = "email"
    phone = "phone"


class GiftKind(str, enum.Enum):
    physical = "physical"
    storage_gift = "storage_gift"
    free_digital = "free_digital"


class GiftRenderingStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ReactionKind(str, enum.Enum):
    """The curated set of feelings we let people express on an event.

    Three is intentional. See `Lily-Personas.md` — Janet leaves "a heart on
    the belly photo" and "hearts on every milestone"; the unlock exists
    precisely because reactions alone can't carry what someone actually
    wants to say. A bigger palette would dilute that gap.
    """

    love = "love"
    wow = "wow"
    pray = "pray"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    memberships: Mapped[list["FamilyMembership"]] = relationship(back_populates="user")

    __table_args__ = (
        sa.Index(
            "ix_users_email_unique",
            "email",
            unique=True,
            postgresql_where=sa.text("email IS NOT NULL"),
        ),
        sa.Index(
            "ix_users_phone_unique",
            "phone",
            unique=True,
            postgresql_where=sa.text("phone IS NOT NULL"),
        ),
        sa.CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="ck_users_email_or_phone",
        ),
    )


class Family(Base):
    __tablename__ = "families"

    id: Mapped[uuid.UUID] = _uuid_pk()
    primary_owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    memberships: Mapped[list["FamilyMembership"]] = relationship(back_populates="family")
    births: Mapped[list["Birth"]] = relationship(back_populates="family")


class FamilyMembership(Base):
    __tablename__ = "family_memberships"

    id: Mapped[uuid.UUID] = _uuid_pk()
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[FamilyRole] = mapped_column(
        sa.Enum(FamilyRole, name="family_role", native_enum=True),
        nullable=False,
    )
    joined_at: Mapped[datetime] = _created_at()

    family: Mapped[Family] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")

    __table_args__ = (
        sa.UniqueConstraint("family_id", "user_id", name="uq_family_memberships_family_user"),
    )


class Birth(Base):
    __tablename__ = "births"

    id: Mapped[uuid.UUID] = _uuid_pk()
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    child_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    child_dob: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    slug: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    status: Mapped[BirthStatus] = mapped_column(
        sa.Enum(BirthStatus, name="birth_status", native_enum=True),
        nullable=False,
        server_default=BirthStatus.preparing.value,
    )
    birth_started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    birth_completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    storage_tier: Mapped[BirthStorageTier] = mapped_column(
        sa.Enum(BirthStorageTier, name="birth_storage_tier", native_enum=True),
        nullable=False,
        server_default=BirthStorageTier.active.value,
    )
    is_unlocked: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    unlocked_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    unlocked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_locked_to_invited: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    theme: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="lily"
    )
    # Actual measurements, recorded by the parents once known. The family's
    # guesses live in `birth_guesses` and are scored against these.
    child_weight_lbs: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    child_length_in: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    family: Mapped[Family] = relationship(back_populates="births")
    events: Mapped[list["TimelineEvent"]] = relationship(back_populates="birth")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    birth_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("births.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[TimelineEventType] = mapped_column(
        sa.Enum(TimelineEventType, name="timeline_event_type", native_enum=True),
        nullable=False,
    )
    sequence_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    posted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    posted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    audience_scope: Mapped[AudienceScope] = mapped_column(
        sa.Enum(AudienceScope, name="audience_scope", native_enum=True),
        nullable=False,
        server_default=AudienceScope.public.value,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    birth: Mapped[Birth] = relationship(back_populates="events")

    __table_args__ = (
        sa.UniqueConstraint("birth_id", "sequence_id", name="uq_timeline_events_birth_seq"),
        sa.Index("ix_timeline_events_birth_occurred", "birth_id", "occurred_at"),
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    birth_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("births.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[MediaKind] = mapped_column(
        sa.Enum(MediaKind, name="media_kind", native_enum=True),
        nullable=False,
    )
    original_s3_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    hot_s3_key: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    cold_s3_key: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    storage_tier: Mapped[MediaStorageTier] = mapped_column(
        sa.Enum(MediaStorageTier, name="media_storage_tier", native_enum=True),
        nullable=False,
        server_default=MediaStorageTier.hot.value,
    )
    width: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    bytes: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_visible_to_viewers: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )
    created_at: Mapped[datetime] = _created_at()
    archived_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )


class ViewerInvitation(Base):
    """A shareable invitation that grants a recipient `family_viewer`
    access to a specific birth after they verify their email/phone.

    The token sent to the recipient is `{invitation_id}.{secret}`. Only
    the salted hash of the secret is stored, mirroring how AuthChallenge
    handles magic-link secrets.

    Multi-use by default — the same link can be redeemed by anyone in the
    family group chat. `revoked_at` is the kill switch; `expires_at` is
    the natural time-out.
    """

    __tablename__ = "viewer_invitations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    birth_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("births.id", ondelete="CASCADE"),
        nullable=False,
    )
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[FamilyRole] = mapped_column(
        sa.Enum(FamilyRole, name="family_role", native_enum=True, create_type=False),
        nullable=False,
        server_default=FamilyRole.family_viewer.value,
    )
    salt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # Plaintext token, kept so parents can re-copy the link to re-share.
    # A deliberate exception to the hash-only rule: a viewer link is
    # low-stakes (multi-use, expiring, revocable, view-only access), unlike
    # auth magic links. Null for invitations created before this existed.
    token: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    display_name_hint: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    email_hint: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    phone_hint: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    redemption_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        sa.Index("ix_viewer_invitations_birth", "birth_id"),
    )


class ViewerInvitationRedemption(Base):
    """One person's redemption of a specific invite link. Lets parents see
    *who* came in through a link and *when* — the `redemption_count` on the
    invitation only ever counted clicks, never identities.

    Unique on (invitation_id, user_id): re-following the same link doesn't
    create a second row, so the list shows distinct people.
    """

    __tablename__ = "viewer_invitation_redemptions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    invitation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("viewer_invitations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    redeemed_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        sa.UniqueConstraint(
            "invitation_id", "user_id", name="uq_invitation_redemption"
        ),
        sa.Index("ix_invitation_redemptions_invitation", "invitation_id"),
    )


class TimelineEventReaction(Base):
    """One user's reaction-of-a-given-kind on a specific event. The unique
    constraint on (event_id, user_id, kind) makes the API idempotent — a
    user can toggle a reaction on/off, but can't accidentally double-count.
    Multi-kind is supported (Janet can leave both love and pray on the
    same milestone).

    Reactions are free-tier; the unlock gate only applies to comments.
    """

    __tablename__ = "timeline_event_reactions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("timeline_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[ReactionKind] = mapped_column(
        sa.Enum(ReactionKind, name="reaction_kind", native_enum=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        sa.UniqueConstraint(
            "event_id",
            "user_id",
            "kind",
            name="uq_timeline_event_reactions_event_user_kind",
        ),
        sa.Index("ix_timeline_event_reactions_event", "event_id"),
    )


class TimelineEventComment(Base):
    """A family member's message on an event. Soft-deleted (not hard) so
    we can recover after honest mistakes and so deleted messages don't
    silently vanish from family memory. The 18-year-from-now case is the
    one that matters here — Janet's comment on labor day must still exist
    when Sarah's daughter logs in for the first time.

    Comments are gated behind `birth.is_unlocked`. Parents can still post
    while locked (they own the page); viewers can't post until the unlock
    is paid for. The check lives at the route layer.
    """

    __tablename__ = "timeline_event_comments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("timeline_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        sa.Index("ix_timeline_event_comments_event", "event_id"),
    )


class AuthChallenge(Base):
    """Short-lived auth challenges. Two valid completion paths:
    - email magic link: client follows `/auth/verify?token=<token>` URL
    - SMS / email OTP: client posts `{identifier, code}` to /auth/verify

    `code_hash` and `magic_link_token_hash` both populated; either one can
    redeem the challenge. Stored as `sha256(salt || secret)` hex.
    """

    __tablename__ = "auth_challenges"

    id: Mapped[uuid.UUID] = _uuid_pk()
    identifier: Mapped[str] = mapped_column(sa.Text, nullable=False)
    identifier_kind: Mapped[AuthIdentifierKind] = mapped_column(
        sa.Enum(AuthIdentifierKind, name="auth_identifier_kind", native_enum=True),
        nullable=False,
    )
    salt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    code_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    magic_link_token_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        sa.Index("ix_auth_challenges_identifier", "identifier"),
    )


class GiftCatalogItem(Base):
    """A purchasable gift product (mug, announcement cards, storage gift).

    `product_kind` is plain text, not an enum: adding a new product is a
    seed row, not a migration. `template_metadata` lists which template ids
    (see `gift_templates.py`) are valid for this product plus product-level
    render params. Price / SKU / `surfaces_in` are stored now but unused
    until the payment + Gelato + day-two-prompt phases land.
    """

    __tablename__ = "gift_catalog_items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[GiftKind] = mapped_column(
        sa.Enum(GiftKind, name="gift_kind", native_enum=True),
        nullable=False,
    )
    product_kind: Mapped[str] = mapped_column(sa.Text, nullable=False)
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    base_price_cents: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    fulfillment_partner: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    fulfillment_sku: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    template_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    storage_years_granted: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    surfaces_in: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class GiftRendering(Base):
    """One generated artwork for a (birth, catalog item, template).

    The artwork is the design that goes *on* the product, generated from the
    birth's timeline + a hero photo. `artwork_s3_key` is the storage key —
    presign at read, never store a URL. Storage gifts have no artwork and
    never get a rendering row.
    """

    __tablename__ = "gift_renderings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    birth_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("births.id", ondelete="CASCADE"),
        nullable=False,
    )
    gift_catalog_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("gift_catalog_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    template_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[GiftRenderingStatus] = mapped_column(
        sa.Enum(GiftRenderingStatus, name="gift_rendering_status", native_enum=True),
        nullable=False,
        server_default=GiftRenderingStatus.pending.value,
    )
    artwork_s3_key: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # Product mockup from the fulfillment partner (e.g. Printful) — the
    # artwork rendered onto the real product. Downloaded into our S3 for
    # permanence. mockup_status: 'none' | 'pending' | 'ready' | 'failed'.
    mockup_s3_key: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    mockup_status: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="none"
    )
    rendering_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    failure_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_visible_to_viewers: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    __table_args__ = (
        sa.Index("ix_gift_renderings_birth", "birth_id"),
        sa.Index(
            "uq_gift_renderings_birth_item_template",
            "birth_id",
            "gift_catalog_item_id",
            "template_id",
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
    )


class GiftRenderingMockup(Base):
    """A product mockup of one rendering's artwork on a specific shortlist
    product (see `fulfillment/products.py`). Generated on demand for the "see
    this design on another product" picker and cached — one row per
    (rendering, product_key). `status`: 'pending' | 'ready' | 'failed'."""

    __tablename__ = "gift_rendering_mockups"

    id: Mapped[uuid.UUID] = _uuid_pk()
    gift_rendering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("gift_renderings.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="pending"
    )
    mockup_s3_key: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    __table_args__ = (
        sa.Index(
            "ix_gift_rendering_mockups_rendering", "gift_rendering_id"
        ),
        sa.UniqueConstraint(
            "gift_rendering_id",
            "product_key",
            name="uq_gift_rendering_mockups_rendering_product",
        ),
    )


class BirthGuess(Base):
    """One family member's guess at the baby's weight/length — the family
    pool. `user_id` links a signed-in guesser (one guess per user per birth,
    editable until the birth); name-only rows (`user_id` NULL) come from
    imports or parent-entered guesses for relatives without accounts.
    `display_name` is snapshotted at write time so the pool reads the same
    even if the account is renamed or removed later."""

    __tablename__ = "birth_guesses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    birth_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("births.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    weight_lbs: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    length_in: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    __table_args__ = (
        sa.Index("ix_birth_guesses_birth", "birth_id"),
        sa.Index(
            "uq_birth_guesses_birth_user",
            "birth_id",
            "user_id",
            unique=True,
            postgresql_where=sa.text("user_id IS NOT NULL"),
        ),
    )


class UnlockPurchase(Base):
    """The $12 family unlock, recorded. UNIQUE(birth_id) is the spec's
    one-successful-purchase-per-birth invariant — a racing second payment is
    refunded and never recorded. The payment-intent unique is a cheap extra
    invariant (one payment can't buy two births)."""

    __tablename__ = "unlock_purchases"

    id: Mapped[uuid.UUID] = _uuid_pk()
    birth_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("births.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    purchased_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="usd"
    )
    stripe_payment_intent_id: Mapped[str] = mapped_column(
        sa.Text, nullable=False, unique=True
    )
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    purchased_at: Mapped[datetime] = _created_at()
