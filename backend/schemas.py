"""Pydantic schemas for API boundaries.

`TimelineEventPayload` uses a discriminated union keyed on `type`, so each
event variant is fully parsed once at the boundary. After parsing, internal
code can trust the types without further checks (parse, don't validate).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal, Optional, Union

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

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
    # The birth-events-only text opt-in; None means not opted in.
    notify_phone: Optional[str] = None


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
    # Who is already in here, excluding the caller. Membership is family-wide,
    # not per-birth, so everyone named below carries over to any new page added
    # to this family — including every viewer who ever redeemed an invite. The
    # setup chooser lists these people instead of asking the user to reason
    # about a container called "family", which promises a small intimate unit
    # and is actually the whole guest list.
    co_parent_names: list[str] = []
    viewer_count: int = 0


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
    is_locked_to_invited: bool
    theme: str = "lily"
    due_date: Optional[date] = None
    gender_pool_enabled: bool = False
    child_weight_lbs: Optional[float] = None
    child_length_in: Optional[float] = None


class GuessIn(BaseModel):
    """A family member's guess. At least one field must be given
    (validated at the route so the error message can be friendly).
    `sex_guess` is accepted only while the birth's gender pool is on;
    `date_guess` only until labor starts. Omitting a field preserves any
    previously-guessed value (the route distinguishes absent from null via
    model_fields_set)."""

    weight_lbs: Optional[float] = Field(default=None, gt=0, lt=30)
    length_in: Optional[float] = Field(default=None, gt=0, lt=40)
    sex_guess: Optional[Literal["boy", "girl"]] = None
    date_guess: Optional[date] = None


class GuessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    weight_lbs: Optional[float] = None
    length_in: Optional[float] = None
    sex_guess: Optional[str] = None
    date_guess: Optional[date] = None
    is_mine: bool = False
    # Everything below is set only once the actual measurements are recorded.
    # Three medals, one per dimension — pounds, inches and days have no
    # exchange rate, so they're never combined into one number. Ties share.
    rank: Optional[int] = None  # weight order; gold is rank 1
    weight_winner: bool = False  # 🏆
    length_winner: bool = False  # 🥈
    date_winner: bool = False  # 🥉
    # How close each guess actually was. Shown on the board so a medal
    # explains itself — most of the "that's not fair" comes from the numbers
    # being invisible.
    weight_delta_lbs: Optional[float] = None
    length_delta_in: Optional[float] = None
    date_delta_days: Optional[int] = None
    # Guesses stay editable until the birth, so the board shows its own
    # provenance instead of locking: a settled row whose updated_at drifted
    # from created_at reads "guessed Jul 12 · updated Aug 14". Visibility is
    # the deterrent; there is no calendar freeze.
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GuessBoardOut(BaseModel):
    """The guessing jar: everyone's guesses, plus the actuals and ranking
    once the parents record the measurements. Pre-settle, other people's
    guess VALUES are sealed server-side (names visible, numbers null) —
    no anchoring, no spoiled reveal."""

    guesses: list[GuessOut] = []
    actual_weight_lbs: Optional[float] = None
    actual_length_in: Optional[float] = None
    actual_sex: Optional[str] = None
    actual_date: Optional[date] = None
    settled: bool = False
    gender_pool_enabled: bool = False
    # prefills the arrival-day guess ("when do YOU think?" starts at the
    # official answer)
    due_date: Optional[date] = None


class ShippingAddressIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    line1: str = Field(..., min_length=1, max_length=200)
    line2: Optional[str] = Field(default=None, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=50)
    postal_code: str = Field(..., min_length=1, max_length=20)
    country: str = Field(default="US", min_length=2, max_length=2)


class GiftCheckoutIn(BaseModel):
    # "both" = a family copy and a self copy in one checkout (quantity 2)
    recipient_kind: str = Field(..., pattern="^(family|self|both)$")
    gift_message: Optional[str] = Field(default=None, max_length=500)
    # Where each copy goes. The buyer names them here rather than on Stripe's
    # page, which collects exactly one address per session — the reason
    # "both" used to be refused unless the parents had saved theirs.
    # `family_address` is unnecessary (and ignored) when they have.
    family_address: Optional[ShippingAddressIn] = None
    self_address: Optional[ShippingAddressIn] = None


class ShippingQuoteIn(BaseModel):
    """Where one parcel is going. `address` is unnecessary for a family copy
    when the parents have saved theirs — it's read on the server and never
    shown to the buyer."""

    recipient_kind: str = Field(..., pattern="^(family|self)$")
    address: Optional[ShippingAddressIn] = None


class ShippingQuoteOut(BaseModel):
    """What posting one parcel there costs — the partner's live rate, or our
    flat stand-in when `estimated`."""

    shipping_cents: int
    estimated: bool
    service: str
    # The item's own price for this design — catalog price plus the chosen
    # product's surcharge — so the sheet's total is the checkout's, not a guess.
    item_cents: int
    min_days: Optional[int] = None
    max_days: Optional[int] = None


class AddressReviewIn(BaseModel):
    address: ShippingAddressIn


class AddressReviewOut(BaseModel):
    """What we make of an address before anyone pays for it.

    `verdict` is confirmed | corrected | unconfirmed | unchecked. Only
    `structure_error` refuses the address; the rest is advice, because a real
    address that a postal database hasn't heard of is still a real address.
    """

    verdict: str
    suggestion: Optional[dict] = None
    structure_error: Optional[str] = None


class StorageGiftCheckoutIn(BaseModel):
    """Storage gifts always go to the family — no recipient choice, no
    shipping — so this is just the optional note from the giver."""

    gift_message: Optional[str] = Field(default=None, max_length=500)


class GiftCheckoutOut(BaseModel):
    url: str


class GiftConfirmIn(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=255)


class GiftConfirmOut(BaseModel):
    """`status`: 'fulfilled' | 'already_processed' | 'refunded' (this buyer
    lost the family-claim race and their payment was returned) | 'pending'."""

    status: str


class ShippingAddressOut(BaseModel):
    address: Optional[dict] = None


class GiftOrderAdminOut(BaseModel):
    """A received gift, for the parents: who sent what, their note, and
    where fulfillment stands."""

    id: uuid.UUID
    status: str
    recipient_kind: str
    gift_message: Optional[str] = None
    amount_cents: int
    shipping_cents: int = 0
    purchased_by: Optional[str] = None
    item_display_name: str
    fulfillment_status: str = "none"
    fulfillment_failure: Optional[str] = None
    carrier: Optional[str] = None
    tracking_url: Optional[str] = None
    shipped_at: Optional[datetime] = None
    created_at: datetime


class OrderReceiptLineOut(BaseModel):
    """One order as the buyer may see it after paying: what it is, where it
    is going (city and state only), what it cost them, and where it stands.
    Nothing here is a secret — the order id is the key to the page, and
    the page shows no email, no street, no partner or payment ids."""

    id: uuid.UUID
    reference: str  # eight characters of the id, what they quote
    status: str  # pending | paid | refunded
    fulfillment_status: str  # none | submitting | submitted | failed
    recipient_kind: str  # family | self
    item_display_name: str
    product_display_name: Optional[str] = None
    image_url: Optional[str] = None
    destination: Optional[str] = None  # "Raleigh, NC"
    product_price_cents: int
    shipping_cents: int
    amount_cents: int
    gift_message: Optional[str] = None
    # once the printer's webhook says the parcel left
    carrier: Optional[str] = None
    tracking_url: Optional[str] = None
    shipped_at: Optional[datetime] = None
    created_at: datetime


class MyOrderOut(OrderReceiptLineOut):
    """A past purchase on the buyer's own orders page: the receipt line,
    plus which page it was for."""

    slug: str
    child_name: Optional[str] = None


class OrderReceiptOut(BaseModel):
    slug: str
    child_name: Optional[str] = None
    theme: str = "lily"
    orders: list[OrderReceiptLineOut]


class ReactionCountOut(BaseModel):
    """Per-kind reaction summary on an event.

    `mine: false` is also returned for anonymous viewers — anon users
    can't react, but they still see counts (this is core to the brand;
    Aunt Linda scanning a QR card 18 years from now should feel the
    love poured in).
    """

    count: int
    mine: bool


# Backdating is the point — posts get logged after the fact all day ("water
# broke at 2am", typed at 7am), and the arrival itself is almost always
# recorded once someone has a free hand. Forward-dating is never legitimate:
# nothing on a birth timeline has happened yet in the future, and a
# future-stamped event pins itself above the whole story permanently.
#
# The skew allowance is for client clocks, not for intent. Phones and laptops
# drift by seconds, and rejecting someone's own "now" would be a worse failure
# than accepting a stamp a minute early.
_CLOCK_SKEW_ALLOWANCE = timedelta(minutes=2)


def _already_happened(value: datetime) -> datetime:
    # Naive input is treated as UTC — the API is UTC everywhere, and comparing
    # a naive datetime against an aware one raises instead of rejecting.
    when = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if when > datetime.now(timezone.utc) + _CLOCK_SKEW_ALLOWANCE:
        raise ValueError("that time is in the future — pick a time that's already happened")
    return value


PastDatetime = Annotated[datetime, AfterValidator(_already_happened)]


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
    identifier: str = Field(..., description="email address (identity is email-keyed)")


class AuthRequestOut(BaseModel):
    identifier_kind: AuthIdentifierKind
    expires_in_seconds: int


class AuthVerifyIn(BaseModel):
    """{identifier, code} — the email OTP path. Magic links are retired.

    An optional `invite_token` redeems a viewer invitation atomically with
    the auth — saves a round trip during the invite flow.
    """

    identifier: Optional[str] = None
    code: Optional[str] = None
    invite_token: Optional[str] = None
    # First-touch acquisition attribution, forwarded from the landing-page
    # capture. Recorded only when this verify creates a brand-new user.
    ref: Optional[str] = Field(default=None, max_length=128)
    utm_source: Optional[str] = Field(default=None, max_length=128)
    utm_medium: Optional[str] = Field(default=None, max_length=128)
    utm_campaign: Optional[str] = Field(default=None, max_length=128)


class GoogleAuthIn(BaseModel):
    """Google Identity Services ID token — verified server-side and resolved
    to the same email-keyed identity as the OTP path."""

    credential: str
    invite_token: Optional[str] = None
    ref: Optional[str] = Field(default=None, max_length=128)
    utm_source: Optional[str] = Field(default=None, max_length=128)
    utm_medium: Optional[str] = Field(default=None, max_length=128)
    utm_campaign: Optional[str] = Field(default=None, max_length=128)


class NotifyPhoneIn(BaseModel):
    """Opt in to birth-event texts — the only thing SMS ever carries."""

    phone: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


class CreateTextNoteIn(BaseModel):
    body: str
    occurred_at: Optional[PastDatetime] = None
    audience_scope: AudienceScope = AudienceScope.group_targeted


class CreateMilestoneIn(BaseModel):
    kind: str
    title: Optional[str] = None
    body: Optional[str] = None
    occurred_at: Optional[PastDatetime] = None
    audience_scope: AudienceScope = AudienceScope.group_targeted


class StartContractionIn(BaseModel):
    occurred_at: Optional[PastDatetime] = None
    audience_scope: AudienceScope = AudienceScope.group_targeted


class StopContractionIn(BaseModel):
    # A contraction that ends in the future would report a duration longer
    # than it lasted, so this gets the same bound.
    end_time: PastDatetime


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
    # True if we auto-delivered the invite via email/SMS. False when no
    # contact was given, or delivery failed — either way the link above
    # still works, so creation never fails just because sending did.
    sent: bool = False


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
    # The preview. `/b/{slug}` used to answer this to anyone who had the
    # URL — and answered with the whole birth, measurements and labour
    # timestamps included. It belongs here, where a token vouches for the
    # asker, and it carries only what the invite screen draws.
    birth_status: BirthStatus
    birth_theme: str = "lily"
    birth_completed_at: Optional[datetime] = None
    display_name_hint: Optional[str] = None
    email_hint: Optional[str] = None
    phone_hint: Optional[str] = None
    expires_at: datetime
    role: FamilyRole


class BabyBornIn(BaseModel):
    """The Baby Born! action. `occurred_at` defaults to now; `body` is an
    optional note that rides along on the milestone (e.g. weight, time).
    """

    occurred_at: Optional[PastDatetime] = None
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


class FocalPointIn(BaseModel):
    """Which part of a photo to keep when the frame has to crop it.

    Fractions of the picture, so they survive any size the photo is shown
    at: (0, 0) is the top-left corner, (0.5, 0.5) the middle — which is
    where a browser crops on its own, and therefore what absence means.
    """

    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)


class EditEventIn(BaseModel):
    """Patch the editable parts of a timeline event.

    For text_note: `body`. For milestone: `title` / `body`. For photo /
    video / voice_memo: `caption`. Unknown keys are ignored; the
    repository merges the patch into the existing payload.

    `occurred_at` is the event's own column, not payload — posts are often
    logged after the fact mid-labor, so the time can be corrected on any
    event except contractions (their durations and gaps derive from it).

    `focal` is for photos: the timeline gives every one the same fixed
    height, so a tall photo is cropped from the middle, and on a newborn
    the middle is a torso.
    """

    body: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    transcript_optional: Optional[str] = None
    occurred_at: Optional[PastDatetime] = None
    focal: Optional[FocalPointIn] = None


# Keep in sync with frontend/src/utils/themes.js THEMES (current ids only,
# not the legacy read-side aliases).
ALLOWED_THEMES = frozenset({"lily", "blossom", "dino", "ocean", "golden", "starry"})


class BirthCreateIn(BaseModel):
    baby_name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    theme: str = Field(default="lily", max_length=50)
    # Optional at setup; also settable later in Birth settings. Shown on the
    # guess board and seeds the date field — it gates nothing.
    due_date: Optional[date] = None
    # Attach to an existing family (second child, twins, etc.) instead of
    # starting a new one. The caller must already be an owner/co-parent
    # there — enforced in the route, not here.
    family_id: Optional[uuid.UUID] = None


class BirthUpdateIn(BaseModel):
    theme: Optional[str] = Field(default=None, max_length=50)
    # Actual measurements, recorded by the parents once known — these settle
    # the guessing jar and unlock the pool gift artwork.
    child_weight_lbs: Optional[float] = Field(default=None, gt=0, lt=30)
    child_length_in: Optional[float] = Field(default=None, gt=0, lt=40)
    # Pool controls (Birth settings): expected arrival + the gender-surprise
    # toggle. child_sex rides along with the actuals at settle.
    due_date: Optional[date] = None
    gender_pool_enabled: Optional[bool] = None
    child_sex: Optional[Literal["boy", "girl"]] = None

    @field_validator("theme")
    @classmethod
    def _validate_theme(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ALLOWED_THEMES:
            raise ValueError("Unknown theme")
        return value


class SlugAvailableOut(BaseModel):
    available: bool
    suggestion: Optional[str] = None


class MockupExtraOut(BaseModel):
    """An extra angle/view mockup alongside the primary one (e.g. a mug's
    handle-from-left shot). `title` is partner-supplied and may be empty."""

    title: str
    url: str


class GiftRenderingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template_id: str
    status: GiftRenderingStatus
    artwork_url: Optional[str] = None
    mockup_url: Optional[str] = None
    mockup_status: str = "none"
    mockup_extras: list[MockupExtraOut] = []
    is_visible_to_viewers: bool
    # This design's own photo. `photo_media_id` is the override, `photo_auto`
    # says nobody has chosen yet (so what's shown is our guess), and
    # `photo_removable` is false where the photo *is* the design and taking it
    # off would leave an empty frame.
    has_photo: bool = False
    photo_media_id: Optional[uuid.UUID] = None
    photo_auto: bool = True
    # The photo the current artwork actually used, resolved. When a design is
    # on auto this is the guess *as it stood when it rendered* — which is not
    # the same as re-running the guess later, and the editor needs the former
    # so opening it can't move a photo nobody touched.
    photo_media_id_effective: Optional[uuid.UUID] = None
    photo_removed: bool = False
    photo_removable: bool = False
    # (cx, cy, r) as fractions of the artwork, so the editor can lay a
    # "change photo" hotspot over the photo itself.
    photo_spot: Optional[tuple[float, float, float]] = None
    # The filmstrip designs: how many photo panels, the explicit choices,
    # and what each panel actually showed at the last render — the editor
    # seeds its per-slot pickers from the latter, exactly as the single
    # photo seeds from photo_media_id_effective.
    photo_slot_count: int = 0
    photo_slots: dict[str, uuid.UUID] = {}
    photo_slots_effective: list[Optional[uuid.UUID]] = []
    # The book: its pages in order — key, kind, which photo slots each holds,
    # a URL for the page on screen and one for its strip thumbnail, once
    # there is one.
    pages: list[dict] = []
    layout_overrides: dict = {}
    photo_crop: dict[str, list[float]] = {}
    # the shape (width / height) of each photo slot's frame and of the hero's,
    # so the editor draws a crop rectangle of the right proportions
    slot_frame_aspects: list[float] = []
    hero_frame_aspect: float = 1.0
    # The story frame only: its photo roll at the last render — every day
    # photo, whether it made the line, and how many the line holds.
    story_roll: Optional[dict] = None
    # Slots this design lets a parent edit, and what they currently say.
    editable_text: list[str] = []
    text_overrides: dict[str, str] = {}
    # What each set line ended up at, and the size below which it stops
    # printing well — so the editor can warn without measuring fonts itself.
    text_sizes: dict[str, int] = {}
    text_print_floor: int = 0
    product_key: Optional[str] = None


class GiftDesignIn(BaseModel):
    """A draft of one design: its photo and any text the template allows.

    Photo: a media id to use it, `removed` to take it off, or neither to hand
    the choice back to the auto-pick. Text is keyed by slot, and keys the
    template doesn't list as editable are dropped at render — a keepsake's
    derived lines aren't up for editing.
    """

    media_id: Optional[uuid.UUID] = None
    removed: bool = False
    # For the filmstrip designs: slot index ("0".."3") → the chosen photo.
    # A missing slot stays on the auto sample; unknown slots are dropped.
    photo_slots: dict[str, uuid.UUID] = Field(default_factory=dict)
    # The book's middle section, as the parent arranged it — None keeps the
    # automatic plan. Each entry: {"kind": "gallery"|"notes"|"write_in",
    # "count": 1–4 for a gallery}.
    pages: Optional[list[dict]] = None
    # The two ruled pages at the back, by position: {"heading", "subheading"}
    # for either; None or an empty entry keeps the book's own words. A ruled
    # page in `pages` may carry the same two keys.
    pen_pages: Optional[list[dict]] = None
    # The part of each placed photo that shows, as fractions of the picture:
    # [x, y, width] of the region's top-left and width (its height follows the
    # frame's shape). "hero" for a design's single photo, the slot index for
    # the rest. Absent means the centre of the picture fills the frame.
    crop: dict[str, list[float]] = Field(default_factory=dict)
    # The story frame's photo roll: which of the day's photos the parent has
    # ticked off the line ("off") and which they've pinned on it ("on").
    # A photo sits at the moment it was taken, so there is nothing to place —
    # only whether it goes. Unmentioned photos are the thinning's to decide.
    story: Optional[dict[str, list[uuid.UUID]]] = None
    text: dict[str, str] = Field(default_factory=dict)
    product_key: Optional[str] = None


class BookPlanOut(BaseModel):
    pages: list[dict]


class StoryRollOut(BaseModel):
    """The story frame's photos in order, each on or off the line under the
    draft's ticks, and how many the line holds."""

    photos: list[dict]
    capacity: int


class GiftPhotoOptionOut(BaseModel):
    """A photo the parent could put on a keepsake."""

    # No URL: the client already builds one with `api.mediaUrl(id)`, the same
    # way the timeline renders its photos. One place that knows the shape.
    media_id: uuid.UUID
    occurred_at: Optional[datetime] = None
    caption: Optional[str] = None


class GiftItemOut(BaseModel):
    """A catalog item plus its generated renderings for a birth. Storage
    gifts (no artwork) come back with an empty `renderings` list."""

    id: uuid.UUID
    kind: GiftKind
    product_kind: str
    display_name: str
    base_price_cents: int
    storage_years_granted: Optional[int] = None
    is_purchasable: bool = False
    is_claimed_for_family: bool = False
    renderings: list[GiftRenderingOut] = []


class GiftGalleryOut(BaseModel):
    """The gift gallery plus birth-level purchase context (whether the
    parents saved a shipping address — the address itself never leaves the
    parent-only routes)."""

    items: list["GiftItemOut"] = []
    family_has_shipping_address: bool = False
    storage_paid_until: Optional[datetime] = None
    storage_lifetime: bool = False
    # When artwork may first be generated: the arrival plus a few hours for
    # the birth time and measurements to settle. None before the birth. In
    # the future, `items` is empty on purpose and the gallery says so rather
    # than rendering a story that's still being corrected.
    artwork_ready_at: Optional[datetime] = None


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
    # The blank product photo, so the chooser costs no mockups at all.
    blank_image_url: str = ""
    surcharge_cents: int = 0
    # what tells this one from its neighbours: "15 oz", "Oak", "Matte"
    caption: str = ""


class RenderingProductsOut(BaseModel):
    rendering_id: uuid.UUID
    products: list[ProductMockupOut] = []


class TrackIn(BaseModel):
    """One SPA page view. No IP, no cookie, no fingerprint — the length
    caps are the abuse posture (alongside nginx rate limiting), since this
    is a public unauthenticated insert."""

    path: str = Field(max_length=512)
    referrer: Optional[str] = Field(default=None, max_length=1024)
    ref: Optional[str] = Field(default=None, max_length=128)
    utm_source: Optional[str] = Field(default=None, max_length=128)
    utm_medium: Optional[str] = Field(default=None, max_length=128)
    utm_campaign: Optional[str] = Field(default=None, max_length=128)


class DailyCount(BaseModel):
    day: date
    count: int


class SourceCount(BaseModel):
    source: str
    count: int


class DailySourceCount(BaseModel):
    day: date
    source: str
    count: int


class SignupStatsOut(BaseModel):
    total: int
    by_day: list[DailyCount]
    by_source: list[SourceCount]


class VisitStatsOut(BaseModel):
    total: int
    by_day_by_source: list[DailySourceCount]
    by_source: list[SourceCount]


class ActivationStatsOut(BaseModel):
    """Signups in range who did the thing the product exists for."""

    activated: int
    signups: int
    rate: Optional[float] = None  # None when signups == 0


class InviteStatsOut(BaseModel):
    created: int
    # Authenticated redemptions incl. the same person re-following a link —
    # NOT anonymous clicks; those are `link_visits` (page_visits /invite/%).
    redemptions: int
    distinct_redeemers: int
    link_visits: int


class ConversionStatsOut(BaseModel):
    """The viral loop, all-time: share-link arrivals who later became
    owners of their own birth story."""

    became_owners: int
    all_redeemers: int
    rate: Optional[float] = None


class ActiveUsersOut(BaseModel):
    dau: int
    wau: int


class RevenueStatsOut(BaseModel):
    gift_count: int
    gift_cents: int
    total_cents: int
    # the economics behind the gross: item vs postage charged, what the
    # partner billed (for the orders whose costs are in), what Stripe kept,
    # and what was left. Zero-defaults keep older callers valid.
    product_cents: int = 0
    shipping_cents: int = 0
    fee_cents: int = 0
    cost_cents: int = 0
    costed_count: int = 0
    margin_cents: int = 0


class AdminOverviewOut(BaseModel):
    start_date: date
    end_date: date  # inclusive, matches the query param
    signups: SignupStatsOut
    visits: VisitStatsOut
    activation: ActivationStatsOut
    invites: InviteStatsOut
    conversion: ConversionStatsOut
    active_users: ActiveUsersOut
    revenue: RevenueStatsOut


class WorkerStatusOut(BaseModel):
    seen_at: Optional[datetime] = None
    ok: bool


class HealthOut(BaseModel):
    status: str  # "ok" | "degraded"
    db: str  # "ok" | "error"
    revision: Optional[str] = None
    worker: WorkerStatusOut


class AppLogOut(BaseModel):
    id: uuid.UUID
    logged_at: datetime
    service: str
    level: str
    logger: str
    message: str
    fingerprint: str
    request_id: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    exception: Optional[str] = None
    extra: Optional[dict] = None


class AdminLogsOut(BaseModel):
    since: datetime
    items: list[AppLogOut]
    level_counts: dict[str, int]
    service_counts: dict[str, int]
    worker: WorkerStatusOut


# Convenience for tests / fixtures that need to validate an EmailStr-shaped
# value without importing pydantic.EmailStr at call sites.
EmailString = EmailStr

MeOut.model_rebuild()
FamilyWithBirthsOut.model_rebuild()
