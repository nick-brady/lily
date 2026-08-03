"""The gift gallery: catalog, per-birth renderings, product shortlists,
and mockups. Purchasing lives in routes/checkout.py."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session

import artwork_links
import fulfillment
from auth import get_current_user
from db import get_db
from fulfillment import products as fulfillment_products
from models import BirthStatus, GiftKind, GiftRendering, GiftRenderingStatus, User
from repositories import births as births_repo
from repositories import gift_orders as gift_orders_repo
from repositories import gifts as gifts_repo
from routes.deps import BirthAccess, require_birth_access, require_parent_access
from schemas import (
    GiftGalleryOut,
    GiftItemOut,
    GiftRenderingOut,
    GiftRenderingPatchIn,
    ProductMockupOut,
    RenderingProductsOut,
)
from storage import get_object_bytes

router = APIRouter()


def _serialize_rendering(rendering) -> GiftRenderingOut:
    return GiftRenderingOut(
        id=rendering.id,
        template_id=rendering.template_id,
        status=rendering.status,
        artwork_url=gifts_repo.artwork_url(rendering),
        mockup_url=gifts_repo.mockup_url(rendering),
        mockup_status=rendering.mockup_status,
        mockup_extras=gifts_repo.mockup_extras(rendering),
        is_visible_to_viewers=rendering.is_visible_to_viewers,
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
