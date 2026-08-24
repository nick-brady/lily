"""Checking a shipping address before the money moves.

Stripe used to collect the destination on its hosted page, which meant its
form did a first pass on it for free. Now that the buyer names the
destination here, that pass is ours — and it matters more than it sounds: a
bad address isn't caught at checkout, it's caught by Printful *after* the
payment, where it lands as a failed shipment with the charge kept.

Two layers, deliberately:

* Structure — required fields, a country we actually ship to, and a state
  code where Printful demands one. Always on, no network, refuses the order.
* Reality — Google's Address Validation API, which knows whether the place
  exists. Optional (needs GOOGLE_MAPS_API_KEY), and it *never* refuses. It
  suggests a correction and says when it couldn't confirm one. Real addresses
  fail confirmation all the time — new construction, rural routes, a flat
  number the postal file hasn't caught up with — and someone who knows where
  their sister lives shouldn't be told they're wrong by a database.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_ENDPOINT = "https://addressvalidation.googleapis.com/v1:validateAddress"
_TIMEOUT = 6.0

# Printful rejects US and Canadian orders without a state/province code; the
# rest of the world it takes without one.
STATE_REQUIRED = {"US", "CA"}


class AddressError(ValueError):
    """The address can't be shipped to as given."""


def check_structure(address: dict, *, allowed_countries: list[str]) -> None:
    """Refuse what we know can't ship. Raises AddressError."""
    country = (address.get("country") or "").upper()
    if country not in {c.upper() for c in allowed_countries}:
        raise AddressError(
            f"We can only ship to: {', '.join(sorted(allowed_countries))}"
        )
    for field, label in (
        ("name", "a name"),
        ("line1", "a street address"),
        ("city", "a city"),
        ("postal_code", "a postal code"),
    ):
        if not (address.get(field) or "").strip():
            raise AddressError(f"This address needs {label}.")
    if country in STATE_REQUIRED and not (address.get("state") or "").strip():
        raise AddressError("This address needs a state or province.")


def is_configured() -> bool:
    return bool(os.getenv("GOOGLE_MAPS_API_KEY"))


def review(address: dict, *, client: httpx.Client | None = None) -> dict:
    """Ask Google whether this address is real, and what it would call it.

    Returns {"verdict", "suggestion"} where verdict is one of:

    * "confirmed"   — Google recognised it; suggestion may still restate it
    * "corrected"   — recognised, but it would write it differently
    * "unconfirmed" — it couldn't confirm part of it; suggestion may be null
    * "unchecked"   — no key configured, or the call didn't come back

    Never raises. An outage at Google is not a reason someone can't buy a mug.
    """
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        return {"verdict": "unchecked", "suggestion": None}
    body = {
        "address": {
            "regionCode": (address.get("country") or "US").upper(),
            "postalCode": address.get("postal_code") or "",
            "administrativeArea": address.get("state") or "",
            "locality": address.get("city") or "",
            "addressLines": [
                line
                for line in (address.get("line1"), address.get("line2"))
                if (line or "").strip()
            ],
        },
        # We're validating what someone typed, not enriching it — don't ask
        # Google to hold onto it.
        "enableUspsCass": False,
    }
    try:
        owned = client is None
        c = client or httpx.Client(timeout=_TIMEOUT)
        try:
            resp = c.post(_ENDPOINT, params={"key": key}, json=body)
            resp.raise_for_status()
            payload = resp.json()
        finally:
            if owned:
                c.close()
    except Exception:  # transport, status, or malformed JSON
        logger.warning("address validation unavailable", exc_info=True)
        return {"verdict": "unchecked", "suggestion": None}

    result = payload.get("result") or {}
    verdict_raw = result.get("verdict") or {}
    suggestion = _suggestion(result, address)

    complete = verdict_raw.get("addressComplete") is True
    unresolved = bool(verdict_raw.get("hasUnconfirmedComponents")) or bool(
        (result.get("address") or {}).get("unresolvedTokens")
    )
    if not complete or unresolved:
        return {"verdict": "unconfirmed", "suggestion": suggestion}
    if suggestion and _comparable(suggestion) != _comparable(address):
        return {"verdict": "corrected", "suggestion": suggestion}
    return {"verdict": "confirmed", "suggestion": suggestion}


def _comparable(address: dict) -> dict:
    """The fields a suggestion can differ in, normalised for comparison —
    so "St" vs "Street" reads as a correction but "st." vs "St." doesn't."""
    return {
        k: " ".join((address.get(k) or "").split()).upper()
        for k in ("line1", "line2", "city", "state", "postal_code", "country")
    }


def _suggestion(result: dict, original: dict) -> dict | None:
    """Google's own rendering of the address, in our canonical shape."""
    postal = result.get("address") or {}
    components = {
        c.get("componentType"): (c.get("componentName") or {}).get("text", "")
        for c in postal.get("addressComponents") or []
    }
    lines = postal.get("postalAddress", {}).get("addressLines") or []
    if not lines:
        return None
    return {
        # The name is ours, not Google's — it validates places, not people.
        "name": original.get("name"),
        "line1": lines[0],
        "line2": lines[1] if len(lines) > 1 else None,
        "city": postal.get("postalAddress", {}).get("locality")
        or components.get("locality", ""),
        "state": postal.get("postalAddress", {}).get("administrativeArea")
        or components.get("administrative_area_level_1", ""),
        "postal_code": postal.get("postalAddress", {}).get("postalCode")
        or components.get("postal_code", ""),
        "country": (postal.get("postalAddress", {}).get("regionCode") or "US").upper(),
    }
