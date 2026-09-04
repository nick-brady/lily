"""Gift orders — the purchase path for physical gifts and storage gifts.

Only the database lives here (Stripe calls and refund decisions belong to
the route-layer funnel, house style). Two invariants do all the race work:

- pending→paid is a compare-and-swap UPDATE, so the webhook and the
  redirect-confirm fulfilling the SAME order can't both win — exactly one
  caller ever creates the shipment and schedules Printful.
- the partial unique index uq_gift_orders_family_claim makes the loser of a
  cross-order family-bound race fail its CAS with IntegrityError (Postgres
  enforces partial unique indexes on the UPDATE's new tuple); the caller
  refunds and we record 'refunded'.

Storage-gift orders share this same table and the same claim index —
`gift_rendering_id` is just null for them (no artwork behind a storage
gift). They skip shipping/fulfillment entirely; see `grant_storage_gift`.
"""
from __future__ import annotations

import logging

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import fulfillment
import gift_shipping
from db import SessionLocal
from fulfillment import products as fulfillment_products
from models import (
    GiftKind,
    Birth,
    GiftCatalogItem,
    GiftOrder,
    GiftRendering,
    GiftShipment,
    User,
)
from artwork_links import signed_artwork_url
from repositories import gifts as gifts_repo

# Draft orders can sit in the Printful dashboard for days before a human
# confirms them; the artwork link must outlive that window (7 days).
_ORDER_FILE_TTL_SECONDS = 604800

# Alembic can't express "365 days per storage_years_granted" declaratively,
# so we approximate a year at fulfillment time instead. Good enough for a
# feature measured in years, not days.
_DAYS_PER_YEAR = 365

MarkPaidOutcome = Literal["paid", "already_paid", "already_refunded", "claim_lost"]


logger = logging.getLogger(__name__)

def create_pending_order(
    db: Session,
    *,
    birth: Birth,
    item: GiftCatalogItem,
    rendering: GiftRendering | None,
    user: User,
    recipient_kind: str,
    gift_message: str | None,
    shipping_address: dict | None = None,
    item_cents: int | None = None,
    shipping_cents: int = 0,
    shipping_estimated: bool = False,
) -> GiftOrder:
    """A pending order priced in full: the item (with any product surcharge,
    `item_cents`; the catalog price when unsaid) plus the postage quoted for
    its address. What Stripe charges is built from these same numbers."""
    order = GiftOrder(
        birth_id=birth.id,
        gift_catalog_item_id=item.id,
        gift_rendering_id=rendering.id if rendering else None,
        purchased_by_user_id=user.id,
        recipient_kind=recipient_kind,
        gift_message=gift_message,
        shipping_address=shipping_address,
        amount_cents=(item.base_price_cents if item_cents is None else item_cents)
        + shipping_cents,
        product_price_cents=item.base_price_cents if item_cents is None else item_cents,
        shipping_cents=shipping_cents,
        shipping_estimated=shipping_estimated,
    )
    db.add(order)
    db.commit()
    return order


def attach_session(db: Session, order: GiftOrder, session_id: str) -> None:
    order.stripe_checkout_session_id = session_id
    db.commit()


def claimed_item_ids(db: Session, *, birth_id: uuid.UUID) -> set[uuid.UUID]:
    """Catalog items already claimed by a family-bound paid order — one
    set-query for the whole gallery (served by the claim index itself)."""
    rows = db.scalars(
        select(GiftOrder.gift_catalog_item_id).where(
            GiftOrder.birth_id == birth_id,
            GiftOrder.status == "paid",
            GiftOrder.recipient_kind == "family",
        )
    ).all()
    return set(rows)


def mark_paid(
    db: Session,
    *,
    order_id: uuid.UUID,
    session_obj: dict,
    charged_cents: int | None = None,
    orders_in_session: int = 1,
) -> tuple[MarkPaidOutcome, GiftOrder | None]:
    """CAS the order pending→paid, recording the payment identifiers and the
    amount Stripe actually charged. `charged_cents` overrides the session's
    amount_total. So does `orders_in_session` > 1: a "both" purchase records
    each copy's own price — the session was built from exactly those pending
    amounts, and two parcels to two places can carry different postage — with
    an even split of the total only for a row that was never priced. Outcomes:

    - "paid": this caller won — it (alone) creates the shipment and
      schedules fulfillment.
    - "already_paid" / "already_refunded": duplicate delivery — no-op.
    - "claim_lost": the family-bound claim index rejected the transition
      (another order already claimed the item) — the caller refunds, then
      calls mark_refunded.
    """
    order = db.get(GiftOrder, order_id)
    if order is None:
        raise LookupError(f"no gift order {order_id}")

    if charged_cents is None and orders_in_session > 1:
        charged_cents = order.amount_cents or (
            (session_obj.get("amount_total") or 0) // orders_in_session or None
        )

    session_id = session_obj.get("id")
    # NULL-session window: if the write-back after session creation failed,
    # accept and backfill; a *different* recorded session can't legitimately
    # happen (every checkout creates its own order) — treat as foreign.
    if (
        order.stripe_checkout_session_id is not None
        and session_id is not None
        and order.stripe_checkout_session_id != session_id
    ):
        return "already_paid", order

    try:
        result = db.execute(
            update(GiftOrder)
            .where(GiftOrder.id == order_id, GiftOrder.status == "pending")
            .values(
                status="paid",
                paid_at=datetime.now(timezone.utc),
                stripe_checkout_session_id=session_id
                or order.stripe_checkout_session_id,
                stripe_payment_intent_id=session_obj.get("payment_intent"),
                amount_cents=charged_cents
                or session_obj.get("amount_total")
                or order.amount_cents,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        db.refresh(order)
        return "claim_lost", order

    if result.rowcount == 0:
        db.refresh(order)
        if order.status == "refunded":
            return "already_refunded", order
        return "already_paid", order
    db.refresh(order)
    return "paid", order


def mark_refunded(db: Session, *, order_id: uuid.UUID) -> None:
    db.execute(
        update(GiftOrder)
        .where(GiftOrder.id == order_id)
        .values(status="refunded")
    )
    db.commit()


def grant_storage_gift(
    db: Session, *, birth: Birth, storage_years_granted: int | None
) -> None:
    """Extend (never shorten) `birth.storage_paid_until` by the granted
    years. Stacks from the later of "now" and the current value, so a
    second grandparent's gift adds on top of the first's instead of
    resetting the clock. `None` years is the lifetime gift — it sets the
    permanent flag and leaves the date alone (lifetime never downgrades,
    and a later year-grant on top of lifetime is a harmless no-op for
    display, which prefers the flag)."""
    if storage_years_granted is None:
        birth.storage_lifetime = True
        db.commit()
        return
    now = datetime.now(timezone.utc)
    base = birth.storage_paid_until if birth.storage_paid_until and birth.storage_paid_until > now else now
    birth.storage_paid_until = base + timedelta(days=_DAYS_PER_YEAR * storage_years_granted)
    db.commit()


def create_shipment(
    db: Session, *, order: GiftOrder, address: dict | None
) -> GiftShipment:
    """The single shipment of this phase. A missing address (shouldn't
    happen given the collection rules; belt-and-braces) records an
    immediately-failed shipment — the order stays paid and a human fixes
    it via retry."""
    shipment = GiftShipment(
        gift_order_id=order.id,
        recipient_kind=order.recipient_kind,
        address=address,
    )
    if address is None:
        shipment.fulfillment_status = "failed"
        shipment.failure_reason = "missing address"
    db.add(shipment)
    db.commit()
    return shipment


def retryable_shipment(db: Session, *, order_id: uuid.UUID) -> GiftShipment | None:
    return db.scalar(
        select(GiftShipment).where(
            GiftShipment.gift_order_id == order_id,
            GiftShipment.fulfillment_status == "failed",
        )
    )


def list_orders_for_birth(db: Session, *, birth_id: uuid.UUID) -> list[dict]:
    """Paid + refunded orders with what the parents care about: who, what,
    the note, and where fulfillment stands."""
    rows = db.execute(
        select(GiftOrder, GiftCatalogItem, User, GiftShipment)
        .join(GiftCatalogItem, GiftCatalogItem.id == GiftOrder.gift_catalog_item_id)
        .outerjoin(User, User.id == GiftOrder.purchased_by_user_id)
        .outerjoin(GiftShipment, GiftShipment.gift_order_id == GiftOrder.id)
        .where(
            GiftOrder.birth_id == birth_id,
            GiftOrder.status.in_(["paid", "refunded"]),
        )
        .order_by(GiftOrder.created_at.desc())
    ).all()
    out = []
    for order, item, user, shipment in rows:
        out.append(
            {
                "id": order.id,
                "status": order.status,
                "recipient_kind": order.recipient_kind,
                "gift_message": order.gift_message,
                "amount_cents": order.amount_cents,
                "shipping_cents": order.shipping_cents,
                "purchased_by": user.display_name if user else None,
                "item_display_name": item.display_name,
                "fulfillment_status": shipment.fulfillment_status
                if shipment
                else "none",
                "fulfillment_failure": shipment.failure_reason if shipment else None,
                "created_at": order.created_at,
            }
        )
    return out


def _printful_confirm_enabled() -> bool:
    return os.getenv("PRINTFUL_CONFIRM_ORDERS", "").lower() in ("1", "true", "yes")


def split_fee(total_fee_cents: int, amounts_cents: list[int]) -> list[int]:
    """One payment's processing fee shared across the orders it paid for, in
    proportion to what each charged, summing exactly to the fee. A single
    order takes the whole fee."""
    total = sum(amounts_cents)
    if not amounts_cents:
        return []
    if total <= 0:
        return [total_fee_cents] + [0] * (len(amounts_cents) - 1)
    shares = [total_fee_cents * a // total for a in amounts_cents]
    shares[0] += total_fee_cents - sum(shares)  # rounding remainder to the first
    return shares


def record_payment_fees(db: Session, *, orders: list[GiftOrder], fee_cents: int) -> None:
    """Write each order's share of the payment's fee."""
    for order, share in zip(orders, split_fee(fee_cents, [o.amount_cents or 0 for o in orders])):
        order.payment_fee_cents = share
    db.commit()


def order_reference(order_id: uuid.UUID) -> str:
    """What a buyer quotes if they write in: eight characters, upper-case,
    from the id — not the UUID, not Stripe's ids."""
    return order_id.hex[:8].upper()


def _destination(address: dict | None) -> str | None:
    """City and state only. The full address is the buyer's already and
    needn't be on a screen someone else might see."""
    if not address:
        return None
    city = address.get("city")
    if city and city.isupper():
        city = city.title()  # "RALEIGH" as the partner stores it → "Raleigh"
    state = address.get("state") or address.get("state_code")
    return ", ".join(p for p in (city, state) if p) or None


def receipt_line(db: Session, o: GiftOrder, birth: Birth) -> dict:
    """One order as its buyer may see it (see OrderReceiptLineOut)."""
    item = db.get(GiftCatalogItem, o.gift_catalog_item_id)
    rendering = db.get(GiftRendering, o.gift_rendering_id) if o.gift_rendering_id else None
    shipment = db.scalar(
        select(GiftShipment).where(GiftShipment.gift_order_id == o.id).order_by(GiftShipment.created_at.desc())
    )
    product = (
        fulfillment_products.for_rendering(getattr(rendering, "product_key", None), item.product_kind)
        if item is not None and item.kind == GiftKind.physical
        else None
    )
    address = (shipment.address if shipment else None) or o.shipping_address or (
        birth.shipping_address if o.recipient_kind == "family" else None
    )
    image = None
    if rendering is not None:
        image = gifts_repo.mockup_url(rendering) or gifts_repo.artwork_url(rendering)
    return {
        "id": o.id,
        "reference": order_reference(o.id),
        "status": o.status,
        "fulfillment_status": shipment.fulfillment_status if shipment else "none",
        "recipient_kind": o.recipient_kind,
        "item_display_name": item.display_name if item else "Gift",
        "product_display_name": product.display_name if product else None,
        "image_url": image,
        "destination": _destination(address),
        "product_price_cents": o.product_price_cents
        if o.product_price_cents is not None
        else max(0, (o.amount_cents or 0) - (o.shipping_cents or 0)),
        "shipping_cents": o.shipping_cents or 0,
        "amount_cents": o.amount_cents or 0,
        "gift_message": o.gift_message,
        "created_at": o.created_at,
    }


def receipt(db: Session, order: GiftOrder, birth: Birth) -> list[dict]:
    """The buyer's view of a checkout: this order and any companion paid in
    the same session (a "both" purchase is two orders, one payment)."""
    orders = [order]
    if order.stripe_checkout_session_id:
        orders += list(
            db.scalars(
                select(GiftOrder).where(
                    GiftOrder.stripe_checkout_session_id == order.stripe_checkout_session_id,
                    GiftOrder.id != order.id,
                ).order_by(GiftOrder.created_at)
            )
        )
    return [receipt_line(db, o, birth) for o in orders]


def my_orders(db: Session, *, user_id: uuid.UUID) -> list[dict]:
    """Everything this person has bought, newest first, across every page —
    each line the receipt's shape plus which page it was for. Abandoned
    checkouts (still pending after their Stripe session expired) aren't
    orders and aren't shown."""
    rows = db.execute(
        select(GiftOrder, Birth)
        .join(Birth, Birth.id == GiftOrder.birth_id)
        .where(
            GiftOrder.purchased_by_user_id == user_id,
            GiftOrder.status.in_(["paid", "refunded"]),
        )
        .order_by(GiftOrder.created_at.desc())
    ).all()
    return [
        {**receipt_line(db, o, b), "slug": b.slug, "child_name": b.child_name}
        for o, b in rows
    ]


def backfill_payment_fees(db: Session, stripe, *, limit: int = 20) -> int:
    """Stripe's balance transaction can trail the payment by a few seconds,
    so the fee is sometimes not there when the order is confirmed. The
    worker calls this on its housekeeping tick to fill in the gaps. Returns
    how many orders were filled."""
    if stripe is None:
        return 0
    orders = list(
        db.scalars(
            select(GiftOrder)
            .where(
                GiftOrder.status == "paid",
                GiftOrder.payment_fee_cents.is_(None),
                GiftOrder.stripe_payment_intent_id.isnot(None),
            )
            .order_by(GiftOrder.paid_at.desc())
            .limit(limit)
        )
    )
    by_intent: dict[str, list[GiftOrder]] = {}
    for o in orders:
        by_intent.setdefault(o.stripe_payment_intent_id, []).append(o)
    filled = 0
    for pi, group in by_intent.items():
        # every order this payment covered shares the fee, in proportion
        siblings = list(
            db.scalars(select(GiftOrder).where(GiftOrder.stripe_payment_intent_id == pi, GiftOrder.status == "paid"))
        )
        fee = stripe.payment_fee_cents(pi)
        if fee is None:
            continue
        record_payment_fees(db, orders=siblings, fee_cents=fee)
        filled += len(group)
    return filled


def partner_external_id(order_id: uuid.UUID) -> str:
    """Our order id as the partner will accept it. Printful caps external
    ids at 32 characters: the bare hex of the UUID fits exactly, and the
    hyphenated form — 36 — was rejected with "Invalid External ID" on the
    very first real order (2026-09-03)."""
    return order_id.hex


def submit_shipment(shipment_id: uuid.UUID) -> None:
    """Submit one shipment to the fulfillment partner as a (default: draft)
    order. Runs as a BackgroundTask after the response, so it owns its own
    DB session; never raises. The none→submitting CAS means a duplicate
    schedule or a concurrent retry can never double-POST the partner."""
    db = SessionLocal()
    try:
        claimed = db.execute(
            update(GiftShipment)
            .where(
                GiftShipment.id == shipment_id,
                GiftShipment.fulfillment_status.in_(["none", "failed"]),
            )
            .values(fulfillment_status="submitting", failure_reason=None)
        )
        db.commit()
        if claimed.rowcount == 0:
            return  # someone else is on it (or it's already submitted)

        shipment = db.get(GiftShipment, shipment_id)
        order = db.get(GiftOrder, shipment.gift_order_id)
        item = db.get(GiftCatalogItem, order.gift_catalog_item_id)
        rendering = db.get(GiftRendering, order.gift_rendering_id)

        def fail(reason: str) -> None:
            # a paid order that will not ship is the one failure that must
            # never be quiet: the row records it, and so does the log
            logger.error("gift shipment %s failed: %s", shipment_id, reason)
            shipment.fulfillment_status = "failed"
            shipment.failure_reason = reason[:500]
            db.commit()

        adapter = fulfillment.get_adapter()
        if adapter is None:
            fail("no fulfillment partner configured")
            return
        if shipment.address is None:
            fail("missing address")
            return
        # What the buyer actually picked in the editor. Before this the order
        # always took the kind's default, so someone could approve a mockup of
        # a black 15oz mug and be shipped a white 11oz.
        product = fulfillment_products.for_rendering(
            getattr(rendering, "product_key", None), item.product_kind
        )
        if product is None:
            fail(f"no fulfillment product mapped for {item.product_kind}")
            return
        if rendering is None or not rendering.artwork_s3_key:
            fail("missing artwork")
            return

        recipient = gift_shipping.to_recipient(shipment.address)
        try:
            # a book's print files are made now, not on every design save
            pages = gifts_repo.ensure_print_pages(db, rendering)
            if pages:
                # a many-file design: the cover and every page, each to its
                # placement — the partner assembles the book from them
                files = [
                    {"type": page_key, "url": signed_artwork_url(rendering.id, expires_in=_ORDER_FILE_TTL_SECONDS, page=page_key)}
                    for page_key in pages
                ]
            else:
                files = [{"url": signed_artwork_url(rendering.id, expires_in=_ORDER_FILE_TTL_SECONDS)}]
            result = adapter.create_order(
                recipient=recipient,
                items=[
                    {
                        "variant_id": product.variant_id,
                        "quantity": 1,
                        "files": files,
                    }
                ],
                external_id=partner_external_id(order.id),
                confirm=_printful_confirm_enabled(),
                gift=(
                    {"subject": "A gift for you", "message": order.gift_message}
                    if order.gift_message
                    else None
                ),
            )
            shipment.printful_order_id = result.order_id
            shipment.fulfillment_status = "submitted"
            if result.costs:
                shipment.product_cost_cents = result.costs.get("product")
                shipment.shipping_cost_cents = result.costs.get("shipping")
                shipment.tax_cost_cents = result.costs.get("tax")
                shipment.total_cost_cents = result.costs.get("total")
                shipment.costs_recorded_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:  # OrderError or any transport/storage error
            db.rollback()
            logger.error("gift shipment %s failed: %s", shipment_id, exc, exc_info=True)
            shipment = db.get(GiftShipment, shipment_id)
            if shipment is not None:
                shipment.fulfillment_status = "failed"
                shipment.failure_reason = str(exc)[:500]
                db.commit()
    finally:
        db.close()
