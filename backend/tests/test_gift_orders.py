"""Gift checkout tests — the Stripe gift session, shipping extraction across
API-version shapes, the CAS mark_paid transitions, the fulfillment funnel,
webhook dispatch, and the Printful order call. All DB-free."""
from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

import payments
from fulfillment.base import OrderError
from fulfillment.printful import PrintfulAdapter
from models import Birth, GiftCatalogItem, GiftKind
from payments import StripeClient


def _client(handler, base="https://api.stripe.com"):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=base)


# ── gift checkout session ─────────────────────────────────────────────────


def _gift_session_kwargs(**overrides):
    kw = dict(
        order_id="o-1",
        birth_id="b-1",
        user_id="u-1",
        slug="lily-wren",
        product_name="Birth Story Mug",
        amount_cents=1800,
        collect_shipping=True,
        allowed_countries=["US"],
    )
    kw.update(overrides)
    return kw


def test_gift_session_form_fields_with_shipping():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["form"] = parse_qs(req.read().decode())
        return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout/x"})

    c = StripeClient(secret_key="sk", client=_client(handler))
    c.create_gift_checkout_session(**_gift_session_kwargs())
    form = seen["form"]
    assert form["metadata[kind]"] == ["gift_order"]
    assert form["metadata[order_id]"] == ["o-1"]
    assert form["payment_intent_data[metadata][kind]"] == ["gift_order"]
    assert form["line_items[0][price_data][unit_amount]"] == ["1800"]
    assert form["shipping_address_collection[allowed_countries][0]"] == ["US"]
    assert "{CHECKOUT_SESSION_ID}" in form["success_url"][0]
    assert "gift_session=" in form["success_url"][0]


def test_gift_session_both_carries_quantity_and_second_order():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["form"] = parse_qs(req.read().decode())
        return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout/x"})

    c = StripeClient(secret_key="sk", client=_client(handler))
    c.create_gift_checkout_session(
        **_gift_session_kwargs(), quantity=2, extra_order_id="o-2"
    )
    form = seen["form"]
    assert form["line_items[0][quantity]"] == ["2"]
    assert form["metadata[order_id]"] == ["o-1"]
    assert form["metadata[order_id_2]"] == ["o-2"]
    assert form["payment_intent_data[metadata][order_id_2]"] == ["o-2"]


def test_gift_session_omits_shipping_when_saved_address():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["form"] = parse_qs(req.read().decode())
        return httpx.Response(200, json={"id": "cs_1", "url": "u"})

    c = StripeClient(secret_key="sk", client=_client(handler))
    c.create_gift_checkout_session(**_gift_session_kwargs(collect_shipping=False))
    assert not any(k.startswith("shipping_address_collection") for k in seen["form"])


def test_refund_kind_namespaces_idempotency_key():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["idem"] = req.headers.get("idempotency-key")
        seen["form"] = parse_qs(req.read().decode())
        return httpx.Response(200, json={"id": "re_1"})

    c = StripeClient(secret_key="sk", client=_client(handler))
    c.create_refund(payment_intent_id="pi_x", kind="gift")
    assert seen["idem"] == "gift-refund-pi_x"
    assert "amount" not in seen["form"]
    c.create_refund(payment_intent_id="pi_x")  # gift is the default
    assert seen["idem"] == "gift-refund-pi_x"
    # a partial refund (one copy of a "both" purchase) carries the amount
    # and keys per order so it can't dedupe against a full refund
    c.create_refund(
        payment_intent_id="pi_x", amount_cents=1800, key_suffix="-o1"
    )
    assert seen["idem"] == "gift-refund-pi_x-o1"
    assert seen["form"]["amount"] == ["1800"]


# ── shipping extraction across Stripe API versions ────────────────────────

_ADDR = {
    "line1": "123 Fern St",
    "line2": None,
    "city": "Raleigh",
    "state": "NC",
    "postal_code": "27601",
    "country": "US",
}


def test_extract_shipping_new_shape():
    session = {
        "collected_information": {
            "shipping_details": {"name": "Janet W", "address": dict(_ADDR)}
        }
    }
    out = payments.extract_shipping(session)
    assert out["name"] == "Janet W" and out["line1"] == "123 Fern St"
    assert out["state"] == "NC" and out["postal_code"] == "27601"


def test_extract_shipping_legacy_shape():
    session = {"shipping_details": {"name": "Janet W", "address": dict(_ADDR)}}
    assert payments.extract_shipping(session)["city"] == "Raleigh"


def test_extract_shipping_billing_fallback_and_none():
    session = {"customer_details": {"name": "Lisa", "address": dict(_ADDR)}}
    assert payments.extract_shipping(session)["name"] == "Lisa"
    assert payments.extract_shipping({}) is None
    # an address without line1 (billing country-only) is not usable
    assert (
        payments.extract_shipping(
            {"customer_details": {"name": "x", "address": {"country": "US"}}}
        )
        is None
    )


# ── mark_paid CAS transitions ─────────────────────────────────────────────


class _Result:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class _FakeOrderSession:
    """Session stub for mark_paid: get() returns the order, execute()
    returns a configurable rowcount or raises IntegrityError."""

    def __init__(self, order, *, rowcount=1, integrity=False):
        self._order = order
        self._rowcount = rowcount
        self._integrity = integrity
        self.commits = 0
        self.rollbacks = 0

    def get(self, _model, _pk):
        return self._order

    def execute(self, stmt):
        if self._integrity:
            raise IntegrityError("claim", None, Exception("unique"))
        # what the UPDATE would have written, for tests about the amounts
        params = getattr(stmt, "_values", None) or {}
        self.values = {getattr(k, "key", str(k)): v.value if hasattr(v, "value") else v for k, v in params.items()}
        return _Result(self._rowcount)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _obj):
        pass


def _order(status="pending", session_id=None, shipping_address=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        birth_id=uuid.uuid4(),
        gift_catalog_item_id=uuid.uuid4(),
        status=status,
        recipient_kind="family",
        stripe_checkout_session_id=session_id,
        # Where the buyer said this copy goes. None falls back to the
        # parents' saved address, then to whatever Stripe collected.
        shipping_address=shipping_address,
        amount_cents=1800,
    )


def _session_obj(order, pi="pi_1", session_id="cs_1"):
    return {
        "id": session_id,
        "payment_intent": pi,
        "amount_total": 1800,
        "payment_status": "paid",
        "metadata": {"kind": "gift_order", "order_id": str(order.id), "birth_id": str(order.birth_id)},
    }


def test_mark_paid_winner():
    from repositories import gift_orders as repo

    order = _order(session_id="cs_1")
    db = _FakeOrderSession(order, rowcount=1)
    outcome, _ = repo.mark_paid(db, order_id=order.id, session_obj=_session_obj(order))
    assert outcome == "paid" and db.commits == 1


def test_mark_paid_in_a_shared_session_records_this_copys_own_price():
    from repositories import gift_orders as repo

    order = _order(session_id="cs_both")
    order.amount_cents = 2499  # $18 mug + its own postage
    db = _FakeOrderSession(order, rowcount=1)
    session_obj = _session_obj(order, session_id="cs_both")
    session_obj["amount_total"] = 4599  # the other copy's postage differed
    outcome, _ = repo.mark_paid(
        db, order_id=order.id, session_obj=session_obj, orders_in_session=2
    )
    assert outcome == "paid"
    assert db.values["amount_cents"] == 2499


def test_mark_paid_duplicate_is_noop():
    from repositories import gift_orders as repo

    order = _order(status="paid", session_id="cs_1")
    db = _FakeOrderSession(order, rowcount=0)
    outcome, _ = repo.mark_paid(db, order_id=order.id, session_obj=_session_obj(order))
    assert outcome == "already_paid"


def test_mark_paid_refunded_duplicate():
    from repositories import gift_orders as repo

    order = _order(status="refunded", session_id="cs_1")
    db = _FakeOrderSession(order, rowcount=0)
    outcome, _ = repo.mark_paid(db, order_id=order.id, session_obj=_session_obj(order))
    assert outcome == "already_refunded"


def test_mark_paid_claim_lost():
    from repositories import gift_orders as repo

    order = _order(session_id="cs_1")
    db = _FakeOrderSession(order, integrity=True)
    outcome, _ = repo.mark_paid(db, order_id=order.id, session_obj=_session_obj(order))
    assert outcome == "claim_lost" and db.rollbacks == 1


def test_mark_paid_null_session_backfills_and_mismatch_rejects():
    from repositories import gift_orders as repo

    # NULL recorded session id → accept (backfill happens in the UPDATE)
    order = _order(session_id=None)
    db = _FakeOrderSession(order, rowcount=1)
    outcome, _ = repo.mark_paid(db, order_id=order.id, session_obj=_session_obj(order))
    assert outcome == "paid"

    # different recorded session id → foreign, no transition
    order2 = _order(session_id="cs_other")
    db2 = _FakeOrderSession(order2, rowcount=1)
    outcome, _ = repo.mark_paid(db2, order_id=order2.id, session_obj=_session_obj(order2))
    assert outcome == "already_paid" and db2.commits == 0


# ── the funnel ────────────────────────────────────────────────────────────


class _Tasks:
    def __init__(self):
        self.scheduled = []

    def add_task(self, fn, *args):
        self.scheduled.append((fn, args))


def _dispatching_db(birth, item):
    """A fake session whose get() returns the right fixture per model —
    fulfill_gift_from_session loads both the birth and the catalog
    item to decide physical-vs-storage handling."""
    class _DB:
        def get(self, model, _pk):
            if model is Birth:
                return birth
            if model is GiftCatalogItem:
                return item
            raise AssertionError(f"unexpected model {model}")

    return _DB()


def test_funnel_paid_schedules_exactly_one_submission(monkeypatch):
    import gift_fulfillment

    order = _order(session_id="cs_1")
    shipment = SimpleNamespace(id=uuid.uuid4(), fulfillment_status="none")
    birth = SimpleNamespace(id=order.birth_id, shipping_address={"name": "Fam", "line1": "1 St"})
    item = SimpleNamespace(kind=GiftKind.physical, storage_years_granted=None)

    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo, "mark_paid", lambda db, **kw: ("paid", order)
    )
    created = []
    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo,
        "create_shipment",
        lambda db, **kw: created.append(kw) or shipment,
    )

    tasks = _Tasks()
    status = asyncio.run(
        gift_fulfillment.fulfill_gift_from_session(
            _dispatching_db(birth, item), SimpleNamespace(), _session_obj(order), tasks,
            raise_on_refund_error=True,
        )
    )
    assert status == "fulfilled"
    assert len(tasks.scheduled) == 1
    # family recipient with a saved address uses it
    assert created[0]["address"]["name"] == "Fam"


def test_funnel_paid_storage_gift_grants_storage_no_shipment(monkeypatch):
    import gift_fulfillment

    order = _order(session_id="cs_1")
    birth = SimpleNamespace(id=order.birth_id, shipping_address=None)
    item = SimpleNamespace(kind=GiftKind.storage_gift, storage_years_granted=5)

    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo, "mark_paid", lambda db, **kw: ("paid", order)
    )
    granted = []
    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo,
        "grant_storage_gift",
        lambda db, **kw: granted.append(kw),
    )
    shipment_calls = []
    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo,
        "create_shipment",
        lambda db, **kw: shipment_calls.append(kw),
    )

    tasks = _Tasks()
    status = asyncio.run(
        gift_fulfillment.fulfill_gift_from_session(
            _dispatching_db(birth, item), SimpleNamespace(), _session_obj(order), tasks,
            raise_on_refund_error=True,
        )
    )
    assert status == "fulfilled"
    assert granted == [{"birth": birth, "storage_years_granted": 5}]
    # no shipment for a storage gift — nothing to ship
    assert shipment_calls == []
    assert tasks.scheduled == []


def test_funnel_claim_lost_refunds_then_marks(monkeypatch):
    import gift_fulfillment

    order = _order()
    calls = []
    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo, "mark_paid", lambda db, **kw: ("claim_lost", order)
    )
    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo,
        "mark_refunded",
        lambda db, **kw: calls.append("marked"),
    )
    stripe = SimpleNamespace(
        create_refund=lambda **kw: calls.append(("refund", kw["kind"]))
    )
    tasks = _Tasks()
    status = asyncio.run(
        gift_fulfillment.fulfill_gift_from_session(
            None, stripe, _session_obj(order), tasks, raise_on_refund_error=True
        )
    )
    assert status == "refunded"
    assert calls == [("refund", "gift"), "marked"]  # refund BEFORE marking
    assert tasks.scheduled == []

    # refund failure on webhook path bubbles; order stays un-marked
    calls.clear()

    def failing(**kw):
        raise payments.StripeError("boom")

    stripe_fail = SimpleNamespace(create_refund=failing)
    with pytest.raises(payments.StripeError):
        asyncio.run(
            gift_fulfillment.fulfill_gift_from_session(
                None, stripe_fail, _session_obj(order), _Tasks(),
                raise_on_refund_error=True,
            )
        )
    assert "marked" not in calls


def test_funnel_already_paid_schedules_nothing(monkeypatch):
    import gift_fulfillment

    order = _order(status="paid")
    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo, "mark_paid", lambda db, **kw: ("already_paid", order)
    )
    tasks = _Tasks()
    status = asyncio.run(
        gift_fulfillment.fulfill_gift_from_session(
            None, SimpleNamespace(), _session_obj(order), tasks,
            raise_on_refund_error=True,
        )
    )
    assert status == "already_processed" and tasks.scheduled == []


# ── grant_storage_gift ──────────────────────────────────────────────────────


class _FakeCommitSession:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_funnel_both_orders_fulfill_from_one_session(monkeypatch):
    import gift_fulfillment

    family = _order()
    selfo = _order()
    selfo.recipient_kind = "self"
    orders = {family.id: family, selfo.id: selfo}
    birth = SimpleNamespace(
        id=family.birth_id, shipping_address={"name": "Fam", "line1": "1 St"}
    )
    item = SimpleNamespace(kind=GiftKind.physical, storage_years_granted=None)

    session_obj = _session_obj(family, session_id="cs_both")
    session_obj["amount_total"] = 3600
    session_obj["metadata"]["order_id_2"] = str(selfo.id)
    session_obj["collected_information"] = {
        "shipping_details": {"name": "Buyer", "address": {"line1": "9 Buyer Rd"}}
    }

    seen = []

    def fake_mark_paid(db, *, order_id, session_obj, orders_in_session=1):
        seen.append((order_id, orders_in_session))
        return "paid", orders[order_id]

    monkeypatch.setattr(gift_fulfillment.gift_orders_repo, "mark_paid", fake_mark_paid)
    created = []
    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo,
        "create_shipment",
        lambda db, **kw: created.append(kw)
        or SimpleNamespace(id=uuid.uuid4(), fulfillment_status="none"),
    )

    tasks = _Tasks()
    status = asyncio.run(
        gift_fulfillment.fulfill_gift_from_session(
            _dispatching_db(birth, item), SimpleNamespace(), session_obj, tasks,
            raise_on_refund_error=True,
        )
    )
    assert status == "fulfilled"
    assert len(tasks.scheduled) == 2
    # each order records its share of the doubled charge
    # each copy records its own price, so mark_paid is told it shares a session
    assert seen == [(family.id, 2), (selfo.id, 2)]
    # family copy → saved address; self copy → the address Stripe collected
    by_kind = {c["order"].recipient_kind: c["address"] for c in created}
    assert by_kind["family"]["name"] == "Fam"
    assert by_kind["self"]["line1"] == "9 Buyer Rd"


def test_funnel_both_family_claim_lost_refunds_half_fulfills_self(monkeypatch):
    import gift_fulfillment

    family = _order()
    selfo = _order()
    selfo.recipient_kind = "self"
    outcomes = {family.id: ("claim_lost", family), selfo.id: ("paid", selfo)}
    birth = SimpleNamespace(id=family.birth_id, shipping_address=None)
    item = SimpleNamespace(kind=GiftKind.physical, storage_years_granted=None)

    session_obj = _session_obj(family, session_id="cs_both")
    session_obj["amount_total"] = 3600
    session_obj["metadata"]["order_id_2"] = str(selfo.id)
    session_obj["collected_information"] = {
        "shipping_details": {"name": "Buyer", "address": {"line1": "9 Buyer Rd"}}
    }

    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo,
        "mark_paid",
        lambda db, *, order_id, session_obj, orders_in_session=1: outcomes[order_id],
    )
    refunds, marked = [], []
    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo,
        "mark_refunded",
        lambda db, *, order_id: marked.append(order_id),
    )
    monkeypatch.setattr(
        gift_fulfillment.gift_orders_repo,
        "create_shipment",
        lambda db, **kw: SimpleNamespace(id=uuid.uuid4(), fulfillment_status="none"),
    )
    stripe = SimpleNamespace(create_refund=lambda **kw: refunds.append(kw))

    status = asyncio.run(
        gift_fulfillment.fulfill_gift_from_session(
            _dispatching_db(birth, item), stripe, session_obj, _Tasks(),
            raise_on_refund_error=True,
        )
    )
    # the self copy still ships, so the session reads fulfilled overall
    assert status == "fulfilled"
    assert marked == [family.id]
    # only the family copy's share is refunded, keyed per order
    assert refunds == [
        {
            "payment_intent_id": "pi_1",
            "kind": "gift",
            "amount_cents": 1800,
            "key_suffix": f"-{family.id}",
        }
    ]


def test_grant_storage_gift_from_nothing():
    from datetime import datetime, timedelta, timezone

    from repositories import gift_orders as repo

    birth = SimpleNamespace(storage_paid_until=None)
    db = _FakeCommitSession()
    before = datetime.now(timezone.utc)

    repo.grant_storage_gift(db, birth=birth, storage_years_granted=5)

    assert db.commits == 1
    # ~5 years out, give or take the leap-year approximation
    assert birth.storage_paid_until > before + timedelta(days=5 * 365 - 1)
    assert birth.storage_paid_until < before + timedelta(days=5 * 365 + 1)


def test_grant_storage_gift_lifetime_sets_flag_not_date():
    from repositories import gift_orders as repo

    birth = SimpleNamespace(storage_paid_until=None, storage_lifetime=False)
    db = _FakeCommitSession()

    repo.grant_storage_gift(db, birth=birth, storage_years_granted=None)

    assert db.commits == 1
    assert birth.storage_lifetime is True
    # lifetime is the flag, not a sentinel date
    assert birth.storage_paid_until is None


def test_grant_storage_gift_stacks_on_existing():
    from datetime import datetime, timedelta, timezone

    from repositories import gift_orders as repo

    existing = datetime.now(timezone.utc) + timedelta(days=365)  # 1 year out
    birth = SimpleNamespace(storage_paid_until=existing)
    db = _FakeCommitSession()

    repo.grant_storage_gift(db, birth=birth, storage_years_granted=5)

    # stacks on top of the existing grant, not from today
    assert birth.storage_paid_until > existing + timedelta(days=5 * 365 - 1)


def test_grant_storage_gift_ignores_expired_grant():
    from datetime import datetime, timedelta, timezone

    from repositories import gift_orders as repo

    expired = datetime.now(timezone.utc) - timedelta(days=30)
    birth = SimpleNamespace(storage_paid_until=expired)
    db = _FakeCommitSession()
    before = datetime.now(timezone.utc)

    repo.grant_storage_gift(db, birth=birth, storage_years_granted=5)

    # bases from now, not from the stale past date
    assert birth.storage_paid_until > before + timedelta(days=5 * 365 - 1)


# ── printful create_order ─────────────────────────────────────────────────


def test_printful_create_order_draft():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["json"] = req.read().decode()
        return httpx.Response(200, json={"result": {
            "id": 4242, "status": "draft",
            "costs": {"currency": "USD", "subtotal": "6.07", "shipping": "6.69", "tax": "0.93", "vat": "0.00", "total": "13.69"},
        }})

    a = PrintfulAdapter(
        api_key="k", client=_client(handler, base="https://api.printful.com")
    )
    result = a.create_order(
        recipient={"name": "Janet", "address1": "1 St", "city": "Phx",
                   "state_code": "AZ", "country_code": "US", "zip": "85001"},
        items=[{"variant_id": 1320, "quantity": 1, "files": [{"url": "https://s3/x.png"}]}],
        external_id="order-1",
        confirm=False,
        gift={"subject": "A gift for you", "message": "love, mom"},
    )
    assert result.order_id == "4242" and result.status == "draft"
    # what the partner will bill, in cents — the margin's other half
    assert result.costs == {"product": 607, "shipping": 669, "tax": 93, "total": 1369}
    assert "confirm=0" in seen["url"]
    assert '"external_id":"order-1"' in seen["json"]
    assert '"variant_id":1320' in seen["json"]
    assert '"love, mom"' in seen["json"]


def test_printful_create_order_confirm_flag_and_error():
    def handler(req: httpx.Request) -> httpx.Response:
        assert "confirm=1" in str(req.url)
        return httpx.Response(400, json={"error": {"message": "bad"}})

    a = PrintfulAdapter(
        api_key="k", client=_client(handler, base="https://api.printful.com")
    )
    with pytest.raises(OrderError) as exc:
        a.create_order(
            recipient={}, items=[], external_id="x", confirm=True
        )
    # the partner's own words, not just the status line — "400 Bad Request"
    # on its own cost an evening's debugging on the first real order
    assert "400" in str(exc.value) and "bad" in str(exc.value)


def test_partner_external_id_fits_printful():
    import uuid

    from repositories.gift_orders import partner_external_id

    oid = uuid.UUID("638659f9-b331-4d03-b7c2-93578c233519")
    ext = partner_external_id(oid)
    assert len(ext) <= 32
    assert "-" not in ext
    # and it still round-trips to the order
    assert uuid.UUID(ext) == oid


# ── webhook dispatch ──────────────────────────────────────────────────────


def test_webhook_dispatches_gift_kind(monkeypatch):
    import hashlib
    import hmac as hmac_mod
    import json as json_mod
    import time as time_mod

    from fastapi.testclient import TestClient
    import gift_fulfillment
    import main

    secret = "whsec_gift"
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")

    called = {"gift": 0}

    async def fake_gift(db, stripe, obj, tasks, *, raise_on_refund_error):
        called["gift"] += 1
        return "fulfilled"

    monkeypatch.setattr(gift_fulfillment, "fulfill_gift_from_session", fake_gift)

    client = TestClient(main.app)

    def signed(body: bytes) -> dict:
        ts = int(time_mod.time())
        mac = hmac_mod.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256)
        return {"stripe-signature": f"t={ts},v1={mac.hexdigest()}"}

    body = json_mod.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"kind": "gift_order", "order_id": str(uuid.uuid4())},
                    "payment_status": "paid",
                }
            },
        }
    ).encode()
    r = client.post("/webhooks/stripe", content=body, headers=signed(body))
    assert r.status_code == 200
    assert called == {"gift": 1}


def test_split_fee_shares_by_amount_and_sums_exactly():
    from repositories.gift_orders import split_fee

    assert split_fee(102, [2469]) == [102]
    # a "both" purchase: two copies at different postage, one fee
    shares = split_fee(150, [2469, 3199])
    assert sum(shares) == 150 and shares[0] < shares[1]
    assert split_fee(30, [0, 0]) == [30, 0]
    assert split_fee(30, []) == []


# ── the buyer's receipt ───────────────────────────────────────────────────


def test_order_reference_is_short_and_quotable():
    import uuid

    from repositories.gift_orders import order_reference

    ref = order_reference(uuid.UUID("638659f9-b331-4d03-b7c2-93578c233519"))
    assert ref == "638659F9"


def test_destination_is_city_and_state_only():
    from repositories.gift_orders import _destination

    assert _destination({"name": "J", "line1": "1 St", "city": "Raleigh", "state": "NC", "postal_code": "27601"}) == "Raleigh, NC"
    # a partner-shaped address (state_code) reads the same
    assert _destination({"city": "Raleigh", "state_code": "NC"}) == "Raleigh, NC"
    assert _destination(None) is None
    assert _destination({"line1": "1 St"}) is None


def test_my_orders_requires_a_token():
    from fastapi.testclient import TestClient
    import main

    assert TestClient(main.app).get("/me/orders").status_code == 401


def test_receipt_route_is_public_and_scoped_to_the_birth(monkeypatch):
    import uuid
    from datetime import datetime, timezone

    from fastapi.testclient import TestClient
    import main
    from db import get_db
    from routes import checkout

    birth = SimpleNamespace(id=uuid.uuid4(), slug="lily-wren", child_name="Lily", theme="lily")
    order_id = uuid.uuid4()
    order = SimpleNamespace(id=order_id, birth_id=birth.id)
    other_birth_order = SimpleNamespace(id=uuid.uuid4(), birth_id=uuid.uuid4())

    class FakeDb:
        def get(self, model, key):
            return {order_id: order, other_birth_order.id: other_birth_order}.get(key)

    monkeypatch.setattr(checkout, "resolve_public_birth", lambda db, slug: birth)
    monkeypatch.setattr(
        checkout.gift_orders_repo,
        "receipt",
        lambda db, o, b: [{
            "id": o.id, "reference": "638659F9", "status": "paid", "fulfillment_status": "submitted",
            "recipient_kind": "self", "item_display_name": "Birth Story Mug",
            "product_display_name": "White glossy 11oz", "image_url": None, "destination": "Raleigh, NC",
            "product_price_cents": 1800, "shipping_cents": 669, "amount_cents": 2469,
            "gift_message": None, "created_at": datetime.now(timezone.utc),
        }],
    )
    main.app.dependency_overrides[get_db] = lambda: FakeDb()
    try:
        client = TestClient(main.app)
        ok = client.get(f"/b/lily-wren/orders/{order_id}")
        assert ok.status_code == 200
        body = ok.json()
        assert body["child_name"] == "Lily" and body["orders"][0]["reference"] == "638659F9"
        assert ok.headers["cache-control"] == "no-store"
        # nothing a stranger could use rides along
        assert not {"email", "line1", "stripe_payment_intent_id", "printful_order_id"} & set(body["orders"][0])
        # an order from another birth is not this page's business
        assert client.get(f"/b/lily-wren/orders/{other_birth_order.id}").status_code == 404
        assert client.get(f"/b/lily-wren/orders/{uuid.uuid4()}").status_code == 404
    finally:
        main.app.dependency_overrides.clear()
