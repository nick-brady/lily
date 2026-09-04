"""Post-payment fulfillment for gift checkouts.

The single funnel shared by the Stripe webhook and the redirect-confirm
route — kept out of the route layer so the money-moving logic lives in
one importable, testable place.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

import gift_receipt_email
import payments
from models import Birth, GiftCatalogItem, GiftKind
from repositories import gift_orders as gift_orders_repo

logger = logging.getLogger(__name__)


async def fulfill_gift_from_session(
    db: Session,
    stripe: payments.StripeClient,
    session_obj: dict,
    background_tasks: BackgroundTasks,
    *,
    raise_on_refund_error: bool,
) -> str:
    """Fulfill a paid gift checkout — the single funnel for the webhook and
    the redirect-confirm. The CAS in mark_paid guarantees exactly one caller
    creates the shipment and schedules the Printful submission; a losing
    family-claim payment is refunded (webhook path re-raises refund errors
    so Stripe redelivery retries; confirm path swallows) and recorded as
    refunded only after the refund succeeds.

    Physical items ship; storage gifts have nothing to ship — they just
    extend the birth's paid-through date."""
    metadata = session_obj.get("metadata") or {}
    order_ids = [uuid.UUID(metadata["order_id"])]
    if metadata.get("order_id_2"):  # a "both" purchase — two copies, one session
        order_ids.append(uuid.UUID(metadata["order_id_2"]))
    statuses = []
    paid_orders = []
    for order_id in order_ids:
        # each order records its own share of the charge, not the session total
        outcome, order = gift_orders_repo.mark_paid(
            db,
            order_id=order_id,
            session_obj=session_obj,
            orders_in_session=len(order_ids),
        )
        if outcome == "paid":
            paid_orders.append(order)
            birth = db.get(Birth, order.birth_id)
            item = db.get(GiftCatalogItem, order.gift_catalog_item_id)
            if item.kind == GiftKind.storage_gift:
                gift_orders_repo.grant_storage_gift(
                    db, birth=birth, storage_years_granted=item.storage_years_granted
                )
                statuses.append("fulfilled")
                continue
            # The order names its own destination, settled at purchase. The
            # two fallbacks are for orders created before it did — a checkout
            # started before that deploy could be paid after it — and nothing
            # written from now on reaches them.
            if order.shipping_address:
                address = dict(order.shipping_address)
            elif order.recipient_kind == "family" and birth.shipping_address:
                address = dict(birth.shipping_address)
            else:
                address = payments.extract_shipping(session_obj)
            shipment = gift_orders_repo.create_shipment(db, order=order, address=address)
            if shipment.fulfillment_status != "failed":
                background_tasks.add_task(gift_orders_repo.submit_shipment, shipment.id)
            statuses.append("fulfilled")
            continue
        if outcome == "claim_lost":
            pi = session_obj.get("payment_intent")
            if pi:
                try:
                    # single-order session: refund the whole payment (legacy
                    # key shape). Multi-order: refund only this copy's share,
                    # keyed per order so it can't collide with a full refund.
                    if len(order_ids) == 1:
                        stripe.create_refund(payment_intent_id=pi, kind="gift")
                    else:
                        stripe.create_refund(
                            payment_intent_id=pi,
                            kind="gift",
                            amount_cents=order.amount_cents,
                            key_suffix=f"-{order_id}",
                        )
                except payments.StripeError:
                    if raise_on_refund_error:
                        raise
                    logger.error(
                        "gift refund failed for %s; webhook redelivery will retry",
                        pi,
                        exc_info=True,
                    )
                    statuses.append("refunded")
                    continue
            gift_orders_repo.mark_refunded(db, order_id=order_id)
            statuses.append("refunded")
            continue
        if outcome == "already_refunded":
            statuses.append("refunded")
        else:
            statuses.append("already_processed")

    if paid_orders:
        _record_fee(db, stripe, session_obj, paid_orders)
        # the buyer's receipt, after the response; a claim on the orders
        # means only one of the webhook and the confirm path sends it
        background_tasks.add_task(
            gift_receipt_email.send_for_orders, [o.id for o in paid_orders], session_obj
        )

    # the session-level status: any fulfillment wins, then any refund
    for status in ("fulfilled", "refunded"):
        if status in statuses:
            return status
    return "already_processed"



def _record_fee(db: Session, stripe, session_obj: dict, orders: list) -> None:
    """What Stripe kept, written onto the orders this payment covered. Best
    effort: the money has moved either way, and a fee we couldn't read is a
    gap in the dashboard, not a reason to fail fulfillment."""
    pi = session_obj.get("payment_intent")
    lookup = getattr(stripe, "payment_fee_cents", None)
    if not pi or lookup is None:
        return
    try:
        fee = lookup(pi)
    except Exception:  # noqa: BLE001 - see docstring
        logger.warning("payment fee not recorded for %s", pi, exc_info=True)
        return
    if fee is None:
        logger.warning("payment fee not available yet for %s", pi)
        return
    gift_orders_repo.record_payment_fees(db, orders=orders, fee_cents=fee)
