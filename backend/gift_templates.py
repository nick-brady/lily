"""Gift template registry.

A "template" is a code artifact (a Jinja2 SVG under templates/gifts/), keyed
by `template_id`. Each `gift_catalog_items.template_metadata.templates` lists
which template ids are valid for that product. Keeping templates in code (not
DB rows) matches the codebase ethos — a new design is a code change, not a
migration.

`dims` are the exact output pixels (≈300 DPI for the product's print area).
`photo=True` templates embed the auto-selected hero photo.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GiftTemplate:
    template_id: str
    product_kind: str
    svg: str  # filename under templates/gifts/
    width: int
    height: int
    dpi: int
    photo: bool


TEMPLATES: dict[str, GiftTemplate] = {
    # Mug wrap print area ≈ 2475 × 1155 px at 300 DPI.
    "mug_pattern": GiftTemplate(
        template_id="mug_pattern",
        product_kind="mug",
        svg="mug_pattern.svg.j2",
        width=2475,
        height=1155,
        dpi=300,
        photo=True,
    ),
    "mug_stats": GiftTemplate(
        template_id="mug_stats",
        product_kind="mug",
        svg="mug_stats.svg.j2",
        width=2475,
        height=1155,
        dpi=300,
        photo=False,
    ),
    # 5×7 in card at 300 DPI = 1500 × 2100 px (portrait).
    "card_classic": GiftTemplate(
        template_id="card_classic",
        product_kind="birth_announcement_cards",
        svg="card_classic.svg.j2",
        width=1500,
        height=2100,
        dpi=300,
        photo=True,
    ),
}


def get(template_id: str) -> GiftTemplate | None:
    return TEMPLATES.get(template_id)


def for_product(product_kind: str) -> list[GiftTemplate]:
    return [t for t in TEMPLATES.values() if t.product_kind == product_kind]
