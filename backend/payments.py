"""Stripe payments — the $12 family unlock via hosted Checkout.

Same conventions as the other integrations (fulfillment/printful.py,
messenger.py): direct REST via httpx, no SDK; injectable client for tests;
env-gated factory so an unconfigured environment degrades gracefully
(the unlock CTA 503s instead of erroring).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import httpx

from auth import FRONTEND_URL

_BASE_URL = "https://api.stripe.com"
_REQUEST_TIMEOUT = 20.0
_SIGNATURE_TOLERANCE_SECONDS = 300
# Pin the API version so response shapes are deterministic instead of
# following the account default (e.g. where a Checkout session exposes its
# collected shipping address). Overridable for a deliberate upgrade.
_API_VERSION = os.getenv("STRIPE_API_VERSION", "2026-06-24.dahlia")


class StripeError(Exception):
    """A Stripe call failed — worth a 502/500, never a silent pass."""


class StripeClient:
    def __init__(self, *, secret_key: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url=_BASE_URL, timeout=_REQUEST_TIMEOUT
        )
        self._client.headers.update(
            {
                "Authorization": f"Bearer {secret_key}",
                "Stripe-Version": _API_VERSION,
            }
        )

    def create_checkout_session(
        self,
        *,
        birth_id: str,
        user_id: str,
        slug: str,
        child_name: str | None,
        amount_cents: int,
    ) -> dict:
        """One-time-payment hosted Checkout session. Returns the session
        object (the caller redirects the browser to session["url"])."""
        product_name = (
            f"Family unlock — {child_name}'s page" if child_name else "Family unlock"
        )
        # {CHECKOUT_SESSION_ID} must reach Stripe literally — it's their
        # template placeholder, not ours.
        success_url = (
            f"{FRONTEND_URL}/b/{slug}?unlock_session={{CHECKOUT_SESSION_ID}}"
        )
        data = {
            "mode": "payment",
            "client_reference_id": str(birth_id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(amount_cents),
            "line_items[0][price_data][product_data][name]": product_name,
            "success_url": success_url,
            "cancel_url": f"{FRONTEND_URL}/b/{slug}",
            # kind lets the shared webhook endpoint ignore future non-unlock
            # products; mirrored onto the PaymentIntent so the dashboard
            # (and refunds) are self-describing.
            "metadata[kind]": "family_unlock",
            "metadata[birth_id]": str(birth_id),
            "metadata[user_id]": str(user_id),
            "payment_intent_data[metadata][kind]": "family_unlock",
            "payment_intent_data[metadata][birth_id]": str(birth_id),
        }
        try:
            resp = self._client.post("/v1/checkout/sessions", data=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise StripeError(f"create checkout session: {exc}") from exc

    def create_gift_checkout_session(
        self,
        *,
        order_id: str,
        birth_id: str,
        user_id: str,
        slug: str,
        product_name: str,
        amount_cents: int,
        collect_shipping: bool,
        allowed_countries: list[str],
    ) -> dict:
        """Hosted Checkout for a gift order. When `collect_shipping`, Stripe
        gathers the shipping address (the buyer's own, or the family's when
        the parents haven't saved one); otherwise the parent-saved address is
        resolved at fulfillment time."""
        data = {
            "mode": "payment",
            "client_reference_id": str(order_id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(amount_cents),
            "line_items[0][price_data][product_data][name]": product_name,
            "success_url": (
                f"{FRONTEND_URL}/b/{slug}?gift_session={{CHECKOUT_SESSION_ID}}"
            ),
            "cancel_url": f"{FRONTEND_URL}/b/{slug}",
            "metadata[kind]": "gift_order",
            "metadata[order_id]": str(order_id),
            "metadata[birth_id]": str(birth_id),
            "metadata[user_id]": str(user_id),
            "payment_intent_data[metadata][kind]": "gift_order",
            "payment_intent_data[metadata][order_id]": str(order_id),
        }
        if collect_shipping:
            for i, country in enumerate(allowed_countries):
                data[f"shipping_address_collection[allowed_countries][{i}]"] = country
        try:
            resp = self._client.post("/v1/checkout/sessions", data=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise StripeError(f"create gift checkout session: {exc}") from exc

    def retrieve_checkout_session(self, session_id: str) -> dict | None:
        """The session object, or None for an unknown/forged id (Stripe
        answers 404/invalid for ids that aren't ours)."""
        try:
            resp = self._client.get(f"/v1/checkout/sessions/{session_id}")
            if resp.status_code in (400, 404):
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise StripeError(f"retrieve checkout session: {exc}") from exc

    def create_refund(self, *, payment_intent_id: str, kind: str = "unlock") -> None:
        """Refund the losing payment of a claim race. Idempotent: the
        Idempotency-Key dedupes concurrent attempts (the loser's webhook and
        redirect-confirm can both try), and an already-refunded charge counts
        as success. `kind` namespaces the key per product (unlock, gift)."""
        try:
            resp = self._client.post(
                "/v1/refunds",
                data={"payment_intent": payment_intent_id},
                headers={"Idempotency-Key": f"{kind}-refund-{payment_intent_id}"},
            )
            if resp.status_code >= 400:
                body = resp.json() if resp.content else {}
                code = (body.get("error") or {}).get("code")
                if code == "charge_already_refunded":
                    return
                raise StripeError(f"refund {payment_intent_id}: {resp.status_code} {code}")
        except httpx.HTTPError as exc:
            raise StripeError(f"refund {payment_intent_id}: {exc}") from exc


def verify_stripe_signature(
    payload: bytes,
    header: str | None,
    secret: str,
    *,
    tolerance_seconds: int = _SIGNATURE_TOLERANCE_SECONDS,
    now: int | None = None,
) -> bool:
    """Verify a Stripe-Signature header (scheme v1): the header carries
    `t=<unix>,v1=<hmac>[,v1=...]`; the signature is HMAC-SHA256 of
    f"{t}.{raw_body}" with the webhook secret. Constant-time compare against
    every v1 candidate; stale timestamps are rejected."""
    if not header or not secret:
        return False
    timestamp: str | None = None
    candidates: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            candidates.append(value)
    if timestamp is None or not candidates:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    current = now if now is not None else int(time.time())
    if abs(current - ts) > tolerance_seconds:
        return False
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, c) for c in candidates)


def extract_shipping(session_obj: dict) -> dict | None:
    """The shipping address a completed Checkout session collected, as our
    canonical shape {name, line1, line2, city, state, postal_code, country}.

    Stripe moved the field across API versions: newer versions put it under
    collected_information.shipping_details, older ones top-level as
    shipping_details; customer_details (billing) is the last resort. We pin
    the API version (so the first shape is expected), but keep all three
    fallbacks — webhook event payloads follow the webhook endpoint's own
    pinned version, not our request header."""
    candidates = [
        (session_obj.get("collected_information") or {}).get("shipping_details"),
        session_obj.get("shipping_details"),
        session_obj.get("customer_details"),
    ]
    for c in candidates:
        if not c:
            continue
        address = c.get("address") or {}
        if not address.get("line1"):
            continue
        return {
            "name": c.get("name"),
            "line1": address.get("line1"),
            "line2": address.get("line2"),
            "city": address.get("city"),
            "state": address.get("state"),
            "postal_code": address.get("postal_code"),
            "country": address.get("country"),
        }
    return None


def gift_shipping_countries() -> list[str]:
    raw = os.getenv("GIFT_SHIPPING_COUNTRIES", "US")
    return [c.strip().upper() for c in raw.split(",") if c.strip()]


def get_stripe() -> StripeClient | None:
    """The configured Stripe client, or None (payment endpoints then 503 —
    same gating ethos as fulfillment.get_adapter)."""
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        return None
    return StripeClient(secret_key=key)


def unlock_price_cents() -> int:
    return int(os.getenv("UNLOCK_PRICE_CENTS", "1200"))
