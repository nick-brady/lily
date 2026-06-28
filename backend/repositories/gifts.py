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

import gift_artwork
import gift_templates
from db import SessionLocal
from models import (
    Birth,
    GiftCatalogItem,
    GiftKind,
    GiftRendering,
    GiftRenderingStatus,
)
from storage import object_key, presigned_get_url, put_object


def list_active_catalog(db: Session) -> list[GiftCatalogItem]:
    return list(
        db.scalars(
            select(GiftCatalogItem)
            .where(GiftCatalogItem.is_active.is_(True))
            .order_by(GiftCatalogItem.created_at.asc())
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
    except Exception as exc:  # never let a background task crash silently
        db.rollback()
        rendering = db.get(GiftRendering, rendering_id)
        if rendering is not None:
            _fail(db, rendering, f"unexpected: {exc}")
    finally:
        db.close()


def _fail(db: Session, rendering: GiftRendering, reason: str) -> None:
    rendering.status = GiftRenderingStatus.failed
    rendering.failure_reason = reason[:500]
    db.commit()
