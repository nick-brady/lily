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
    # A photograph of the blank product, straight from Printful's catalog CDN.
    # This is what makes choosing a mug free: the picker shows these, and the
    # partner's mockup generator — 2 calls a minute for the whole store — is
    # spent only on the one someone actually picks.
    blank_image_url: str = ""
    # What Printful charges us, for reference when pricing. The spread is
    # $5.95–$9.50, so every mug here is profitable at the item price.
    cost_cents: int = 0
    # Added to the item price when this product is chosen. The default mug is
    # the price on the tin; the larger and darker ones cost us $2–$3.55 more,
    # so they carry a flat surcharge rather than eating the margin.
    surcharge_cents: int = 0


# Insertion order is the display order in the picker; the first is the default.
#
# White only, and not for want of options. The artwork fills its whole print
# area with the theme's background — an opaque rectangle, not a transparency —
# so on a dark mug it prints a pale slab across the wrap rather than sitting on
# the ceramic. Recolouring the type wouldn't help; the panel is the problem. A
# dark product needs artwork drawn for it, not this artwork inverted.
SHORTLIST: dict[str, ShortlistProduct] = {
    "white_glossy_11oz": ShortlistProduct(
        key="white_glossy_11oz",
        display_name="White Glossy Mug (11 oz)",
        product_kind="mug",
        product_id=19,
        variant_id=1320,
        blank_image_url="https://files.cdn.printful.com/products/19/1320_1663762583.jpg",
        cost_cents=595,
    ),
    "white_glossy_15oz": ShortlistProduct(
        key="white_glossy_15oz",
        display_name="White Glossy Mug (15 oz)",
        product_kind="mug",
        product_id=19,
        variant_id=4830,
        blank_image_url="https://files.cdn.printful.com/products/19/4830_1519394046.jpg",
        cost_cents=795,
        surcharge_cents=300,
    ),
    "white_glossy_20oz": ShortlistProduct(
        key="white_glossy_20oz",
        display_name="White Glossy Mug (20 oz)",
        product_kind="mug",
        product_id=19,
        variant_id=16586,
        blank_image_url="https://files.cdn.printful.com/products/19/16586_1680616351.jpg",
        cost_cents=950,
        surcharge_cents=300,
    ),
    "latte_mug": ShortlistProduct(
        key="latte_mug",
        display_name="Latte Mug (12 oz)",
        product_kind="mug",
        product_id=837,
        variant_id=21352,
        blank_image_url="https://files.cdn.printful.com/products/837/21352_1735896974.jpg",
        cost_cents=829,
        surcharge_cents=300,
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


def surcharge_for(product_key: str | None) -> int:
    """What choosing this product adds to the item price. Unknown or unset
    keys cost nothing extra — the default mug is the price on the tin."""
    product = SHORTLIST.get(product_key or "")
    return product.surcharge_cents if product else 0


def for_rendering(product_key: str | None, product_kind: str) -> ShortlistProduct | None:
    """The product a design is destined for: what was chosen, else the default
    for its kind. One place decides this, so the mockup someone approves and
    the mug that ships can't disagree."""
    chosen = SHORTLIST.get(product_key or "")
    if chosen is not None and chosen.product_kind == product_kind:
        return chosen
    return default_for_product_kind(product_kind)
