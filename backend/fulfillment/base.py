"""Vendor-agnostic fulfillment adapter interface.

A fulfillment partner (Printful first) turns our flat artwork into a product
mockup — the artwork rendered onto the real mug/card. Keeping this behind an
interface means a second vendor is a new adapter, not a rewrite, and lets the
app run with no partner configured (the gallery just shows the flat artwork).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class MockupError(Exception):
    """Mockup generation failed for a reason worth recording on the row."""


class OrderError(Exception):
    """Order submission failed for a reason worth recording on the shipment."""


@dataclass
class MockupExtra:
    """An additional angle/view of the same mockup (e.g. a mug's
    handle-from-left shot). Not every product has these."""

    title: str
    image_bytes: bytes
    content_type: str


@dataclass
class MockupResult:
    image_bytes: bytes
    content_type: str
    source_url: str
    extra: list[MockupExtra] = field(default_factory=list)


@dataclass
class OrderResult:
    order_id: str
    status: str


class FulfillmentAdapter(ABC):
    name: str

    @abstractmethod
    def create_order(
        self,
        *,
        recipient: dict,
        items: list[dict],
        external_id: str,
        confirm: bool,
        gift: dict | None = None,
    ) -> OrderResult:
        """Submit a fulfillment order (confirm=False → a draft the merchant
        approves by hand — the safe default). `recipient` is the partner's
        address shape; `items` carry variant ids + artwork file URLs, which
        must stay publicly reachable long enough for a draft to be confirmed.
        Raises OrderError on failure."""

    @abstractmethod
    def generate_mockup(
        self,
        *,
        artwork_url: str,
        product_id: int,
        variant_id: int,
        artwork_width: int,
        artwork_height: int,
        placement: str = "default",
        option_groups: tuple[str, ...] = (),
    ) -> MockupResult:
        """Render `artwork_url` onto the partner's product/variant and return
        the mockup image, plus any extra angle/view mockups the partner
        generated alongside it. Raises MockupError on failure. `artwork_url` must be
        reachable by the partner's servers (a public/presigned URL — not a
        localhost dev URL). `artwork_width`/`artwork_height` are the artwork's
        pixel dimensions — our templates are drawn at the product's full print
        area, so placement is always the full area. The caller picks the
        product/variant from the curated shortlist (`fulfillment.products`)."""
