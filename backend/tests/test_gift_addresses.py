"""Where a gift goes, now that the buyer names it instead of Stripe.

Structure checks, Google's advisory opinion, and the resolution order
fulfillment uses to decide which address a parcel actually gets.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import pytest

import address_validation as av


_GOOD = {
    "name": "Nora Brady",
    "line1": "12 Rue Street",
    "line2": None,
    "city": "Boston",
    "state": "MA",
    "postal_code": "02118",
    "country": "US",
}


# ── structure: the part that refuses ──────────────────────────────────────


def test_a_complete_us_address_passes():
    av.check_structure(_GOOD, allowed_countries=["US"])


@pytest.mark.parametrize("missing", ["name", "line1", "city", "postal_code"])
def test_the_parcel_needs_somewhere_to_go(missing):
    with pytest.raises(av.AddressError):
        av.check_structure({**_GOOD, missing: ""}, allowed_countries=["US"])


def test_us_and_canada_need_a_state_because_printful_does():
    with pytest.raises(av.AddressError):
        av.check_structure({**_GOOD, "state": ""}, allowed_countries=["US"])
    with pytest.raises(av.AddressError):
        av.check_structure(
            {**_GOOD, "country": "CA", "state": "", "postal_code": "M5V"},
            allowed_countries=["CA"],
        )


def test_elsewhere_a_state_is_genuinely_optional():
    av.check_structure(
        {**_GOOD, "country": "GB", "state": "", "postal_code": "SW1A 1AA"},
        allowed_countries=["GB"],
    )


def test_we_only_ship_where_we_ship():
    with pytest.raises(av.AddressError) as exc:
        av.check_structure({**_GOOD, "country": "FR"}, allowed_countries=["US"])
    assert "US" in str(exc.value)


# ── Google: the part that only advises ────────────────────────────────────


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _verdict_response(*, complete=True, unconfirmed=False, line1="12 Rue Street"):
    def handler(_req):
        return httpx.Response(
            200,
            json={
                "result": {
                    "verdict": {
                        "addressComplete": complete,
                        "hasUnconfirmedComponents": unconfirmed,
                    },
                    "address": {
                        "postalAddress": {
                            "addressLines": [line1],
                            "locality": "Boston",
                            "administrativeArea": "MA",
                            "postalCode": "02118",
                            "regionCode": "US",
                        }
                    },
                }
            },
        )

    return handler


def test_without_a_key_it_simply_doesnt_check(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    assert av.review(_GOOD) == {"verdict": "unchecked", "suggestion": None}


def test_a_recognised_address_is_confirmed(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "k")
    out = av.review(_GOOD, client=_client(_verdict_response()))
    assert out["verdict"] == "confirmed"


def test_a_different_spelling_comes_back_as_a_suggestion(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "k")
    out = av.review(_GOOD, client=_client(_verdict_response(line1="12 Rue St")))
    assert out["verdict"] == "corrected"
    assert out["suggestion"]["line1"] == "12 Rue St"
    # the person is ours to name, not Google's
    assert out["suggestion"]["name"] == "Nora Brady"


def test_case_and_spacing_alone_are_not_a_correction(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "k")
    out = av.review(
        {**_GOOD, "line1": "12  rue street"},
        client=_client(_verdict_response(line1="12 Rue Street")),
    )
    assert out["verdict"] == "confirmed"


def test_an_address_google_cant_place_is_flagged_not_refused(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "k")
    out = av.review(_GOOD, client=_client(_verdict_response(unconfirmed=True)))
    assert out["verdict"] == "unconfirmed"


def test_google_being_down_never_blocks_a_sale(monkeypatch):
    """A new build with no postal record, a rural route, an outage at Google —
    none of them are reasons someone can't buy a mug."""
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "k")

    def broken(_req):
        return httpx.Response(500, json={"error": "nope"})

    assert av.review(_GOOD, client=_client(broken)) == {
        "verdict": "unchecked",
        "suggestion": None,
    }


# ── which address a parcel actually gets ──────────────────────────────────


def _resolve(order, birth, session_obj):
    """The resolution order in gift_fulfillment, isolated."""
    import payments

    if order.shipping_address:
        return dict(order.shipping_address)
    if order.recipient_kind == "family" and birth.shipping_address:
        return dict(birth.shipping_address)
    return payments.extract_shipping(session_obj)


def test_what_the_buyer_typed_wins():
    typed = {**_GOOD, "name": "Typed At Checkout"}
    order = SimpleNamespace(shipping_address=typed, recipient_kind="family")
    birth = SimpleNamespace(shipping_address={**_GOOD, "name": "Saved"})
    assert _resolve(order, birth, {})["name"] == "Typed At Checkout"


def test_a_family_copy_carries_the_saved_address_it_was_bought_against():
    """Copied onto the order at purchase, not read at shipping time. The
    payment was for a parcel to a particular place; if the family updates
    their address afterwards, an order already paid for shouldn't quietly
    change destination."""
    order = SimpleNamespace(
        shipping_address={**_GOOD, "name": "Saved At Purchase"},
        recipient_kind="family",
    )
    birth = SimpleNamespace(shipping_address={**_GOOD, "name": "Moved Since"})
    assert _resolve(order, birth, {})["name"] == "Saved At Purchase"


def test_an_order_from_before_the_snapshot_falls_back_to_the_birth():
    """Orders created while the family copy still resolved at shipping time."""
    order = SimpleNamespace(shipping_address=None, recipient_kind="family")
    birth = SimpleNamespace(shipping_address={**_GOOD, "name": "Saved"})
    assert _resolve(order, birth, {})["name"] == "Saved"


def test_a_session_from_before_the_change_still_ships():
    """Checkouts started while Stripe still collected the address were paid
    after we stopped asking it to."""
    order = SimpleNamespace(shipping_address=None, recipient_kind="self")
    birth = SimpleNamespace(shipping_address=None)
    session = {
        "collected_information": {
            "shipping_details": {
                "name": "From Stripe",
                "address": {
                    "line1": "9 Old Way",
                    "city": "Boston",
                    "state": "MA",
                    "postal_code": "02118",
                    "country": "US",
                },
            }
        }
    }
    assert _resolve(order, birth, session)["name"] == "From Stripe"
