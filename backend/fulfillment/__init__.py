"""Fulfillment partner adapters. `get_adapter()` returns the configured
partner, or None when none is configured (the app then just shows the flat
artwork)."""
from __future__ import annotations

import os

from fulfillment.base import FulfillmentAdapter, MockupError, MockupResult
from fulfillment.printful import PrintfulAdapter

__all__ = [
    "FulfillmentAdapter",
    "MockupError",
    "MockupResult",
    "PrintfulAdapter",
    "get_adapter",
]


def get_adapter() -> FulfillmentAdapter | None:
    """The configured fulfillment partner, or None. Currently Printful, gated
    on PRINTFUL_API_KEY so dev/test runs with no partner."""
    api_key = os.getenv("PRINTFUL_API_KEY")
    if not api_key:
        return None
    return PrintfulAdapter(api_key=api_key, store_id=os.getenv("PRINTFUL_STORE_ID"))
