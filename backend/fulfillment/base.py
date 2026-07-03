"""Vendor-agnostic fulfillment adapter interface.

A fulfillment partner (Printful first) turns our flat artwork into a product
mockup — the artwork rendered onto the real mug/card. Keeping this behind an
interface means a second vendor is a new adapter, not a rewrite, and lets the
app run with no partner configured (the gallery just shows the flat artwork).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class MockupError(Exception):
    """Mockup generation failed for a reason worth recording on the row."""


@dataclass
class MockupResult:
    image_bytes: bytes
    content_type: str
    source_url: str


class FulfillmentAdapter(ABC):
    name: str

    @abstractmethod
    def generate_mockup(
        self,
        *,
        artwork_url: str,
        product_id: int,
        variant_id: int,
        placement: str = "default",
    ) -> MockupResult:
        """Render `artwork_url` onto the partner's product/variant and return
        the mockup image. Raises MockupError on failure. `artwork_url` must be
        reachable by the partner's servers (a public/presigned URL — not a
        localhost dev URL). The caller picks the product/variant from the
        curated shortlist (`fulfillment.products`)."""
