"""The gift gallery: catalog, per-birth renderings, product shortlists,
and mockups. Purchasing lives in routes/checkout.py."""
from __future__ import annotations

import json
import math
import uuid

from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

import artwork_links
import fulfillment
import gift_artwork
import gift_templates
from auth import get_current_user
from db import get_db
from fulfillment import products as fulfillment_products
from models import (
    BirthStatus,
    GiftKind,
    GiftRendering,
    GiftRenderingStatus,
    MediaAsset,
    MediaKind,
    TimelineEvent,
    TimelineEventType,
    User,
)
from repositories import births as births_repo
from repositories import gift_orders as gift_orders_repo
from repositories import gifts as gifts_repo
from repositories import media as media_repo
from routes.deps import BirthAccess, require_birth_access, require_parent_access
from schemas import (
    BookPlanOut,
    StoryRollOut,
    GiftPhotoOptionOut,
    GiftDesignIn,
    GiftGalleryOut,
    GiftItemOut,
    GiftRenderingOut,
    GiftRenderingPatchIn,
    ProductMockupOut,
    RenderingProductsOut,
)
from storage import get_object_bytes, put_object

router = APIRouter()


def _serialize_rendering(rendering) -> GiftRenderingOut:
    template = gift_templates.get(rendering.template_id)
    shows_photo = bool(template and template.photo)
    return GiftRenderingOut(
        id=rendering.id,
        template_id=rendering.template_id,
        status=rendering.status,
        artwork_url=gifts_repo.artwork_url(rendering),
        mockup_url=gifts_repo.mockup_url(rendering),
        mockup_status=rendering.mockup_status,
        mockup_extras=gifts_repo.mockup_extras(rendering),
        is_visible_to_viewers=rendering.is_visible_to_viewers,
        has_photo=shows_photo,
        photo_media_id=rendering.photo_media_id,
        photo_media_id_effective=gift_artwork.effective_photo_id(rendering),
        photo_auto=(
            rendering.photo_media_id is None and not rendering.photo_removed
        ),
        photo_removed=rendering.photo_removed,
        # `card_welcome` is a full-bleed hero in a keyline mat — removing its
        # photo leaves an empty frame, so it doesn't get the option.
        photo_removable=shows_photo and not (template and template.photo_required),
        photo_spot=template.photo_spot if template else None,
        # how many slot pickers to show: what the last render actually placed
        # when it recorded that (the story fits as many photos as its line
        # holds), else the template's count
        pages=gifts_repo.book_pages(rendering),
        layout_overrides=rendering.layout_overrides or {},
        photo_crop=(rendering.layout_overrides or {}).get("crop") or {},
        slot_frame_aspects=(rendering.rendering_metadata or {}).get("slot_frame_aspects") or [],
        story_roll=(rendering.rendering_metadata or {}).get("story_roll"),
        photo_slot_count=(
            len((rendering.rendering_metadata or {}).get("selected_slot_media_ids") or [])
            or (template.photo_slots if template else 0)
        ) if template and template.photo_slots else 0,
        photo_slots=rendering.photo_slots or {},
        photo_slots_effective=(
            (rendering.rendering_metadata or {}).get("selected_slot_media_ids") or []
        ),
        editable_text=list(template.editable_text) if template else [],
        text_overrides=dict(rendering.text_overrides or {}),
        product_key=rendering.product_key,
        text_sizes=(rendering.rendering_metadata or {}).get("text_sizes") or {},
        text_print_floor=(rendering.rendering_metadata or {}).get(
            "text_print_floor"
        ) or 0,
    )


def _serialize_gift_items(db, birth_id, *, is_parent: bool) -> list[GiftItemOut]:
    items = gifts_repo.list_active_catalog(db)
    renderings = gifts_repo.list_renderings_for_birth(db, birth_id=birth_id)
    claimed = gift_orders_repo.claimed_item_ids(db, birth_id=birth_id)
    by_item: dict = {}
    for r in renderings:
        if not is_parent and not r.is_visible_to_viewers:
            continue
        by_item.setdefault(r.gift_catalog_item_id, []).append(r)
    return [
        GiftItemOut(
            id=item.id,
            kind=item.kind,
            product_kind=item.product_kind,
            display_name=item.display_name,
            base_price_cents=item.base_price_cents,
            storage_years_granted=item.storage_years_granted,
            # physical: purchasable once a fulfillment product is mapped
            # (cards stay "coming soon" until a registry entry exists).
            # storage gifts: always purchasable, no fulfillment involved.
            is_purchasable=(
                item.kind == GiftKind.storage_gift
                or (
                    item.kind == GiftKind.physical
                    and fulfillment_products.default_for_product_kind(item.product_kind)
                    is not None
                )
            ),
            is_claimed_for_family=item.id in claimed,
            renderings=[_serialize_rendering(r) for r in by_item.get(item.id, [])],
        )
        for item in items
    ]


def _gift_gallery_out(db, birth, *, is_parent: bool) -> GiftGalleryOut:
    return GiftGalleryOut(
        items=_serialize_gift_items(db, birth.id, is_parent=is_parent),
        family_has_shipping_address=birth.shipping_address is not None,
        storage_paid_until=birth.storage_paid_until,
        storage_lifetime=birth.storage_lifetime,
        artwork_ready_at=gifts_repo.artwork_ready_at(birth),
    )


@router.get("/gift-artwork/{rendering_id}.png")
def gift_artwork_file(
    rendering_id: uuid.UUID,
    exp: int,
    sig: str,
    db: Session = Depends(get_db),
) -> Response:
    """Gift artwork for fulfillment partners (Printful fetches mockup and
    print files by URL). Unauthenticated on purpose — the caller is a
    partner server, not a user; a valid unexpired HMAC signature is the
    credential, exactly like a presigned S3 URL but short enough for
    Printful's 1000-character URL cap."""
    if not artwork_links.verify_artwork_sig(rendering_id, exp, sig):
        raise HTTPException(status_code=403, detail="Invalid or expired link")
    rendering = db.get(GiftRendering, rendering_id)
    if (
        rendering is None
        or rendering.deleted_at is not None
        or not rendering.artwork_s3_key
    ):
        raise HTTPException(status_code=404, detail="Unknown artwork")
    body = get_object_bytes(rendering.artwork_s3_key)
    return Response(content=body, media_type="image/png")


@router.get("/gift-artwork/{rendering_id}/{page}.png")
def gift_artwork_page_file(
    rendering_id: uuid.UUID,
    page: str,
    exp: int,
    sig: str,
    db: Session = Depends(get_db),
) -> Response:
    """One file of a many-file design — the book's cover wrap or a page —
    for the partner. Same credential as the single-file route."""
    if not artwork_links.verify_artwork_sig(rendering_id, exp, sig, page):
        raise HTTPException(status_code=403, detail="Invalid or expired link")
    rendering = db.get(GiftRendering, rendering_id)
    key = ((rendering.rendering_metadata or {}).get("pages") or {}).get(page) if rendering else None
    if rendering is None or rendering.deleted_at is not None or not key:
        raise HTTPException(status_code=404, detail="Unknown artwork")
    return Response(content=get_object_bytes(key), media_type="image/png")


@router.get("/gifts/catalog", response_model=list[GiftItemOut])
def gift_catalog(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GiftItemOut]:
    return [
        GiftItemOut(
            id=item.id,
            kind=item.kind,
            product_kind=item.product_kind,
            display_name=item.display_name,
            base_price_cents=item.base_price_cents,
            storage_years_granted=item.storage_years_granted,
            renderings=[],
        )
        for item in gifts_repo.list_active_catalog(db)
    ]


@router.get("/birth/{birth_id}/gifts", response_model=GiftGalleryOut)
def list_gifts(
    background_tasks: BackgroundTasks,
    access: BirthAccess = Depends(require_birth_access),
    db: Session = Depends(get_db),
) -> GiftGalleryOut:
    """The gift gallery. Lazily ensures a rendering exists per (physical item
    × template) and schedules a background render for anything pending — but
    only once the story has had time to settle: gifts are made FROM the story
    (Day Two is the moment), and a pre-birth page has no story to render.
    Merely browsing the page must never generate artwork from an empty
    timeline.

    This is also the only thing that turns a stale row back into artwork, so a
    correction made to the birth time or the measurements reaches the keepsake
    the next time anyone opens the gallery — and the only thing that retries a
    product mockup the fulfillment partner refused (rate limits mean a
    re-render of the whole gallery routinely loses one), so a design doesn't
    stay stuck showing its flat artwork.
    """
    if gifts_repo.artwork_window_open(access.birth):
        gifts_repo.ensure_renderings(db, birth=access.birth)
        pending = gifts_repo.ids_needing_render(db, birth_id=access.birth.id)
        for rendering_id in gifts_repo.claim_renders(pending):
            background_tasks.add_task(gifts_repo.render_rendering, rendering_id)
    retryable = gifts_repo.ids_needing_mockup_retry(db, birth_id=access.birth.id)
    for rendering_id in gifts_repo.claim_renders(retryable):
        background_tasks.add_task(gifts_repo.retry_mockup, rendering_id)
    return _gift_gallery_out(
        db, access.birth, is_parent=births_repo.is_parent(access.role)
    )


@router.post("/birth/{birth_id}/gifts/generate", response_model=GiftGalleryOut)
def generate_gifts(
    background_tasks: BackgroundTasks,
    rendering_id: uuid.UUID | None = None,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> GiftGalleryOut:
    """Force a (re)render — all of the birth's gift artwork, or a single
    rendering when `rendering_id` is given. Parents only.

    Deliberately not gated on the grace period: this is the escape hatch for a
    parent who wants their keepsake now, and asking for it is consent to
    whatever the story currently says.
    """
    gifts_repo.ensure_renderings(db, birth=access.birth)
    ids = gifts_repo.reset_to_pending(
        db, birth_id=access.birth.id, rendering_id=rendering_id
    )
    for rid in gifts_repo.claim_renders(ids):
        background_tasks.add_task(gifts_repo.render_rendering, rid)
    return _gift_gallery_out(db, access.birth, is_parent=True)


def load_rendering_for_products(db, access, rendering_id):
    """Fetch a rendering, applying the same visibility rule as the rest of
    the gift routes (viewers only see visible renderings)."""
    rendering = gifts_repo.get_rendering(
        db, birth_id=access.birth.id, rendering_id=rendering_id
    )
    is_parent = births_repo.is_parent(access.role)
    if rendering is None or (not is_parent and not rendering.is_visible_to_viewers):
        raise HTTPException(status_code=404, detail="Rendering not found")
    return rendering


@router.get(
    "/birth/{birth_id}/gifts/photos", response_model=list[GiftPhotoOptionOut]
)
def list_gift_photos(
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> list[GiftPhotoOptionOut]:
    """Photos this birth could put on a keepsake — everything on the timeline
    plus anything uploaded for the artwork alone. Parents only; this is a
    picker for the people who own the story.

    Captions come from the timeline event that carried the photo, so the grid
    can be read at a glance. Keepsake-only uploads have no event and no
    caption, which is the point of them.
    """
    assets = list(
        db.scalars(
            select(MediaAsset)
            .where(
                MediaAsset.birth_id == access.birth.id,
                MediaAsset.kind == MediaKind.photo,
                MediaAsset.archived_at.is_(None),
            )
            .order_by(MediaAsset.created_at.asc())
        ).all()
    )
    events = list(
        db.scalars(
            select(TimelineEvent).where(
                TimelineEvent.birth_id == access.birth.id,
                TimelineEvent.event_type == TimelineEventType.photo,
                TimelineEvent.deleted_at.is_(None),
            )
        ).all()
    )
    by_media = {
        (e.payload or {}).get("media_id"): e for e in events
    }
    out = []
    for asset in assets:
        event = by_media.get(str(asset.id))
        out.append(
            GiftPhotoOptionOut(
                media_id=asset.id,
                occurred_at=event.occurred_at if event else asset.created_at,
                caption=(event.payload or {}).get("caption") if event else None,
            )
        )
    return out


@router.post(
    "/birth/{birth_id}/gifts/photos", response_model=GiftPhotoOptionOut
)
async def upload_gift_photo(
    file: UploadFile = File(...),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftPhotoOptionOut:
    """Add a photo for the keepsakes without posting it to the story.

    Deliberately not `POST /birth/{id}/media`, which always appends a timeline
    event: choosing a nicer picture for a mug isn't an announcement, and it
    shouldn't push a notification to everyone the family invited.
    """
    extension = Path(file.filename or "").suffix or ".jpg"
    content = await file.read()
    key = media_repo.media_object_key(
        family_id=access.birth.family_id,
        birth_id=access.birth.id,
        filename=f"{uuid.uuid4()}{extension}",
    )
    put_object(key=key, body=content, content_type=file.content_type)
    asset = media_repo.create_media_asset(
        db,
        family_id=access.birth.family_id,
        birth_id=access.birth.id,
        uploaded_by_user_id=current_user.id,
        kind=MediaKind.photo,
        original_s3_key=key,
        mime_type=file.content_type,
        bytes_=len(content),
    )
    db.commit()
    return GiftPhotoOptionOut(
        media_id=asset.id,
        occurred_at=asset.created_at,
        caption=None,
    )


@router.get(
    "/birth/{birth_id}/gifts/{rendering_id}", response_model=GiftRenderingOut
)
def get_gift_rendering(
    rendering_id: uuid.UUID,
    access: BirthAccess = Depends(require_birth_access),
    db: Session = Depends(get_db),
) -> GiftRenderingOut:
    rendering = load_rendering_for_products(db, access, rendering_id)
    return _serialize_rendering(rendering)


@router.patch(
    "/birth/{birth_id}/gifts/{rendering_id}", response_model=GiftRenderingOut
)
def patch_gift_rendering(
    rendering_id: uuid.UUID,
    payload: GiftRenderingPatchIn,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> GiftRenderingOut:
    rendering = gifts_repo.get_rendering(
        db, birth_id=access.birth.id, rendering_id=rendering_id
    )
    if rendering is None:
        raise HTTPException(status_code=404, detail="Rendering not found")
    rendering.is_visible_to_viewers = payload.is_visible_to_viewers
    db.commit()
    db.refresh(rendering)
    return _serialize_rendering(rendering)


class _Draft:
    """An unsaved design, shaped like a GiftRendering for the renderer's
    benefit. Previews never touch the database or S3, so a parent can try
    five photos and three names and walk away having changed nothing."""

    def __init__(self, rendering, payload: GiftDesignIn):
        self.photo_media_id = None if payload.removed else payload.media_id
        self.photo_removed = payload.removed
        self.photo_slots = {k: str(v) for k, v in (payload.photo_slots or {}).items()}
        self.layout_overrides = _layout_overrides(payload)
        self.text_overrides = dict(payload.text or {})
        self.template_id = rendering.template_id
        self.product_key = payload.product_key


def _page_spec(pg: dict) -> dict:
    spec = {"kind": str(pg.get("kind") or "")}
    if pg.get("count") is not None:
        spec["count"] = int(pg["count"])
    photos = pg.get("photos")
    if isinstance(photos, list) and any(photos):
        spec["photos"] = [str(m) if m else None for m in photos[:4]]
    if pg.get("spare") is not None and pg.get("spare") is not False:
        spec["spare"] = int(pg["spare"]) if not isinstance(pg["spare"], bool) else 0
    for k, cap in (("heading", gift_artwork.WRITE_IN_HEADING_MAX), ("subheading", gift_artwork.WRITE_IN_SUB_MAX)):
        v = str(pg.get(k) or "").strip()[:cap]
        if v:
            spec[k] = v
    return spec


def _layout_overrides(payload: GiftDesignIn) -> dict:
    """The parent's arrangement, as stored: the book's pages when given, and
    the crop of any placed photo they've moved or zoomed."""
    out: dict = {}
    if payload.pages is not None:
        # only what a page can be, plus a ruled page's own words
        out["pages"] = [_page_spec(pg) for pg in payload.pages if isinstance(pg, dict)]
    if payload.pen_pages is not None:
        out["pen_pages"] = [_page_spec(pg) for pg in payload.pen_pages[:2] if isinstance(pg, dict)]
    crop = {
        str(k): [float(v[0]), float(v[1]), float(v[2])]
        for k, v in (payload.crop or {}).items()
        if isinstance(v, (list, tuple)) and len(v) == 3
    }
    if crop:
        out["crop"] = crop
    if payload.story is not None:
        out["story"] = {
            side: [str(m) for m in (payload.story.get(side) or [])]
            for side in ("off", "on")
        }
    return out


def _apply_draft(rendering, payload: GiftDesignIn) -> None:
    rendering.photo_media_id = None if payload.removed else payload.media_id
    rendering.photo_removed = payload.removed
    # Stringified for JSONB; unknown slot keys fall away at render, the same
    # posture as text overrides.
    rendering.photo_slots = {
        k: str(v) for k, v in (payload.photo_slots or {}).items()
    }
    rendering.layout_overrides = _layout_overrides(payload)
    rendering.text_overrides = dict(payload.text or {})
    # Unknown keys are ignored rather than rejected: the shortlist is a code
    # registry, and a design pointing at a product we've since retired should
    # fall back to the default, not fail to save.
    rendering.product_key = (
        payload.product_key
        if payload.product_key in fulfillment_products.SHORTLIST
        else None
    )


def _load_editable(db, access, rendering_id):
    """A rendering plus its template, checked for editability."""
    rendering = gifts_repo.get_rendering(
        db, birth_id=access.birth.id, rendering_id=rendering_id
    )
    if rendering is None:
        raise HTTPException(status_code=404, detail="Rendering not found")
    template = gift_templates.get(rendering.template_id)
    if template is None:
        raise HTTPException(status_code=400, detail="Unknown design")
    return rendering, template


def _check_photo(db, access, payload: GiftDesignIn, template) -> None:
    if payload.removed and template.photo_required:
        raise HTTPException(
            status_code=400, detail="This design can't be rendered without a photo"
        )
    for media_id in [payload.media_id, *(payload.photo_slots or {}).values()]:
        if media_id is None:
            continue
        asset = db.get(MediaAsset, media_id)
        if (
            asset is None
            or asset.birth_id != access.birth.id
            or asset.archived_at is not None
        ):
            raise HTTPException(status_code=404, detail="Photo not found")


# Wide enough to read, small enough to be instant: a preview costs ~107ms and
# 13KB against ~500ms and 304KB for the print-resolution render. Most of that
# saving is the photo, not the raster — hence the max_px.
_PREVIEW_W = 900
_PREVIEW_PHOTO_PX = 500


@router.post("/birth/{birth_id}/gifts/{rendering_id}/preview")
def preview_gift_design(
    rendering_id: uuid.UUID,
    payload: GiftDesignIn,
    full: bool = False,
    page: str | None = None,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> Response:
    """Render a draft and hand back the PNG. Nothing is saved.

    This is what makes the editor feel live: the client debounces keystrokes
    onto it and swaps the image. No partner call, no storage write, no row
    touched — so trying things costs nothing and abandoning them costs
    nothing either.

    `full` renders at print resolution instead. Keystrokes don't need it, but
    someone opening their unsaved design full screen to look closely does —
    handing them the 900px draft would be answering the wrong question. One
    request on an explicit action, rather than a bigger render on every one.
    """
    rendering, template = _load_editable(db, access, rendering_id)
    _check_photo(db, access, payload, template)
    try:
        if template.scene == "book":
            # one page at a time: the editor is looking at one
            files, _meta = gift_artwork.render_book(
                access.birth,
                template,
                db,
                _Draft(rendering, payload),
                only=page or "cover_front",
                photo_max_px=None if full else _PREVIEW_PHOTO_PX,
                output_width=None if full else _PREVIEW_W,
            )
            if not files:
                raise HTTPException(status_code=404, detail="No such page")
            png = next(iter(files.values()))
        else:
            png, _meta = gift_artwork.render(
                access.birth,
                template,
                db,
                _Draft(rendering, payload),
                photo_max_px=None if full else _PREVIEW_PHOTO_PX,
                output_width=None if full else _PREVIEW_W,
            )
    except gift_artwork.ArtworkError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            # The body is a PNG, so the fitted sizes ride along in a header:
            # the editor needs them to warn about type that's shrunk too far,
            # and only the server can measure them.
            "X-Text-Fit": json.dumps(
                {
                    "sizes": _meta.get("text_sizes", {}),
                    "floor": _meta.get("text_print_floor", 0),
                }
            ),
        },
    )


@router.post(
    "/birth/{birth_id}/gifts/{rendering_id}/book-plan", response_model=BookPlanOut
)
def book_plan_preview(
    rendering_id: uuid.UUID,
    payload: GiftDesignIn,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> BookPlanOut:
    """The book's page plan for a draft — nothing drawn, nothing saved. The
    editor asks after a page is added, removed or moved, to learn which pages
    now exist and which photo slots each holds."""
    rendering, template = _load_editable(db, access, rendering_id)
    if template.scene != "book":
        raise HTTPException(status_code=400, detail="Not a book")
    return BookPlanOut(pages=gift_artwork.book_plan_for(db, access.birth, rendering, payload.pages))


@router.post(
    "/birth/{birth_id}/gifts/{rendering_id}/story-roll", response_model=StoryRollOut
)
def story_roll_preview(
    rendering_id: uuid.UUID,
    payload: GiftDesignIn,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> StoryRollOut:
    """The story frame's photo roll for a draft — nothing drawn, nothing
    saved. The editor asks after a tick, to learn which photos now make the
    line: untick one and the room it frees brings back the next."""
    rendering, template = _load_editable(db, access, rendering_id)
    layout = gift_artwork._layout_of(template)
    if layout.scene != "frame_story":
        raise HTTPException(status_code=400, detail="Not the story frame")
    edges = gift_artwork._story_edges(layout.width, layout.height)
    straight = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b, _ in edges)
    roll = gift_artwork.story_roll(db, access.birth, _Draft(rendering, payload), straight)
    return StoryRollOut(**roll)


@router.patch(
    "/birth/{birth_id}/gifts/{rendering_id}/design", response_model=GiftRenderingOut
)
def save_gift_design(
    rendering_id: uuid.UUID,
    payload: GiftDesignIn,
    background_tasks: BackgroundTasks,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> GiftRenderingOut:
    """Commit the draft and re-render at print resolution.

    Rendered inline rather than queued: half a second doesn't need a
    background task, a pending status and a poll. No partner call happens
    here — the product mockup is asked for separately, and only when someone
    wants to see one.
    """
    rendering, template = _load_editable(db, access, rendering_id)
    _check_photo(db, access, payload, template)
    _apply_draft(rendering, payload)
    db.commit()

    if template.scene == "book":
        # twenty-six files, not one — too long to hold the request open.
        # The editor sees `pending` and waits for `ready`.
        gifts_repo.reset_to_pending(db, birth_id=access.birth.id, rendering_id=rendering.id)
        background_tasks.add_task(gifts_repo.render_rendering, rendering.id)
    else:
        gifts_repo.render_rendering(rendering.id)
    db.expire_all()
    rendering = gifts_repo.get_rendering(
        db, birth_id=access.birth.id, rendering_id=rendering_id
    )
    return _serialize_rendering(rendering)


@router.post(
    "/birth/{birth_id}/gifts/{rendering_id}/mockup", response_model=GiftRenderingOut
)
def refresh_gift_mockup(
    rendering_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> GiftRenderingOut:
    """Ask the fulfillment partner to photograph this design on the product.

    Deliberately explicit. The partner allows 2 mockups a minute for the whole
    store, so they're generated once per design automatically — that's what
    fills the gallery — and after that only when someone asks, for the design
    they actually settled on. Returns immediately with `mockup_status`
    pending; the client polls.
    """
    rendering = gifts_repo.get_rendering(
        db, birth_id=access.birth.id, rendering_id=rendering_id
    )
    if rendering is None:
        raise HTTPException(status_code=404, detail="Rendering not found")
    if rendering.status is not GiftRenderingStatus.ready:
        raise HTTPException(status_code=409, detail="The design isn't ready yet")
    if rendering.mockup_status != "pending":
        background_tasks.add_task(gifts_repo.refresh_mockup, rendering.id)
    return _serialize_rendering(rendering)


def _serialize_rendering_products(db, rendering) -> RenderingProductsOut:
    product_kind = gifts_repo.product_kind_for_rendering(db, rendering)
    products = (
        fulfillment_products.for_product_kind(product_kind) if product_kind else []
    )
    cached = gifts_repo.list_product_mockups(db, rendering_id=rendering.id)
    return RenderingProductsOut(
        rendering_id=rendering.id,
        products=[
            _serialize_product_mockup(product, cached.get(product.key))
            for product in products
        ],
    )


def _serialize_product_mockup(product, mockup) -> ProductMockupOut:
    return ProductMockupOut(
        product_key=product.key,
        display_name=product.display_name,
        status=mockup.status if mockup is not None else "none",
        mockup_url=(
            gifts_repo.product_mockup_url(mockup) if mockup is not None else None
        ),
        blank_image_url=product.blank_image_url,
        surcharge_cents=product.surcharge_cents,
        caption=product.caption,
    )


@router.get(
    "/birth/{birth_id}/gifts/{rendering_id}/products",
    response_model=RenderingProductsOut,
)
def list_rendering_products(
    rendering_id: uuid.UUID,
    access: BirthAccess = Depends(require_birth_access),
    db: Session = Depends(get_db),
) -> RenderingProductsOut:
    """The shortlist of products this design can be shown on, plus any cached
    mockup per product."""
    rendering = load_rendering_for_products(db, access, rendering_id)
    return _serialize_rendering_products(db, rendering)


@router.post(
    "/birth/{birth_id}/gifts/{rendering_id}/products/{product_key}/mockup",
    response_model=ProductMockupOut,
)
def request_rendering_product_mockup(
    rendering_id: uuid.UUID,
    product_key: str,
    background_tasks: BackgroundTasks,
    access: BirthAccess = Depends(require_birth_access),
    db: Session = Depends(get_db),
) -> ProductMockupOut:
    """Request (get-or-create) a product mockup for a design on a shortlist
    product. Schedules a background render only for a new or previously-failed
    row; a cached row is returned as-is. The client polls the list endpoint
    for status."""
    rendering = load_rendering_for_products(db, access, rendering_id)
    product = fulfillment_products.get(product_key)
    product_kind = gifts_repo.product_kind_for_rendering(db, rendering)
    if product is None or product.product_kind != product_kind:
        raise HTTPException(status_code=404, detail="Unknown product for this design")
    if rendering.status != GiftRenderingStatus.ready:
        raise HTTPException(status_code=409, detail="Design is not ready yet")
    if fulfillment.get_adapter() is None:
        # No partner configured (dev without PRINTFUL_API_KEY): say so instead
        # of writing a doomed row that renders as a puzzling failed tile.
        raise HTTPException(
            status_code=503, detail="Product previews aren't configured"
        )

    mockup, should_render = gifts_repo.get_or_create_product_mockup(
        db, rendering=rendering, product_key=product_key
    )
    if should_render:
        background_tasks.add_task(gifts_repo.render_product_mockup, mockup.id)
    return _serialize_product_mockup(product, mockup)
