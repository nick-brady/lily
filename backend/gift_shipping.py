"""What it costs to post a gift, asked of the partner before anyone pays.

Printful bills us shipping on every parcel, so the buyer pays it as its own
line — quoted live for the address they typed, or, when the partner can't be
asked, the flat stand-in each product carries. The quote is taken once at
checkout and written onto the order; the sheet asks for the same quote as the
address is typed, so the number on the pay button is the number Stripe shows.
"""
from __future__ import annotations

from dataclasses import dataclass

import fulfillment
from fulfillment.base import RateError
from fulfillment.products import ShortlistProduct


@dataclass
class ShippingQuote:
    cents: int
    # True when this is the product's flat stand-in rather than the partner's
    # own number — recorded on the order, because a guess should say it is one.
    estimated: bool
    service: str = "Standard"
    min_days: int | None = None
    max_days: int | None = None


def to_recipient(address: dict) -> dict:
    """Our address shape → the partner's. One place, so the address a rate was
    quoted for and the address the parcel goes to can't be spelled apart."""
    return {
        "name": address.get("name") or "Gift recipient",
        "address1": address.get("line1"),
        "address2": address.get("line2") or "",
        "city": address.get("city"),
        "state_code": address.get("state") or "",
        "country_code": address.get("country") or "US",
        "zip": address.get("postal_code"),
    }


def quote(product: ShortlistProduct, address: dict, *, quantity: int = 1) -> ShippingQuote:
    """The cheapest service to `address` for one parcel of `product`.

    Never raises: a partner outage at the moment of paying is not the buyer's
    problem, so it falls back to the product's estimate and says so."""
    adapter = fulfillment.get_adapter()
    if adapter is not None:
        try:
            rate = adapter.shipping_rate(
                recipient=to_recipient(address),
                items=[{"variant_id": product.variant_id, "quantity": quantity}],
            )
            return ShippingQuote(
                cents=rate.cents,
                estimated=False,
                service=rate.name,
                min_days=rate.min_days,
                max_days=rate.max_days,
            )
        except RateError as exc:
            print(f"shipping quote fell back to the estimate: {exc}", flush=True)
    return ShippingQuote(cents=product.shipping_estimate_cents * quantity, estimated=True)
