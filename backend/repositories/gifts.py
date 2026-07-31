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

import threading
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


def artwork_url(rendering: GiftRendering) -> str | None:
    if rendering.status != GiftRenderingStatus.ready or not rendering.artwork_s3_key:
        return None
    return presigned_get_url(rendering.artwork_s3_key)


def mockup_url(rendering: GiftRendering) -> str | None:
    if rendering.mockup_status != "ready" or not rendering.mockup_s3_key:
        return None
    return presigned_get_url(rendering.mockup_s3_key)


def mockup_extras(rendering: GiftRendering) -> list[dict]:
    """Extra angle/view mockups alongside the primary one, presigned. Empty
    when the mockup isn't ready or the product had none."""
    if rendering.mockup_status != "ready":
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
            png, metadata = gift_artwork.render(birth, template, db)
        except gift_artwork.ArtworkError as exc:
            _fail(db, rendering, str(exc))
            return

        key = object_key(
            family_id=birth.family_id,
            birth_id=birth.id,
            filename=f"gifts/{rendering.id}.png",
        )
        put_object(key=key, body=png, content_type="image/png")
        rendering.artwork_s3_key = key
        rendering.rendering_metadata = metadata
        rendering.status = GiftRenderingStatus.ready
        rendering.failure_reason = None
        db.commit()

        # Then try to turn the flat artwork into a product mockup via the
        # fulfillment partner. Best-effort: a failure here never fails the
        # rendering — the gallery just keeps showing the flat artwork.
        _try_generate_mockup(db, rendering)
    except Exception as exc:  # never let a background task crash silently
        db.rollback()
        rendering = db.get(GiftRendering, rendering_id)
        if rendering is not None:
            _fail(db, rendering, f"unexpected: {exc}")
    finally:
        db.close()
        _release_render(rendering_id)


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
    product = fulfillment_products.default_for_product_kind(item.product_kind)
    template = gift_templates.get(rendering.template_id)
    if product is None or template is None:
        return

    rendering.mockup_status = "pending"
    db.commit()
    try:
        # The partner fetches the artwork by URL, so it must be publicly
        # reachable (the prod domain — a localhost dev URL won't work). The
        # app serves it via a short signed link: presigned S3 URLs from the
        # instance role exceed Printful's 1000-char URL cap.
        artwork = signed_artwork_url(rendering.id, expires_in=3600)
        result = adapter.generate_mockup(
            artwork_url=artwork,
            product_id=product.product_id,
            variant_id=product.variant_id,
            artwork_width=template.width,
            artwork_height=template.height,
            placement=product.placement,
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
    except Exception:  # MockupError or any transport error
        db.rollback()
        rendering = db.get(GiftRendering, rendering.id)
        if rendering is not None:
            rendering.mockup_status = "failed"
            db.commit()


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
