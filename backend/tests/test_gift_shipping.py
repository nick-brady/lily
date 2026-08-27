"""Postage: quoted from the partner, charged as its own line, recorded per
order."""
from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest

import gift_shipping
from fulfillment import products as fulfillment_products
from fulfillment.base import RateError
from fulfillment.printful import PrintfulAdapter
from payments import StripeClient


def _adapter(handler):
    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.printful.com"
    )
    return PrintfulAdapter(api_key="test-key", client=client, mockup_interval_seconds=0)


ADDRESS = {
    "name": "Aunt May",
    "line1": "20 Ingram St",
    "city": "Forest Hills",
    "state": "NY",
    "postal_code": "11375",
    "country": "US",
}


def test_the_cheapest_service_is_the_one_we_charge_for():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/shipping/rates"
        seen["body"] = json.loads(req.read())
        return httpx.Response(
            200,
            json={
                "result": [
                    {"id": "PRINTFUL_FAST", "name": "Express", "rate": "14.50",
                     "minDeliveryDays": 1, "maxDeliveryDays": 2},
                    {"id": "STANDARD", "name": "Flat Rate", "rate": "4.99",
                     "minDeliveryDays": 3, "maxDeliveryDays": 5},
                ]
            },
        )

    rate = _adapter(handler).shipping_rate(
        recipient=gift_shipping.to_recipient(ADDRESS),
        items=[{"variant_id": 1320, "quantity": 1}],
    )
    assert (rate.cents, rate.name, rate.min_days, rate.max_days) == (499, "Flat Rate", 3, 5)
    # the partner's address shape, not ours
    assert seen["body"]["recipient"]["state_code"] == "NY"
    assert seen["body"]["recipient"]["zip"] == "11375"
    assert seen["body"]["items"] == [{"variant_id": 1320, "quantity": 1}]


def test_no_service_offered_is_an_error_not_a_free_parcel():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": []})

    with pytest.raises(RateError):
        _adapter(handler).shipping_rate(
            recipient=gift_shipping.to_recipient(ADDRESS), items=[{"variant_id": 1}]
        )


def test_quote_uses_the_partner_when_it_answers(monkeypatch):
    class Adapter:
        def shipping_rate(self, *, recipient, items):
            from fulfillment.base import ShippingRate

            return ShippingRate(cents=1050, name="Flat Rate", min_days=3, max_days=6)

    monkeypatch.setattr(gift_shipping.fulfillment, "get_adapter", lambda: Adapter())
    q = gift_shipping.quote(fulfillment_products.SHORTLIST["frame_black_12x16"], ADDRESS)
    assert (q.cents, q.estimated, q.service, q.max_days) == (1050, False, "Flat Rate", 6)


def test_quote_falls_back_to_the_estimate_and_says_so(monkeypatch):
    class Adapter:
        def shipping_rate(self, *, recipient, items):
            raise RateError("down")

    monkeypatch.setattr(gift_shipping.fulfillment, "get_adapter", lambda: Adapter())
    frame = fulfillment_products.SHORTLIST["frame_black_12x16"]
    q = gift_shipping.quote(frame, ADDRESS)
    assert q.estimated and q.cents == frame.shipping_estimate_cents == 1050

    # and with no partner at all (dev), the same stand-in
    monkeypatch.setattr(gift_shipping.fulfillment, "get_adapter", lambda: None)
    q = gift_shipping.quote(fulfillment_products.SHORTLIST["book_8x8_matte"], ADDRESS)
    assert q.estimated and q.cents == 750


def test_stripe_gets_postage_as_its_own_line():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["form"] = parse_qs(req.read().decode())
        return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout/x"})

    client = StripeClient(
        secret_key="sk_test",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.stripe.com"),
    )
    client.create_gift_checkout_session(
        order_id="o-1", birth_id="b-1", user_id="u-1", slug="lily-wren",
        product_name="Birth Story Mug", amount_cents=1800, collect_shipping=False,
        allowed_countries=["US"], quantity=2, extra_order_id="o-2",
        shipping_cents=998, shipping_label="Shipping (2 parcels)",
    )
    form = seen["form"]
    assert form["line_items[0][quantity]"] == ["2"]
    assert form["line_items[0][price_data][unit_amount]"] == ["1800"]
    assert form["line_items[1][quantity]"] == ["1"]
    assert form["line_items[1][price_data][unit_amount]"] == ["998"]
    assert form["line_items[1][price_data][product_data][name]"] == ["Shipping (2 parcels)"]


def test_no_postage_means_no_shipping_line():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["form"] = parse_qs(req.read().decode())
        return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout/x"})

    client = StripeClient(
        secret_key="sk_test",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.stripe.com"),
    )
    client.create_gift_checkout_session(
        order_id="o-1", birth_id="b-1", user_id="u-1", slug="lily-wren",
        product_name="Birth Story Mug", amount_cents=1800, collect_shipping=False,
        allowed_countries=["US"],
    )
    assert not any(k.startswith("line_items[1]") for k in seen["form"])
