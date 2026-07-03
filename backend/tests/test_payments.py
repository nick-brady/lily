"""Stripe unlock tests — signature verification, the REST client against
mocked transports, idempotent fulfillment branches, and the route guards.
All DB-free (conftest.py); the real-money paths are exercised manually in
Stripe test mode per the PR checklist."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

import payments
from payments import (
    StripeClient,
    StripeError,
    get_stripe,
    unlock_price_cents,
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


# ── checkout session creation ─────────────────────────────────────────────


def test_create_checkout_session_form_fields():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["auth"] = req.headers.get("authorization")
        seen["form"] = parse_qs(req.read().decode())
        return httpx.Response(
            200, json={"id": "cs_test_1", "url": "https://checkout.stripe.com/x"}
        )

    c = StripeClient(secret_key="sk_test_x", client=_client(handler))
    session = c.create_checkout_session(
        birth_id="b-1",
        user_id="u-1",
        slug="lily-wren",
        child_name="Lily",
        amount_cents=1200,
    )
    assert session["url"].startswith("https://checkout.stripe.com")
    assert seen["path"] == "/v1/checkout/sessions"
    assert seen["auth"] == "Bearer sk_test_x"
    form = seen["form"]
    assert form["mode"] == ["payment"]
    assert form["line_items[0][price_data][unit_amount]"] == ["1200"]
    assert form["metadata[kind]"] == ["family_unlock"]
    assert form["metadata[birth_id]"] == ["b-1"]
    assert form["payment_intent_data[metadata][kind]"] == ["family_unlock"]
    # Stripe's template placeholder must arrive literally
    assert "{CHECKOUT_SESSION_ID}" in form["success_url"][0]
    assert "/b/lily-wren" in form["cancel_url"][0]


def test_retrieve_session_unknown_is_none():
    c = StripeClient(
        secret_key="sk",
        client=_client(lambda r: httpx.Response(404, json={"error": {}})),
    )
    assert c.retrieve_checkout_session("cs_bogus") is None


# ── refunds ───────────────────────────────────────────────────────────────


def test_refund_sends_idempotency_key():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["idem"] = req.headers.get("idempotency-key")
        seen["form"] = parse_qs(req.read().decode())
        return httpx.Response(200, json={"id": "re_1"})

    StripeClient(secret_key="sk", client=_client(handler)).create_refund(
        payment_intent_id="pi_x"
    )
    assert seen["idem"] == "unlock-refund-pi_x"
    assert seen["form"]["payment_intent"] == ["pi_x"]


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


def test_unlock_price_default_and_override(monkeypatch):
    monkeypatch.delenv("UNLOCK_PRICE_CENTS", raising=False)
    assert unlock_price_cents() == 1200
    monkeypatch.setenv("UNLOCK_PRICE_CENTS", "1500")
    assert unlock_price_cents() == 1500


# ── fulfill_purchase branches ─────────────────────────────────────────────


class _FakeSession:
    """Enough of a Session for fulfill_purchase: get() returns the birth,
    flush() optionally raises IntegrityError, scalar() returns the
    configured winner row."""

    def __init__(self, birth, *, conflict=False, existing=None):
        self._birth = birth
        self._conflict = conflict
        self._existing = existing
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, _model, _pk):
        return self._birth

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        if self._conflict:
            raise IntegrityError("dup", None, Exception("unique"))

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def scalar(self, _stmt):
        return self._existing


def _birth(unlocked=False):
    return SimpleNamespace(
        id=uuid.uuid4(),
        is_unlocked=unlocked,
        unlocked_at=None,
        unlocked_by_user_id=None,
    )


def _fulfill(db, **kw):
    from repositories import unlocks as unlocks_repo

    defaults = dict(
        birth_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        payment_intent_id="pi_win",
        checkout_session_id="cs_1",
        amount_cents=1200,
        currency="usd",
    )
    defaults.update(kw)
    return unlocks_repo.fulfill_purchase(db, **defaults)


def test_fulfill_winner_flips_flags_and_commits():
    birth = _birth()
    db = _FakeSession(birth)
    outcome, returned = _fulfill(db)
    assert outcome == "unlocked" and returned is birth
    assert birth.is_unlocked is True
    assert birth.unlocked_at is not None
    assert db.commits == 1 and len(db.added) == 1


def test_fulfill_duplicate_same_intent_is_noop():
    birth = _birth(unlocked=True)
    winner = SimpleNamespace(stripe_payment_intent_id="pi_win")
    db = _FakeSession(birth, conflict=True, existing=winner)
    outcome, _ = _fulfill(db, payment_intent_id="pi_win")
    assert outcome == "already_same_intent"
    assert db.rollbacks == 1 and db.commits == 0


def test_fulfill_losing_intent_signals_refund_without_writes():
    birth = _birth(unlocked=True)
    winner = SimpleNamespace(stripe_payment_intent_id="pi_win")
    db = _FakeSession(birth, conflict=True, existing=winner)
    outcome, _ = _fulfill(db, payment_intent_id="pi_loser")
    assert outcome == "already_other_intent"
    assert db.commits == 0


# ── orchestrator ──────────────────────────────────────────────────────────


def _session_obj(birth_id, pi="pi_1"):
    return {
        "id": "cs_1",
        "payment_intent": pi,
        "amount_total": 1200,
        "currency": "usd",
        "payment_status": "paid",
        "metadata": {
            "kind": "family_unlock",
            "birth_id": str(birth_id),
            "user_id": str(uuid.uuid4()),
        },
    }


def test_orchestrator_publishes_only_when_unlocked(monkeypatch):
    import main

    birth = _birth()
    published = []

    monkeypatch.setattr(
        main.unlocks_repo, "fulfill_purchase", lambda db, **kw: ("unlocked", birth)
    )

    async def fake_publish(birth_id, b):
        published.append(birth_id)

    monkeypatch.setattr(main, "publish_birth_update", fake_publish)
    stripe = SimpleNamespace(create_refund=lambda **kw: (_ for _ in ()).throw(AssertionError("no refund")))

    status = asyncio.run(
        main._fulfill_unlock_from_session(
            None, stripe, _session_obj(birth.id), raise_on_refund_error=True
        )
    )
    assert status == "unlocked" and published == [birth.id]


def test_orchestrator_refunds_loser_and_respects_raise_flag(monkeypatch):
    import main

    birth = _birth(unlocked=True)
    refunds = []

    monkeypatch.setattr(
        main.unlocks_repo,
        "fulfill_purchase",
        lambda db, **kw: ("already_other_intent", birth),
    )

    async def fake_publish(birth_id, b):
        raise AssertionError("no publish for losers")

    monkeypatch.setattr(main, "publish_birth_update", fake_publish)

    stripe = SimpleNamespace(
        create_refund=lambda *, payment_intent_id: refunds.append(payment_intent_id)
    )
    status = asyncio.run(
        main._fulfill_unlock_from_session(
            None, stripe, _session_obj(birth.id, pi="pi_loser"),
            raise_on_refund_error=True,
        )
    )
    assert status == "already_unlocked" and refunds == ["pi_loser"]

    def failing_refund(*, payment_intent_id):
        raise payments.StripeError("boom")

    stripe_failing = SimpleNamespace(create_refund=failing_refund)
    # webhook path: bubbles (Stripe redelivery is the retry loop)
    with pytest.raises(payments.StripeError):
        asyncio.run(
            main._fulfill_unlock_from_session(
                None, stripe_failing, _session_obj(birth.id, pi="pi_l2"),
                raise_on_refund_error=True,
            )
        )
    # confirm path: swallowed
    status = asyncio.run(
        main._fulfill_unlock_from_session(
            None, stripe_failing, _session_obj(birth.id, pi="pi_l3"),
            raise_on_refund_error=False,
        )
    )
    assert status == "already_unlocked"


# ── webhook route ─────────────────────────────────────────────────────────


@pytest.fixture
def client_app():
    from fastapi.testclient import TestClient
    import main

    return TestClient(main.app), main


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
    client, main_mod = client_app
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    called = []

    async def fake_fulfill(db, stripe, obj, *, raise_on_refund_error):
        called.append(obj)

    monkeypatch.setattr(main_mod, "_fulfill_unlock_from_session", fake_fulfill)

    body = json.dumps({"type": "invoice.paid"}).encode()
    r = client.post(
        "/webhooks/stripe", content=body, headers={"stripe-signature": _sign(body)}
    )
    assert r.status_code == 200 and called == []

    # right type, wrong kind → still ignored
    body = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"kind": "gift_order"}, "payment_status": "paid"}},
        }
    ).encode()
    r = client.post(
        "/webhooks/stripe", content=body, headers={"stripe-signature": _sign(body)}
    )
    assert r.status_code == 200 and called == []


def test_webhook_fulfills_signed_unlock_event(client_app, monkeypatch):
    client, main_mod = client_app
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    called = []

    async def fake_fulfill(db, stripe, obj, *, raise_on_refund_error):
        called.append((obj["id"], raise_on_refund_error))
        return "unlocked"

    monkeypatch.setattr(main_mod, "_fulfill_unlock_from_session", fake_fulfill)

    obj = _session_obj(uuid.uuid4())
    body = json.dumps(
        {"type": "checkout.session.completed", "data": {"object": obj}}
    ).encode()
    r = client.post(
        "/webhooks/stripe", content=body, headers={"stripe-signature": _sign(body)}
    )
    assert r.status_code == 200
    assert called == [("cs_1", True)]
