"""Curated Printful product shortlist for the "see this design on another
product" picker.

A code registry (same ethos as `gift_templates.py` — adding a product is a
code change, not a migration). Each entry maps a stable `key` to a Printful
catalog product/variant plus the artwork `product_kind` it accepts. All
mug-shaped designs share the same 2475x1155 wrap artwork, so any "mug" design
can be rendered onto any mug product listed here.

Product/variant ids are from the live Printful catalog
(GET https://api.printful.com/products/{id}).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShortlistProduct:
    key: str
    display_name: str
    product_kind: str  # the artwork product_kind this product accepts
    product_id: int  # Printful catalog product id
    variant_id: int  # Printful catalog variant id
    placement: str = "default"


# Insertion order is the display order in the picker.
SHORTLIST: dict[str, ShortlistProduct] = {
    "white_glossy_11oz": ShortlistProduct(
        key="white_glossy_11oz",
        display_name="White Glossy Mug (11 oz)",
        product_kind="mug",
        product_id=19,
        variant_id=1320,
    ),
    "white_glossy_15oz": ShortlistProduct(
        key="white_glossy_15oz",
        display_name="White Glossy Mug (15 oz)",
        product_kind="mug",
        product_id=19,
        variant_id=4830,
    ),
    "white_glossy_20oz": ShortlistProduct(
        key="white_glossy_20oz",
        display_name="White Glossy Mug (20 oz)",
        product_kind="mug",
        product_id=19,
        variant_id=16586,
    ),
    "black_glossy_11oz": ShortlistProduct(
        key="black_glossy_11oz",
        display_name="Black Glossy Mug (11 oz)",
        product_kind="mug",
        product_id=300,
        variant_id=9323,
    ),
    "black_glossy_15oz": ShortlistProduct(
        key="black_glossy_15oz",
        display_name="Black Glossy Mug (15 oz)",
        product_kind="mug",
        product_id=300,
        variant_id=9324,
    ),
    "latte_mug": ShortlistProduct(
        key="latte_mug",
        display_name="Latte Mug (12 oz)",
        product_kind="mug",
        product_id=837,
        variant_id=21352,
    ),
}

# The product used for the default hero mockup on the gift gallery, per
# artwork product_kind. The picker offers the rest as alternatives.
DEFAULT_PRODUCT_BY_KIND: dict[str, str] = {
    "mug": "white_glossy_11oz",
}


def get(key: str) -> ShortlistProduct | None:
    return SHORTLIST.get(key)


def for_product_kind(product_kind: str) -> list[ShortlistProduct]:
    """The shortlist products a given artwork product_kind can be shown on."""
    return [p for p in SHORTLIST.values() if p.product_kind == product_kind]


def default_for_product_kind(product_kind: str) -> ShortlistProduct | None:
    """The product used for the auto-generated hero mockup, or None when the
    product_kind has no mapped product (mockups are then skipped)."""
    key = DEFAULT_PRODUCT_BY_KIND.get(product_kind)
    return SHORTLIST.get(key) if key else None
