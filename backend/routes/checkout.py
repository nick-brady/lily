"""Gift purchasing: Stripe checkout sessions, the webhook and
redirect-confirm fulfillment entry points, the family shipping address,
and the parents' order list."""
from __future__ import annotations

import json
import os
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Path as PathParam,
    Request,
)
from sqlalchemy.orm import Session

import gift_fulfillment
import payments
from auth import get_current_user
from db import get_db
from fulfillment import products as fulfillment_products
from models import GiftCatalogItem, GiftKind, GiftOrder, GiftRenderingStatus, User
from repositories import gift_orders as gift_orders_repo
from routes.deps import (
    BirthAccess,
    require_birth_access,
    require_parent_access,
    resolve_public_birth,
)
from routes.gifts import load_rendering_for_products
from schemas import (
    GiftCheckoutIn,
    GiftCheckoutOut,
    GiftConfirmIn,
    GiftConfirmOut,
    GiftOrderAdminOut,
    ShippingAddressIn,
    ShippingAddressOut,
    StorageGiftCheckoutIn,
)

router = APIRouter()


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Stripe's source-of-truth fulfillment path. Signature-verified
    against the raw body; dispatched on metadata.kind (gift_order);
    anything else is acknowledged and ignored. Errors 500 on purpose —
    Stripe's at-least-once redelivery is the retry loop."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook not configured")
    body = await request.body()
    if not payments.verify_stripe_signature(
        body, request.headers.get("stripe-signature"), secret
    ):
        raise HTTPException(status_code=400, detail="Bad signature")
    event = json.loads(body)
    if event.get("type") != "checkout.session.completed":
        return {"received": True}
    obj = (event.get("data") or {}).get("object") or {}
    metadata = obj.get("metadata") or {}
    kind = metadata.get("kind")
    if kind != "gift_order" or obj.get("payment_status") != "paid":
        return {"received": True}
    stripe = payments.get_stripe()
    if stripe is None:  # webhook secret without an API key is a misconfig
        raise HTTPException(status_code=503, detail="Payments aren't configured")
    await gift_fulfillment.fulfill_gift_from_session(
        db, stripe, obj, background_tasks, raise_on_refund_error=True
    )
    return {"received": True}


@router.post(
    "/birth/{birth_id}/gifts/{rendering_id}/checkout",
    response_model=GiftCheckoutOut,
)
def create_gift_checkout(
    rendering_id: uuid.UUID,
    payload: GiftCheckoutIn,
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftCheckoutOut:
    """Start a gift purchase. Any family member can buy (viewers are the
    intended buyers); one family-bound purchase per item per birth, "one for
    me" copies unlimited."""
    stripe = payments.get_stripe()
    if stripe is None:
        raise HTTPException(status_code=503, detail="Payments aren't configured")

    rendering = load_rendering_for_products(db, access, rendering_id)
    if rendering.status != GiftRenderingStatus.ready:
        raise HTTPException(status_code=409, detail="Design is not ready yet")
    item = db.get(GiftCatalogItem, rendering.gift_catalog_item_id)
    if (
        item is None
        or item.kind != GiftKind.physical
        or fulfillment_products.default_for_product_kind(item.product_kind) is None
    ):
        raise HTTPException(
            status_code=409, detail={"code": "not_purchasable"}
        )
    wants_family = payload.recipient_kind in ("family", "both")
    wants_self = payload.recipient_kind in ("self", "both")
    if wants_family and item.id in gift_orders_repo.claimed_item_ids(
        db, birth_id=access.birth.id
    ):
        # UX guard — the partial unique index is the real enforcement
        raise HTTPException(status_code=409, detail={"code": "already_claimed"})
    if payload.recipient_kind == "both" and access.birth.shipping_address is None:
        # Stripe collects exactly one address per session (the buyer's, for
        # the self copy) — the family copy needs the parent-saved address.
        raise HTTPException(
            status_code=409, detail={"code": "family_address_required"}
        )

    message = (payload.gift_message or "").strip() or None
    orders = []
    if wants_family:
        orders.append(
            gift_orders_repo.create_pending_order(
                db,
                birth=access.birth,
                item=item,
                rendering=rendering,
                user=current_user,
                recipient_kind="family",
                gift_message=message,
            )
        )
    if wants_self:
        orders.append(
            gift_orders_repo.create_pending_order(
                db,
                birth=access.birth,
                item=item,
                rendering=rendering,
                user=current_user,
                recipient_kind="self",
                gift_message=None if wants_family else message,
            )
        )
    collect_shipping = wants_self or access.birth.shipping_address is None
    try:
        session = stripe.create_gift_checkout_session(
            order_id=str(orders[0].id),
            birth_id=str(access.birth.id),
            user_id=str(current_user.id),
            slug=access.birth.slug,
            product_name=item.display_name,
            amount_cents=item.base_price_cents,
            collect_shipping=collect_shipping,
            allowed_countries=payments.gift_shipping_countries(),
            quantity=len(orders),
            extra_order_id=str(orders[1].id) if len(orders) > 1 else None,
        )
    except payments.StripeError:
        # the pending rows are inert; leave them
        raise HTTPException(
            status_code=502, detail="Couldn't start checkout — try again"
        )
    for order in orders:
        gift_orders_repo.attach_session(db, order, session["id"])
    return GiftCheckoutOut(url=session["url"])


@router.post(
    "/birth/{birth_id}/gifts/storage/{item_id}/checkout",
    response_model=GiftCheckoutOut,
)
def create_storage_gift_checkout(
    item_id: uuid.UUID,
    payload: StorageGiftCheckoutIn = Body(default=StorageGiftCheckoutIn()),
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftCheckoutOut:
    """Start a storage-gift purchase. Unlike physical items there's no
    rendering (no artwork behind it) and no shipping — it's always a gift
    to the family, one-of-one per birth, same claim mechanic as a
    family-bound physical gift."""
    stripe = payments.get_stripe()
    if stripe is None:
        raise HTTPException(status_code=503, detail="Payments aren't configured")

    item = db.get(GiftCatalogItem, item_id)
    if item is None or item.kind != GiftKind.storage_gift or not item.is_active:
        raise HTTPException(status_code=409, detail={"code": "not_purchasable"})
    if item.id in gift_orders_repo.claimed_item_ids(db, birth_id=access.birth.id):
        # UX guard — the partial unique index is the real enforcement
        raise HTTPException(status_code=409, detail={"code": "already_claimed"})

    order = gift_orders_repo.create_pending_order(
        db,
        birth=access.birth,
        item=item,
        rendering=None,
        user=current_user,
        recipient_kind="family",
        gift_message=(payload.gift_message or "").strip() or None,
    )
    try:
        session = stripe.create_gift_checkout_session(
            order_id=str(order.id),
            birth_id=str(access.birth.id),
            user_id=str(current_user.id),
            slug=access.birth.slug,
            product_name=item.display_name,
            amount_cents=item.base_price_cents,
            collect_shipping=False,
            allowed_countries=payments.gift_shipping_countries(),
        )
    except payments.StripeError:
        # the pending row is inert; leave it
        raise HTTPException(
            status_code=502, detail="Couldn't start checkout — try again"
        )
    gift_orders_repo.attach_session(db, order, session["id"])
    return GiftCheckoutOut(url=session["url"])


@router.post("/b/{slug}/gifts/confirm", response_model=GiftConfirmOut)
async def confirm_gift(
    payload: GiftConfirmIn,
    background_tasks: BackgroundTasks,
    slug: str = PathParam(...),
    db: Session = Depends(get_db),
) -> GiftConfirmOut:
    """Redirect-return fulfillment for gifts (the dev path — no webhook
    needed). Deliberately unauthenticated: all trust comes from retrieving
    the session server-side with our key (a forged id 404s at Stripe)."""
    stripe = payments.get_stripe()
    if stripe is None:
        raise HTTPException(status_code=503, detail="Payments aren't configured")
    birth = resolve_public_birth(db, slug)
    session = stripe.retrieve_checkout_session(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown checkout session")
    metadata = session.get("metadata") or {}
    if (
        metadata.get("kind") != "gift_order"
        or metadata.get("birth_id") != str(birth.id)
    ):
        raise HTTPException(status_code=400, detail="Session doesn't match this page")
    if session.get("payment_status") != "paid":
        return GiftConfirmOut(status="pending")
    status = await gift_fulfillment.fulfill_gift_from_session(
        db, stripe, session, background_tasks, raise_on_refund_error=False
    )
    return GiftConfirmOut(status=status)


@router.get(
    "/birth/{birth_id}/shipping-address", response_model=ShippingAddressOut
)
def get_shipping_address(
    access: BirthAccess = Depends(require_parent_access),
) -> ShippingAddressOut:
    """Parent-only on purpose — the family's home address never rides on the
    public birth payload."""
    return ShippingAddressOut(address=access.birth.shipping_address)


@router.put(
    "/birth/{birth_id}/shipping-address", response_model=ShippingAddressOut
)
def put_shipping_address(
    payload: ShippingAddressIn,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> ShippingAddressOut:
    allowed = set(payments.gift_shipping_countries())
    if payload.country.upper() not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Shipping is currently available to: {', '.join(sorted(allowed))}",
        )
    access.birth.shipping_address = {
        "name": payload.name,
        "line1": payload.line1,
        "line2": payload.line2,
        "city": payload.city,
        "state": payload.state,
        "postal_code": payload.postal_code,
        "country": payload.country.upper(),
    }
    db.commit()
    return ShippingAddressOut(address=access.birth.shipping_address)


@router.get(
    "/birth/{birth_id}/gifts/orders", response_model=list[GiftOrderAdminOut]
)
def list_gift_orders(
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> list[GiftOrderAdminOut]:
    """Gifts received — buyer, item, their note, fulfillment state."""
    rows = gift_orders_repo.list_orders_for_birth(db, birth_id=access.birth.id)
    return [GiftOrderAdminOut(**row) for row in rows]


@router.post("/birth/{birth_id}/gifts/orders/{order_id}/retry-fulfillment")
def retry_gift_fulfillment(
    order_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    access: BirthAccess = Depends(require_parent_access),
    db: Session = Depends(get_db),
) -> dict:
    """Re-run a failed shipment submission (the submitting CAS makes this
    double-POST-safe)."""
    order = db.get(GiftOrder, order_id)
    if order is None or order.birth_id != access.birth.id:
        raise HTTPException(status_code=404, detail="Order not found")
    shipment = gift_orders_repo.retryable_shipment(db, order_id=order_id)
    if shipment is None:
        raise HTTPException(status_code=409, detail="Nothing to retry")
    background_tasks.add_task(gift_orders_repo.submit_shipment, shipment.id)
    return {"scheduled": True}
