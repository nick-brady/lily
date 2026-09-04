"""Gift purchasing: Stripe checkout sessions, the webhook and
redirect-confirm fulfillment entry points, the family shipping address,
and the parents' order list."""
from __future__ import annotations

import json
import logging
import os
import secrets
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Path as PathParam,
    Request,
    Response,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

import address_validation
import admin as admin_mod
import fulfillment
import gift_fulfillment
import gift_receipt_email
import gift_shipping
import payments
from auth import get_current_user
from db import get_db
from fulfillment import products as fulfillment_products
from fulfillment.base import OrderError
from models import GiftCatalogItem, GiftKind, GiftOrder, GiftRenderingStatus, GiftShipment, User
from repositories import gift_orders as gift_orders_repo
from routes.deps import (
    BirthAccess,
    require_birth_access,
    require_parent_access,
    resolve_public_birth,
)
from routes.gifts import load_rendering_for_products
from schemas import (
    AdminOrderOut,
    MyOrderOut,
    OrderReceiptLineOut,
    OrderReceiptOut,
    AddressReviewIn,
    AddressReviewOut,
    GiftCheckoutIn,
    GiftCheckoutOut,
    GiftConfirmIn,
    GiftConfirmOut,
    GiftOrderAdminOut,
    ShippingAddressIn,
    ShippingAddressOut,
    ShippingQuoteIn,
    ShippingQuoteOut,
    StorageGiftCheckoutIn,
)

logger = logging.getLogger(__name__)

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


@router.post("/webhooks/printful/{token}")
async def printful_webhook(
    token: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """What the printer tells us after the draft: shipped (with tracking),
    failed, canceled, held. Printful doesn't sign its webhooks, so the URL
    carries a secret; a wrong one is a 404 that says nothing. Always 200 for
    a recognised caller — Printful retries anything else, and a shipment we
    can't match is our problem to look into, not theirs to resend."""
    expected = os.getenv("PRINTFUL_WEBHOOK_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="Webhook not configured")
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        event = json.loads(await request.body())
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad body")
    outcome = gift_orders_repo.apply_partner_event(db, event)
    if outcome == "unknown_order":
        logger.warning("printful %s for an order we don't know", event.get("type"))
    elif outcome == "shipped":
        shipment = gift_orders_repo.shipment_for_partner_order(db, (event.get("data") or {}).get("order") or {})
        if shipment is not None:
            background_tasks.add_task(gift_receipt_email.send_shipped, shipment.id)
    return {"received": True, "outcome": outcome}


def _checked(address, whose: str) -> dict:
    """A destination we're willing to send a parcel to, as a plain dict.

    Structure only. Whether the place is real is Google's opinion and the
    buyer's to overrule — see address_validation.review — but a missing
    postcode or a country we don't ship to is ours to refuse, and refusing it
    here costs a form field where refusing it later costs a failed shipment
    with the money already taken."""
    if address is None:
        raise HTTPException(
            status_code=422, detail=f"We need {whose} to send this."
        )
    data = address.model_dump()
    data["country"] = (data.get("country") or "US").upper()
    try:
        address_validation.check_structure(
            data, allowed_countries=payments.gift_shipping_countries()
        )
    except address_validation.AddressError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return data


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
    # Where each copy is going, settled before anyone pays and written onto
    # the order. The parents' saved address is copied here rather than read at
    # shipping time: an order should say where it was going, and the buyer is
    # being charged for a parcel to a particular place. If that address
    # changed between the payment and the shipment, we'd be delivering
    # something nobody agreed to.
    family_address = None
    if wants_family:
        family_address = (
            dict(access.birth.shipping_address)
            if access.birth.shipping_address
            else _checked(payload.family_address, "the family's address")
        )
    self_address = _checked(payload.self_address, "your address") if wants_self else None

    # Bigger and darker mugs cost us more, so the choice carries a flat
    # surcharge. Priced off the rendering rather than the request: what ships
    # is what the design says, so what's charged should be too.
    product = fulfillment_products.for_rendering(
        getattr(rendering, "product_key", None), item.product_kind
    )
    item_cents = item.base_price_cents + fulfillment_products.surcharge_for(
        getattr(rendering, "product_key", None)
    )
    # Postage, per parcel, for the address it's going to — the partner bills
    # us for every one, so every one is charged. Quoted now and written onto
    # the order, so the number on the pay button, the Stripe line and the
    # record all say the same thing.
    message = (payload.gift_message or "").strip() or None
    orders = []
    if wants_family:
        postage = gift_shipping.quote(product, family_address)
        orders.append(
            gift_orders_repo.create_pending_order(
                db,
                birth=access.birth,
                item=item,
                rendering=rendering,
                user=current_user,
                recipient_kind="family",
                gift_message=message,
                shipping_address=family_address,
                item_cents=item_cents,
                shipping_cents=postage.cents,
                shipping_estimated=postage.estimated,
            )
        )
    if wants_self:
        postage = gift_shipping.quote(product, self_address)
        orders.append(
            gift_orders_repo.create_pending_order(
                db,
                birth=access.birth,
                item=item,
                rendering=rendering,
                user=current_user,
                recipient_kind="self",
                gift_message=None if wants_family else message,
                shipping_address=self_address,
                item_cents=item_cents,
                shipping_cents=postage.cents,
                shipping_estimated=postage.estimated,
            )
        )
    shipping_cents = sum(order.shipping_cents for order in orders)
    # Stripe takes the payment; it no longer takes the destination. It never
    # needed one — Printful ships the mug — and its page can only hold a
    # single address, which is what made two parcels in one payment
    # impossible.
    collect_shipping = False
    try:
        session = stripe.create_gift_checkout_session(
            order_id=str(orders[0].id),
            birth_id=str(access.birth.id),
            user_id=str(current_user.id),
            slug=access.birth.slug,
            product_name=item.display_name,
            amount_cents=item_cents,
            collect_shipping=collect_shipping,
            allowed_countries=payments.gift_shipping_countries(),
            quantity=len(orders),
            extra_order_id=str(orders[1].id) if len(orders) > 1 else None,
            shipping_cents=shipping_cents,
            shipping_label="Shipping" if len(orders) == 1 else "Shipping (2 parcels)",
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


@router.post(
    "/birth/{birth_id}/gifts/{rendering_id}/shipping-quote",
    response_model=ShippingQuoteOut,
)
def quote_shipping(
    rendering_id: uuid.UUID,
    payload: ShippingQuoteIn,
    access: BirthAccess = Depends(require_birth_access),
    db: Session = Depends(get_db),
) -> ShippingQuoteOut:
    """What posting this design to one address will cost, before anyone pays.

    The same quote the checkout takes, so the sheet's total and Stripe's
    agree. A family copy to the parents' saved address is priced without the
    address ever leaving the server. Any family member may ask: buyers are
    viewers."""
    rendering = load_rendering_for_products(db, access, rendering_id)
    item = db.get(GiftCatalogItem, rendering.gift_catalog_item_id)
    product = (
        fulfillment_products.for_rendering(
            getattr(rendering, "product_key", None), item.product_kind
        )
        if item is not None
        else None
    )
    if product is None:
        raise HTTPException(status_code=409, detail={"code": "not_purchasable"})
    if payload.recipient_kind == "family" and access.birth.shipping_address:
        address = dict(access.birth.shipping_address)
    else:
        address = _checked(
            payload.address,
            "the family's address" if payload.recipient_kind == "family" else "your address",
        )
    postage = gift_shipping.quote(product, address)
    return ShippingQuoteOut(
        shipping_cents=postage.cents,
        estimated=postage.estimated,
        service=postage.service,
        item_cents=item.base_price_cents
        + fulfillment_products.surcharge_for(getattr(rendering, "product_key", None)),
        min_days=postage.min_days,
        max_days=postage.max_days,
    )


@router.post(
    "/birth/{birth_id}/gifts/address-review", response_model=AddressReviewOut
)
def review_shipping_address(
    payload: AddressReviewIn,
    access: BirthAccess = Depends(require_birth_access),
) -> AddressReviewOut:
    """Look over an address the buyer is typing, before they pay for it.

    Advisory by design. It refuses nothing the checkout wouldn't refuse
    anyway; it offers the postal service's spelling and admits when it can't
    find the place. Available to any family member because gift buyers are
    viewers, and the address they're describing is one they already know."""
    data = payload.address.model_dump()
    data["country"] = (data.get("country") or "US").upper()
    try:
        address_validation.check_structure(
            data, allowed_countries=payments.gift_shipping_countries()
        )
    except address_validation.AddressError as exc:
        return AddressReviewOut(verdict="unchecked", structure_error=str(exc))
    result = address_validation.review(data)
    return AddressReviewOut(
        verdict=result["verdict"], suggestion=result["suggestion"]
    )


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


@router.get("/admin/orders", response_model=list[AdminOrderOut])
def admin_orders(
    admin_user: User = Depends(admin_mod.get_admin_user),
    db: Session = Depends(get_db),
) -> list[AdminOrderOut]:
    """Every order, for the operator: buyer, item, money in and out, where
    the printer has it, and the ids to find it in Stripe and Printful."""
    return [AdminOrderOut(**row) for row in gift_orders_repo.admin_orders(db)]


def _admin_order_row(db: Session, order_id: uuid.UUID) -> AdminOrderOut:
    for row in gift_orders_repo.admin_orders(db, limit=1000):
        if row["id"] == order_id:
            return AdminOrderOut(**row)
    raise HTTPException(status_code=404, detail="Order not found")


@router.post("/admin/orders/{order_id}/approve", response_model=AdminOrderOut)
def admin_approve_order(
    order_id: uuid.UUID,
    admin_user: User = Depends(admin_mod.get_admin_user),
    db: Session = Depends(get_db),
) -> AdminOrderOut:
    """Send the draft to print. This is where our money moves at the
    partner, so it is a deliberate act from the admin page, never a flag."""
    order = db.get(GiftOrder, order_id)
    if order is None or order.status != "paid":
        raise HTTPException(status_code=404, detail="No paid order")
    shipment = db.scalar(
        select(GiftShipment).where(GiftShipment.gift_order_id == order_id).order_by(GiftShipment.created_at.desc())
    )
    adapter = fulfillment.get_adapter()
    if shipment is None or adapter is None:
        raise HTTPException(status_code=409, detail="Nothing at the printer to approve")
    try:
        gift_orders_repo.approve_shipment(db, shipment, adapter=adapter, by_user_id=admin_user.id)
    except gift_orders_repo.NotADraft as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except OrderError as exc:
        logger.error("approve failed for shipment %s: %s", shipment.id, exc)
        raise HTTPException(status_code=502, detail=str(exc))
    return _admin_order_row(db, order_id)


@router.post("/admin/orders/{order_id}/cancel", response_model=AdminOrderOut)
def admin_cancel_order(
    order_id: uuid.UUID,
    admin_user: User = Depends(admin_mod.get_admin_user),
    db: Session = Depends(get_db),
) -> AdminOrderOut:
    """Cancel the draft and refund the buyer in full — the Terms' promise
    for any order not yet sent to print."""
    order = db.get(GiftOrder, order_id)
    if order is None or order.status not in ("paid", "refunded"):
        raise HTTPException(status_code=404, detail="No paid order")
    shipment = db.scalar(
        select(GiftShipment).where(GiftShipment.gift_order_id == order_id).order_by(GiftShipment.created_at.desc())
    )
    try:
        gift_orders_repo.cancel_and_refund(
            db, order, shipment, adapter=fulfillment.get_adapter(), stripe=payments.get_stripe()
        )
    except gift_orders_repo.NotADraft as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (OrderError, payments.StripeError) as exc:
        logger.error("cancel failed for order %s: %s", order_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))
    return _admin_order_row(db, order_id)


@router.get("/me/orders", response_model=list[MyOrderOut])
def my_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MyOrderOut]:
    """What the signed-in person has bought, across every page, newest
    first. Each links to its receipt."""
    return [MyOrderOut(**row) for row in gift_orders_repo.my_orders(db, user_id=current_user.id)]


@router.get("/b/{slug}/orders/{order_id}", response_model=OrderReceiptOut)
def gift_order_receipt(
    slug: str,
    order_id: uuid.UUID,
    response: Response,
    db: Session = Depends(get_db),
) -> OrderReceiptOut:
    """The page after Stripe: what was bought, where it's going, what it
    cost, where it stands. Unauthenticated like the confirm route — the
    order id is the key and the page carries nothing a stranger could use
    (no email, no street, no partner or payment ids)."""
    birth = resolve_public_birth(db, slug)
    order = db.get(GiftOrder, order_id)
    if order is None or order.birth_id != birth.id:
        raise HTTPException(status_code=404, detail="Unknown order")
    response.headers["Cache-Control"] = "no-store"
    return OrderReceiptOut(
        slug=birth.slug,
        child_name=birth.child_name,
        theme=birth.theme or "lily",
        orders=[
            OrderReceiptLineOut(**line)
            for line in gift_orders_repo.receipt(db, order, birth)
        ],
    )


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
