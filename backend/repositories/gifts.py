"""Gift catalog + rendering persistence and the render job.

Renderings are created lazily: opening a birth's gift gallery ensures a
`pending` row exists per (active physical catalog item × its templates), and
the route schedules a background render for any row that needs one. Storage
gifts have no artwork and never get a rendering row.

Two rules keep the artwork honest about a story that is still settling:

* Nothing renders until `ARTWORK_GRACE_PERIOD` after the arrival. The birth
  time is posted once someone has a free hand, so it is nearly always
  corrected afterwards — and the measurements usually arrive later still.
  Rendering at the Baby Born tap meant the keepsake captured the provisional
  version of both.
* Anything that changes what the artwork draws marks the rows stale
  (`mark_stale`), and the next gallery view re-renders them. Deferring the
  work to the view rather than the edit collapses a flurry of Day-One posts
  into one render.
"""
from __future__ import annotations

import io
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import fulfillment
import gift_artwork
import gift_templates
from db import SessionLocal
from fulfillment import products as fulfillment_products
from models import (
    Birth,
    BirthStatus,
    GiftCatalogItem,
    GiftKind,
    GiftRendering,
    GiftRenderingMockup,
    GiftRenderingStatus,
)
from artwork_links import signed_artwork_url
from storage import object_key, presigned_get_url, put_object

logger = logging.getLogger(__name__)

# How long the story is allowed to settle before any artwork is generated.
# Long enough to cover the usual "posted at 10:54, actually arrived 10:38"
# correction and the measurements being written up; short enough that a
# family looking for a keepsake on day one still finds one waiting.
ARTWORK_GRACE_PERIOD = timedelta(hours=4)


def artwork_ready_at(birth: Birth) -> datetime | None:
    """When this birth's artwork may first be generated, or None if it never
    can yet (still expecting, or born without a recorded arrival time)."""
    if birth.status is not BirthStatus.born or birth.birth_completed_at is None:
        return None
    return birth.birth_completed_at + ARTWORK_GRACE_PERIOD


def artwork_window_open(birth: Birth) -> bool:
    ready_at = artwork_ready_at(birth)
    return ready_at is not None and datetime.now(timezone.utc) >= ready_at


# Renders are claimed in-process before being scheduled, so a gallery poll
# arriving mid-render doesn't start a second one for the same row. A single
# uvicorn worker is a deliberate constraint of this app (see the SSE broker in
# events.py), which is what makes a process-local set sufficient. Background
# tasks run in a threadpool, hence the lock. Losing the set on restart is the
# right failure: whatever was mid-flight is gone too, and the row is still
# `pending` for the next view to pick up.
_in_flight: set[uuid.UUID] = set()
_in_flight_lock = threading.Lock()


def claim_renders(rendering_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Take ownership of the ids that aren't already rendering."""
    with _in_flight_lock:
        claimed = [rid for rid in rendering_ids if rid not in _in_flight]
        _in_flight.update(claimed)
    return claimed


def _release_render(rendering_id: uuid.UUID) -> None:
    with _in_flight_lock:
        _in_flight.discard(rendering_id)


# A hero mockup that the partner refused (a rate limit, usually) is retried
# the next time anyone opens the gallery. The gallery polls every few seconds
# while a render is in flight, so the retries are spaced by a cooldown that
# widens with each failure — otherwise one permanently-broken design would
# knock on the partner's door forever. Process-local for the same reason
# `_in_flight` is: one uvicorn worker, and losing it on restart just means the
# next view gets a fresh attempt.
_MOCKUP_RETRY_BACKOFF = timedelta(minutes=5)
_MOCKUP_RETRY_BACKOFF_MAX = timedelta(hours=1)
_mockup_retries: dict[uuid.UUID, tuple[int, float]] = {}  # id -> (failures, not_before)


def _mockup_retry_due(rendering_id: uuid.UUID) -> bool:
    """True when this rendering's hero mockup may be attempted again. A row
    we've never retried is due immediately — the failure has already happened
    and the family is looking at the flat artwork right now."""
    with _in_flight_lock:
        entry = _mockup_retries.get(rendering_id)
    return entry is None or time.monotonic() >= entry[1]


def _record_mockup_retry(rendering_id: uuid.UUID, *, succeeded: bool) -> None:
    with _in_flight_lock:
        if succeeded:
            _mockup_retries.pop(rendering_id, None)
            return
        failures = _mockup_retries.get(rendering_id, (0, 0.0))[0] + 1
        backoff = min(
            _MOCKUP_RETRY_BACKOFF * (2 ** (failures - 1)), _MOCKUP_RETRY_BACKOFF_MAX
        )
        _mockup_retries[rendering_id] = (
            failures,
            time.monotonic() + backoff.total_seconds(),
        )


def list_active_catalog(db: Session) -> list[GiftCatalogItem]:
    return list(
        db.scalars(
            select(GiftCatalogItem)
            .where(GiftCatalogItem.is_active.is_(True))
            .order_by(GiftCatalogItem.sort_order.asc(), GiftCatalogItem.created_at.asc())
        ).all()
    )


def list_renderings_for_birth(
    db: Session, *, birth_id: uuid.UUID
) -> list[GiftRendering]:
    return list(
        db.scalars(
            select(GiftRendering)
            .where(
                GiftRendering.birth_id == birth_id,
                GiftRendering.deleted_at.is_(None),
            )
            .order_by(GiftRendering.created_at.asc())
        ).all()
    )


def get_rendering(
    db: Session, *, birth_id: uuid.UUID, rendering_id: uuid.UUID
) -> GiftRendering | None:
    rendering = db.get(GiftRendering, rendering_id)
    if (
        rendering is None
        or rendering.birth_id != birth_id
        or rendering.deleted_at is not None
    ):
        return None
    return rendering


def _template_ids_for(item: GiftCatalogItem) -> list[str]:
    """The template ids valid for a catalog item. Driven by the code
    registry keyed on product_kind, so adding a design is a code change (a
    new registry entry) — no migration. Non-physical items (storage gifts)
    have none."""
    if item.kind != GiftKind.physical:
        return []
    return [t.template_id for t in gift_templates.for_product(item.product_kind)]


def ensure_renderings(
    db: Session, *, birth: Birth
) -> tuple[list[GiftRendering], list[uuid.UUID]]:
    """Make sure a rendering row exists for every (active physical item ×
    template). Returns (all rows for the birth, ids of newly-created rows).
    Only the new ids should be scheduled for rendering — existing rows are
    already done or in flight, so polling this won't restart them.
    """
    items = list_active_catalog(db)
    existing = list_renderings_for_birth(db, birth_id=birth.id)
    seen = {(r.gift_catalog_item_id, r.template_id) for r in existing}

    new_ids: list[uuid.UUID] = []
    for item in items:
        for template_id in _template_ids_for(item):
            if (item.id, template_id) in seen:
                continue
            row = GiftRendering(
                birth_id=birth.id,
                gift_catalog_item_id=item.id,
                template_id=template_id,
                status=GiftRenderingStatus.pending,
            )
            db.add(row)
            try:
                db.flush()
            except IntegrityError:
                # A concurrent request created it first — fall back to it.
                db.rollback()
                continue
            new_ids.append(row.id)

    db.commit()
    return list_renderings_for_birth(db, birth_id=birth.id), new_ids


def mark_stale(db: Session, *, birth_id: uuid.UUID) -> int:
    """Flag this birth's artwork as needing a re-render because something it
    draws from changed. Flips finished rows back to `pending` and leaves the
    old `artwork_s3_key` in place, so the gallery keeps showing the previous
    design (and a purchased order keeps a valid print file) until the new one
    lands. Does NOT commit — it composes into the caller's transaction, and
    must not half-commit an edit that later fails.

    Returns the number of rows marked, so callers can skip pointless work.
    Rows already `pending` are left alone: they're either queued or in flight.
    """
    rows = [
        row
        for row in list_renderings_for_birth(db, birth_id=birth_id)
        if row.status is not GiftRenderingStatus.pending
    ]
    for row in rows:
        row.status = GiftRenderingStatus.pending
        row.failure_reason = None
    return len(rows)


def ids_needing_render(db: Session, *, birth_id: uuid.UUID) -> list[uuid.UUID]:
    """Pending rows for a birth — freshly created, marked stale, or left over
    from a restart that killed their render."""
    return [
        row.id
        for row in list_renderings_for_birth(db, birth_id=birth_id)
        if row.status is GiftRenderingStatus.pending
    ]


def ids_needing_mockup_retry(db: Session, *, birth_id: uuid.UUID) -> list[uuid.UUID]:
    """Renderings whose artwork is ready but whose product mockup never
    landed — the partner refused it, or a restart killed a `pending` one.
    Without this a failed hero mockup is permanent (only a fresh re-render
    would try again) and the gallery shows the flat artwork forever, which is
    exactly the bug this exists to fix. Mirrors the retry that
    `get_or_create_product_mockup` already does for shortlist mockups."""
    if not fulfillment.is_configured():
        return []
    return [
        row.id
        for row in list_renderings_for_birth(db, birth_id=birth_id)
        if row.status is GiftRenderingStatus.ready
        and row.artwork_s3_key
        and row.mockup_status in ("failed", "pending")
        and _mockup_retry_due(row.id)
    ]


def reset_to_pending(
    db: Session, *, birth_id: uuid.UUID, rendering_id: uuid.UUID | None = None
) -> list[uuid.UUID]:
    """Flip renderings back to `pending` for a forced re-render. Scopes to a
    single rendering when `rendering_id` is given, else the whole birth.
    Returns the ids to schedule."""
    rows = list_renderings_for_birth(db, birth_id=birth_id)
    if rendering_id is not None:
        rows = [r for r in rows if r.id == rendering_id]
    for row in rows:
        row.status = GiftRenderingStatus.pending
        row.failure_reason = None
    db.commit()
    return [r.id for r in rows]


# What the editor shows is not what the printer gets. A book page is a
# 2325px print file — up to 2.4MB, and 31.6MB for the twenty-five of them —
# which the browser was downloading in full to draw a 48px tile. So a page is
# stored three ways, the shape Pearl settled on: `raw` is the print file and
# what the order ships; `display` is what the editor shows on screen;
# `thumbnail` is what the page strip draws. Measured over this book:
# raw 31.58MB · display 0.78MB (32KB a page) · thumbnail 0.17MB (7KB a page).
#
# Made once, at render time, beside the print files — never on request.
VARIANTS = {"display": (900, 82), "thumbnail": (300, 85)}


def _variant_bytes(png: bytes, size: int, quality: int) -> bytes | None:
    """One derivative of a page. None if it can't be made — a smaller copy is
    a convenience, never a reason to fail a render."""
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(png)).convert("RGB")
        im.thumbnail((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=quality, method=4)
        return buf.getvalue()
    except Exception:  # noqa: BLE001 - never fail a render for a thumbnail
        logger.warning("page variant failed", exc_info=True)
        return None


def page_variants(rendering: GiftRendering, variant: str) -> dict[str, str]:
    """The pages of a many-file design at one size, key → s3 key. Empty for a
    book rendered before that size existed, which then shows its print
    files."""
    store = (rendering.rendering_metadata or {}).get("page_variants") or {}
    return dict(store.get(variant) or {})


def print_pages(rendering: GiftRendering) -> dict[str, str]:
    """The print files of a many-file design, key → s3 key — the book's cover
    wrap and its pages. Empty for a one-file design."""
    return dict((rendering.rendering_metadata or {}).get("pages") or {})


def book_pages(rendering: GiftRendering) -> list[dict]:
    """The book's pages for the editor: in order, with kind, photo slots, a
    presigned URL for the page on screen and one for its strip thumbnail.
    Empty for anything that isn't a book."""
    plan = (rendering.rendering_metadata or {}).get("book_plan") or []
    # each size where there is one; the print file for books drawn before
    # there were, so an old book still shows its pages
    raw = print_pages(rendering)
    display = {**raw, **page_variants(rendering, "display")}
    thumb = {**display, **page_variants(rendering, "thumbnail")}
    return [
        {
            **p,
            "url": presigned_get_url(display[p["key"]]) if p["key"] in display else None,
            "thumb_url": presigned_get_url(thumb[p["key"]]) if p["key"] in thumb else None,
        }
        for p in plan
    ]


def artwork_url(rendering: GiftRendering) -> str | None:
    if rendering.status != GiftRenderingStatus.ready or not rendering.artwork_s3_key:
        return None
    return presigned_get_url(rendering.artwork_s3_key)


# Whether we have a photograph of the product is the s3 key's business; the
# status only says how current it is. A `stale` shot shows the design as it
# was before the last edit, and a `failed` one means the most recent *attempt*
# came back empty-handed — neither unmakes the photograph already taken. The
# status rides along so the UI can say so and offer to refresh.
#
# Gating these on status is how a failed refresh used to empty a gallery that
# had perfectly good shots in it: one refused request and the mug disappeared.


def mockup_url(rendering: GiftRendering) -> str | None:
    if not rendering.mockup_s3_key:
        return None
    return presigned_get_url(rendering.mockup_s3_key)


def mockup_extras(rendering: GiftRendering) -> list[dict]:
    """Extra angle/view mockups alongside the primary one, presigned. Empty
    when no mockup has ever landed or the product had none."""
    if not rendering.mockup_s3_key:
        return []
    return [
        {"title": extra.get("title", ""), "url": presigned_get_url(extra["s3_key"])}
        for extra in (rendering.mockup_extras or [])
        if extra.get("s3_key")
    ]


def product_mockup_url(mockup: GiftRenderingMockup) -> str | None:
    if mockup.status != "ready" or not mockup.mockup_s3_key:
        return None
    return presigned_get_url(mockup.mockup_s3_key)


def product_kind_for_rendering(db: Session, rendering: GiftRendering) -> str | None:
    item = db.get(GiftCatalogItem, rendering.gift_catalog_item_id)
    return item.product_kind if item is not None else None


def list_product_mockups(
    db: Session, *, rendering_id: uuid.UUID
) -> dict[str, GiftRenderingMockup]:
    """Cached product mockups for a rendering, keyed by product_key."""
    rows = db.scalars(
        select(GiftRenderingMockup).where(
            GiftRenderingMockup.gift_rendering_id == rendering_id
        )
    ).all()
    return {r.product_key: r for r in rows}


def get_or_create_product_mockup(
    db: Session, *, rendering: GiftRendering, product_key: str
) -> tuple[GiftRenderingMockup, bool]:
    """Get the cached (rendering, product_key) mockup row, creating a pending
    one if absent. Returns (row, should_render): should_render is True for a
    freshly-created row or when retrying a previously-failed one — the caller
    schedules a background render only then, so a cached row never re-hits the
    partner."""
    existing = db.scalar(
        select(GiftRenderingMockup).where(
            GiftRenderingMockup.gift_rendering_id == rendering.id,
            GiftRenderingMockup.product_key == product_key,
        )
    )
    if existing is not None:
        if existing.status == "failed":
            existing.status = "pending"
            existing.mockup_s3_key = None
            db.commit()
            return existing, True
        return existing, False

    row = GiftRenderingMockup(
        gift_rendering_id=rendering.id,
        product_key=product_key,
        status="pending",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request created it first — fall back to that row.
        db.rollback()
        row = db.scalar(
            select(GiftRenderingMockup).where(
                GiftRenderingMockup.gift_rendering_id == rendering.id,
                GiftRenderingMockup.product_key == product_key,
            )
        )
        return row, False
    return row, True


# ── background render job ─────────────────────────────────────────────────


def render_rendering(rendering_id: uuid.UUID) -> None:
    """Render one gift artwork and persist it. Runs in a FastAPI
    BackgroundTask *after* the response, so it owns its own DB session.
    Failures are recorded on the row, never raised."""
    db = SessionLocal()
    try:
        rendering = db.get(GiftRendering, rendering_id)
        if rendering is None or rendering.deleted_at is not None:
            return
        birth = db.get(Birth, rendering.birth_id)
        template = gift_templates.get(rendering.template_id)
        if birth is None or template is None:
            _fail(db, rendering, "missing-birth-or-template")
            return
        try:
            if template.scene == "book":
                files, metadata = gift_artwork.render_book(birth, template, db, rendering)
                png = files.pop("cover_front")
            else:
                png, metadata = gift_artwork.render(birth, template, db, rendering)
                files = {}
        except gift_artwork.ArtworkError as exc:
            _fail(db, rendering, str(exc))
            return

        key = object_key(
            family_id=birth.family_id,
            birth_id=birth.id,
            filename=f"gifts/{rendering.id}.png",
        )
        put_object(key=key, body=png, content_type="image/png")
        # a many-file design keeps its print files beside the one it shows
        if files:
            pages: dict[str, str] = {}
            variants: dict[str, dict[str, str]] = {v: {} for v in VARIANTS}
            for page_key, body in files.items():
                pk = object_key(
                    family_id=birth.family_id,
                    birth_id=birth.id,
                    filename=f"gifts/{rendering.id}-{page_key}.png",
                )
                put_object(key=pk, body=body, content_type="image/png")
                pages[page_key] = pk
                for variant, (size, quality) in VARIANTS.items():
                    small = _variant_bytes(body, size, quality)
                    if small is None:
                        continue
                    vk = object_key(
                        family_id=birth.family_id,
                        birth_id=birth.id,
                        filename=f"gifts/{rendering.id}-{page_key}-{variant}.webp",
                    )
                    put_object(key=vk, body=small, content_type="image/webp")
                    variants[variant][page_key] = vk
            metadata["pages"] = pages
            metadata["page_variants"] = variants
        rendering.artwork_s3_key = key
        rendering.rendering_metadata = metadata
        rendering.status = GiftRenderingStatus.ready
        rendering.failure_reason = None
        db.commit()

        # Then the product mockup — but only the first time this design has
        # ever had one. The partner rate-limits mockups to 2 per minute for
        # the *whole store*, so they can't be spent on every re-render: a
        # single birth's designs would otherwise eat minutes of a budget
        # shared by every family on the site.
        #
        # The first one is worth it — that's what fills the gallery with
        # pre-made product shots from our best guess, before anyone has asked
        # for anything. After that a mockup is generated when a human asks to
        # see one, in the customise flow, for the design they actually settled
        # on. Re-renders just mark the existing shot stale.
        if should_generate_mockup(rendering):
            _try_generate_mockup(db, rendering)
        elif rendering.mockup_status == "ready":
            rendering.mockup_status = "stale"
            db.commit()
    except Exception as exc:  # never let a background task crash silently
        db.rollback()
        rendering = db.get(GiftRendering, rendering_id)
        if rendering is not None:
            _fail(db, rendering, f"unexpected: {exc}")
    finally:
        db.close()
        _release_render(rendering_id)


def should_generate_mockup(rendering: GiftRendering) -> bool:
    """Whether a finished render should also ask the partner for a product
    shot — true only the first time a design has ever had one.

    The partner allows 2 mockups a minute for the whole store. One birth has
    eleven designs, so generating on every render would spend minutes of a
    budget shared by every family on the site, on artwork nobody has asked to
    see on a product yet. The first one earns its place: it's what fills the
    gallery with ready-made product shots. After that it's on request.
    """
    return rendering.mockup_status == "none" and not rendering.mockup_s3_key


def _try_generate_mockup(db: Session, rendering: GiftRendering) -> None:
    """Generate the default hero product mockup for a ready rendering, if a
    fulfillment partner is configured and the product_kind has a default
    product mapped. Records mockup_status; never raises."""
    adapter = fulfillment.get_adapter()
    if adapter is None or not rendering.artwork_s3_key:
        return
    item = db.get(GiftCatalogItem, rendering.gift_catalog_item_id)
    birth = db.get(Birth, rendering.birth_id)
    if item is None or birth is None:
        return
    # The product they chose, not our default — `for_rendering` is the one
    # place that decides, so the mug someone approves in the mockup and the
    # mug that ships are the same mug.
    product = fulfillment_products.for_rendering(
        rendering.product_key, item.product_kind
    )
    template = gift_templates.get(rendering.template_id)
    if product is None or template is None:
        return
    # Held separately: after a rollback the ORM object is expired, and the
    # error path still needs to say which design failed.
    rendering_id = rendering.id
    template_id = rendering.template_id

    rendering.mockup_status = "pending"
    db.commit()
    try:
        # The partner fetches the artwork by URL, so it must be publicly
        # reachable (the prod domain — a localhost dev URL won't work). The
        # app serves it via a short signed link: presigned S3 URLs from the
        # instance role exceed Printful's 1000-char URL cap.
        # a many-file design is photographed by its cover alone — the pages
        # are the parent's to look at in the editor, and sending all of them
        # made the partner slow for a picture nobody asked for
        artwork = signed_artwork_url(
            rendering_id, expires_in=3600, page="cover" if print_pages(rendering) else None
        )
        result = adapter.generate_mockup(
            artwork_url=artwork,
            product_id=product.product_id,
            variant_id=product.variant_id,
            artwork_width=template.width,
            artwork_height=template.height,
            placement=product.placement,
            option_groups=product.mockup_option_groups,
            options=product.mockup_options,
        )
        key = object_key(
            family_id=birth.family_id,
            birth_id=birth.id,
            filename=f"gifts/{rendering.id}-mockup.png",
        )
        put_object(key=key, body=result.image_bytes, content_type=result.content_type)
        extras = []
        for i, extra in enumerate(result.extra):
            extra_key = object_key(
                family_id=birth.family_id,
                birth_id=birth.id,
                filename=f"gifts/{rendering.id}-mockup-extra-{i}.png",
            )
            put_object(
                key=extra_key, body=extra.image_bytes, content_type=extra.content_type
            )
            extras.append({"title": extra.title, "s3_key": extra_key})
        rendering.mockup_s3_key = key
        rendering.mockup_extras = extras
        rendering.mockup_status = "ready"
        db.commit()
        _record_mockup_retry(rendering_id, succeeded=True)
    except Exception:  # MockupError or any transport error
        # Loud on purpose: this failure is invisible in the gallery (it just
        # keeps showing the flat artwork), so the log is the only trace.
        logger.warning(
            "mockup generation failed for rendering %s (%s) on %s",
            rendering_id,
            template_id,
            product.key,
            exc_info=True,
        )
        db.rollback()
        rendering = db.get(GiftRendering, rendering_id)
        if rendering is not None:
            rendering.mockup_status = "failed"
            db.commit()
        _record_mockup_retry(rendering_id, succeeded=False)


def refresh_mockup(rendering_id: uuid.UUID) -> None:
    """Generate a product mockup on request — the customise flow asking to see
    this design on the real thing.

    Separate from `retry_mockup`, which only picks up failures: this one is
    deliberate, so it regenerates a stale shot too. It's the only path that
    spends the partner's 2-per-minute store budget after a design's first
    render, which is what keeps that budget meaningful.
    """
    db = SessionLocal()
    try:
        rendering = db.get(GiftRendering, rendering_id)
        if (
            rendering is None
            or rendering.deleted_at is not None
            or rendering.status is not GiftRenderingStatus.ready
        ):
            return
        _try_generate_mockup(db, rendering)
    finally:
        db.close()


def retry_mockup(rendering_id: uuid.UUID) -> None:
    """Re-attempt the hero mockup for a rendering whose artwork is already
    ready — scheduled by the gallery view for rows `ids_needing_mockup_retry`
    turned up. Runs as a BackgroundTask, so it owns its session, takes the
    same in-flight claim a render does (a retry must never race a re-render
    of the same row), and never raises."""
    db = SessionLocal()
    try:
        rendering = db.get(GiftRendering, rendering_id)
        if (
            rendering is None
            or rendering.deleted_at is not None
            or rendering.status is not GiftRenderingStatus.ready
        ):
            return
        _try_generate_mockup(db, rendering)
    except Exception:  # never let a background task crash silently
        logger.warning("mockup retry crashed for %s", rendering_id, exc_info=True)
        db.rollback()
    finally:
        db.close()
        _release_render(rendering_id)


def render_product_mockup(mockup_id: uuid.UUID) -> None:
    """Generate one on-demand product mockup (a rendering's artwork on a
    shortlist product) and persist it. Runs as a BackgroundTask after the
    response, so it owns its own DB session. Failures are recorded on the row,
    never raised."""
    db = SessionLocal()
    try:
        mockup = db.get(GiftRenderingMockup, mockup_id)
        if mockup is None:
            return
        rendering = db.get(GiftRendering, mockup.gift_rendering_id)
        product = fulfillment_products.get(mockup.product_key)
        adapter = fulfillment.get_adapter()
        if (
            rendering is None
            or rendering.status != GiftRenderingStatus.ready
            or not rendering.artwork_s3_key
            or product is None
            or adapter is None
        ):
            mockup.status = "failed"
            db.commit()
            return
        birth = db.get(Birth, rendering.birth_id)
        if birth is None:
            mockup.status = "failed"
            db.commit()
            return
        try:
            artwork = signed_artwork_url(rendering.id, expires_in=3600)
            template = gift_templates.get(rendering.template_id)
            result = adapter.generate_mockup(
                artwork_url=artwork,
                product_id=product.product_id,
                variant_id=product.variant_id,
                artwork_width=template.width if template else 2475,
                artwork_height=template.height if template else 1155,
                placement=product.placement,
                option_groups=product.mockup_option_groups,
                options=product.mockup_options,
            )
            key = object_key(
                family_id=birth.family_id,
                birth_id=birth.id,
                filename=f"gifts/{rendering.id}-{product.key}.png",
            )
            put_object(
                key=key, body=result.image_bytes, content_type=result.content_type
            )
            mockup.mockup_s3_key = key
            mockup.status = "ready"
            db.commit()
        except Exception:  # MockupError or any transport error
            logger.warning(
                "product mockup failed for rendering %s on %s",
                mockup.gift_rendering_id,
                mockup.product_key,
                exc_info=True,
            )
            db.rollback()
            mockup = db.get(GiftRenderingMockup, mockup_id)
            if mockup is not None:
                mockup.status = "failed"
                db.commit()
    finally:
        db.close()


def _fail(db: Session, rendering: GiftRendering, reason: str) -> None:
    rendering.status = GiftRenderingStatus.failed
    rendering.failure_reason = reason[:500]
    db.commit()
