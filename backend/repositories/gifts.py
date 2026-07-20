"""Gift catalog + rendering persistence and the render job.

Renderings are created lazily: opening a birth's gift gallery ensures a
`pending` row exists per (active physical catalog item × its templates), and
the route schedules a background render for the newly-created ones. Storage
gifts have no artwork and never get a rendering row.
"""
from __future__ import annotations

import uuid

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
    GiftCatalogItem,
    GiftKind,
    GiftRendering,
    GiftRenderingMockup,
    GiftRenderingStatus,
)
from storage import object_key, presigned_get_url, put_object


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
        # reachable (real S3 in prod — a localhost dev MinIO URL won't work).
        artwork = presigned_get_url(rendering.artwork_s3_key, expires_in=3600)
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
        rendering.mockup_s3_key = key
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
            artwork = presigned_get_url(rendering.artwork_s3_key, expires_in=3600)
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
