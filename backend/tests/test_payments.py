"""Stripe plumbing tests — signature verification, the REST client against
mocked transports, and the webhook route guards. All DB-free (conftest.py);
the real-money paths are exercised manually in Stripe test mode per the PR
checklist. Gift checkout/fulfillment specifics live in test_gift_orders.py."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import httpx
import pytest

from payments import (
    StripeClient,
    StripeError,
    get_stripe,
    verify_stripe_signature,
)

_SECRET = "whsec_testsecret"


def _sign(payload: bytes, secret: str = _SECRET, t: int | None = None) -> str:
    ts = t if t is not None else int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256)
    return f"t={ts},v1={mac.hexdigest()}"


def _client(handler):
    return httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.stripe.com"
    )


# ── signature verification ────────────────────────────────────────────────


def test_signature_valid():
    body = b'{"ok": true}'
    assert verify_stripe_signature(body, _sign(body), _SECRET)


def test_signature_wrong_secret_fails():
    body = b"{}"
    assert not verify_stripe_signature(body, _sign(body, "whsec_other"), _SECRET)


def test_signature_tampered_body_fails():
    header = _sign(b'{"amount": 1200}')
    assert not verify_stripe_signature(b'{"amount": 9999}', header, _SECRET)


def test_signature_stale_timestamp_fails():
    body = b"{}"
    old = int(time.time()) - 3600
    header = _sign(body, t=old)
    assert not verify_stripe_signature(body, header, _SECRET)
    # but fine when "now" is injected near the signing time
    assert verify_stripe_signature(body, header, _SECRET, now=old + 10)


def test_signature_multiple_v1_one_valid():
    body = b"{}"
    ts = int(time.time())
    good = _sign(body, t=ts).split("v1=")[1]
    header = f"t={ts},v1=deadbeef,v1={good}"
    assert verify_stripe_signature(body, header, _SECRET)


def test_signature_malformed_or_missing():
    assert not verify_stripe_signature(b"{}", None, _SECRET)
    assert not verify_stripe_signature(b"{}", "v1=abc", _SECRET)  # no t
    assert not verify_stripe_signature(b"{}", "t=notanumber,v1=abc", _SECRET)
    assert not verify_stripe_signature(b"{}", _sign(b"{}"), "")


# ── session retrieval ─────────────────────────────────────────────────────


def test_retrieve_session_unknown_is_none():
    c = StripeClient(
        secret_key="sk",
        client=_client(lambda r: httpx.Response(404, json={"error": {}})),
    )
    assert c.retrieve_checkout_session("cs_bogus") is None


# ── refunds ───────────────────────────────────────────────────────────────


def test_refund_already_refunded_is_success():
    c = StripeClient(
        secret_key="sk",
        client=_client(
            lambda r: httpx.Response(
                400, json={"error": {"code": "charge_already_refunded"}}
            )
        ),
    )
    c.create_refund(payment_intent_id="pi_x")  # no raise


def test_refund_other_error_raises():
    c = StripeClient(
        secret_key="sk",
        client=_client(
            lambda r: httpx.Response(400, json={"error": {"code": "nope"}})
        ),
    )
    with pytest.raises(StripeError):
        c.create_refund(payment_intent_id="pi_x")


# ── env gating ────────────────────────────────────────────────────────────


def test_get_stripe_gated_on_env(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    assert get_stripe() is None
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    assert isinstance(get_stripe(), StripeClient)


# ── webhook route ─────────────────────────────────────────────────────────


@pytest.fixture
def client_app():
    from fastapi.testclient import TestClient
    import gift_fulfillment
    import main

    return TestClient(main.app), gift_fulfillment


def test_webhook_unconfigured_is_503(client_app, monkeypatch):
    client, _ = client_app
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    assert client.post("/webhooks/stripe", content=b"{}").status_code == 503


def test_webhook_bad_signature_is_400(client_app, monkeypatch):
    client, _ = client_app
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    body = json.dumps({"type": "checkout.session.completed"}).encode()
    r = client.post(
        "/webhooks/stripe",
        content=b'{"tampered": true}',
        headers={"stripe-signature": _sign(body)},
    )
    assert r.status_code == 400


def test_webhook_ignores_foreign_events(client_app, monkeypatch):
    client, fulfillment_mod = client_app
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    called = []

    async def fake_fulfill(db, stripe, obj, tasks, *, raise_on_refund_error):
        called.append(obj)

    monkeypatch.setattr(fulfillment_mod, "fulfill_gift_from_session", fake_fulfill)

    body = json.dumps({"type": "invoice.paid"}).encode()
    r = client.post(
        "/webhooks/stripe", content=body, headers={"stripe-signature": _sign(body)}
    )
    assert r.status_code == 200 and called == []

    # right type, wrong kind → still ignored (family_unlock is a retired
    # product; a straggling redelivery must be acknowledged, not fulfilled)
    for kind in ("storage_gift", "family_unlock"):
        body = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {"object": {"metadata": {"kind": kind}, "payment_status": "paid"}},
            }
        ).encode()
        r = client.post(
            "/webhooks/stripe", content=body, headers={"stripe-signature": _sign(body)}
        )
        assert r.status_code == 200 and called == []


def test_webhook_fulfills_signed_gift_event(client_app, monkeypatch):
    client, fulfillment_mod = client_app
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    called = []

    async def fake_fulfill(db, stripe, obj, tasks, *, raise_on_refund_error):
        called.append((obj["id"], raise_on_refund_error))
        return "fulfilled"

    monkeypatch.setattr(fulfillment_mod, "fulfill_gift_from_session", fake_fulfill)

    obj = {
        "id": "cs_1",
        "payment_intent": "pi_1",
        "payment_status": "paid",
        "metadata": {"kind": "gift_order", "order_id": str(uuid.uuid4())},
    }
    body = json.dumps(
        {"type": "checkout.session.completed", "data": {"object": obj}}
    ).encode()
    r = client.post(
        "/webhooks/stripe", content=body, headers={"stripe-signature": _sign(body)}
    )
    assert r.status_code == 200
    assert called == [("cs_1", True)]


# ── the processing fee ────────────────────────────────────────────────────


def test_payment_fee_comes_from_the_balance_transaction():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        return httpx.Response(200, json={
            "id": "pi_1", "latest_charge": {"id": "ch_1", "balance_transaction": {
                "amount": 2469, "fee": 102, "net": 2367}}})

    c = StripeClient(secret_key="sk", client=_client(handler))
    assert c.payment_fee_cents("pi_1") == 102
    assert "expand" in seen["url"] and "balance_transaction" in seen["url"]


def test_payment_fee_is_none_until_the_charge_settles():
    c = StripeClient(
        secret_key="sk",
        client=_client(lambda r: httpx.Response(200, json={"id": "pi_1", "latest_charge": "ch_1"})),
    )
    assert c.payment_fee_cents("pi_1") is None
