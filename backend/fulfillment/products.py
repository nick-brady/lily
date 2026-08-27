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
    # Which of the partner's mockup styles to ask for. Empty means their
    # default set — for mugs that's three angles (front, handle left, front
    # view). A framed poster's default is one flat shot, so the frames ask
    # for the flat and the in-room ones too, to give the tile the same
    # three-image rhythm the mug has.
    mockup_option_groups: tuple[str, ...] = ()
    # The one or two words that tell this product apart from its neighbours
    # in the picker, under its picture: "15 oz", "Oak", "Matte". The blank
    # photos alone can't — two white books look the same at a hundred pixels.
    caption: str = ""
    # Which sides to photograph. The ornament has a front and a back placement
    # and we print the front; left unsaid, the partner also sends a picture of
    # the blank back, which the tile then shows as if it were ours.
    mockup_options: tuple[str, ...] = ()
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
        caption="11 oz",
        display_name="White Glossy Mug (11 oz)",
        product_kind="mug",
        product_id=19,
        variant_id=1320,
        blank_image_url="https://files.cdn.printful.com/products/19/1320_1663762583.jpg",
        cost_cents=595,
    ),
    "white_glossy_15oz": ShortlistProduct(
        key="white_glossy_15oz",
        caption="15 oz",
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
        caption="20 oz",
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
        caption="Latte",
        display_name="Latte Mug (12 oz)",
        product_kind="mug",
        product_id=837,
        variant_id=21352,
        blank_image_url="https://files.cdn.printful.com/products/837/21352_1735896974.jpg",
        cost_cents=829,
        surcharge_cents=300,
    ),
}

# ── framed prints ─────────────────────────────────────────────────────────
# One size, three frames, one price. 12×16 is the nearest sheet to the card
# designs' 5:7 (the margin the mat covers is 2% a side), and Printful charges
# the same $35.70 whatever the frame, so the colour is a free choice rather
# than a surcharge. The print file is 3600×4800 at 300 DPI.
_FRAME_IMAGES = {
    20256: "https://files.cdn.printful.com/products/795/20256_1722419854.jpg",
    20257: "https://files.cdn.printful.com/products/795/20257_1722419975.jpg",
    20258: "https://files.cdn.printful.com/products/795/20258_1722419996.jpg",
}
for _key, _name, _variant in (
    ("frame_black_12x16", "Black frame (12×16 in, matted)", 20256),
    ("frame_oak_12x16", "Oak frame (12×16 in, matted)", 20257),
    ("frame_white_12x16", "White frame (12×16 in, matted)", 20258),
):
    SHORTLIST[_key] = ShortlistProduct(
        key=_key,
        display_name=_name,
        caption=_name.split()[0],
        product_kind="framed_print",
        product_id=795,
        variant_id=_variant,
        blank_image_url=_FRAME_IMAGES[_variant],
        cost_cents=3570,
        mockup_option_groups=("Flat", "Lifestyle"),
    )

# ── ornaments ─────────────────────────────────────────────────────────────
# A ceramic circle, printed edge to edge on the front. $6.22 + about $5.30
# to ship. (A wooden oval with the dial on it came first; a photo of the
# baby beats a dial at three inches, and ceramic takes a photo.)
SHORTLIST["ornament_circle"] = ShortlistProduct(
    key="ornament_circle",
    display_name="Ceramic ornament (circle)",
    caption="Circle",
    product_kind="ornament",
    product_id=881,
    variant_id=22782,
    placement="front",
    blank_image_url="https://files.cdn.printful.com/products/881/22782_1747141509.jpg",
    cost_cents=622,
    mockup_option_groups=("Flat", "Lifestyle"),
    mockup_options=("Front",),
)

# ── the photo book ────────────────────────────────────────────────────────
# Hardcover 8×8, twenty-four pages, $11.23 + about $7.50 to ship. Matte is
# the default because two of its pages are for a pen, and glossy paper takes
# ink badly. Same price either way.
for _key, _name, _variant, _image in (
    ("book_8x8_matte", "Matte pages (8×8 in hardcover)", 49376, "https://files.cdn.printful.com/products/1564/49376_1781805692.jpg"),
    ("book_8x8_glossy", "Glossy pages (8×8 in hardcover)", 49375, "https://files.cdn.printful.com/products/1564/49375_1781805691.jpg"),
):
    SHORTLIST[_key] = ShortlistProduct(
        key=_key,
        display_name=_name,
        caption=_name.split()[0],
        product_kind="photo_book",
        product_id=1564,
        variant_id=_variant,
        placement="cover",
        blank_image_url=_image,
        cost_cents=1123,
        mockup_options=("Front", "Back"),   # the closed book, both sides
    )

# The product used for the default hero mockup on the gift gallery, per
# artwork product_kind. The picker offers the rest as alternatives.
DEFAULT_PRODUCT_BY_KIND: dict[str, str] = {
    "mug": "white_glossy_11oz",
    "framed_print": "frame_black_12x16",
    "ornament": "ornament_circle",
    "photo_book": "book_8x8_matte",
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
