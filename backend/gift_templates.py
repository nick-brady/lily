"""Gift template registry.

A "template" is a code artifact (a Jinja2 SVG under templates/gifts/), keyed
by `template_id`. Each `gift_catalog_items.template_metadata.templates` lists
which template ids are valid for that product. Keeping templates in code (not
DB rows) matches the codebase ethos — a new design is a code change, not a
migration.

`dims` are the exact output pixels (≈300 DPI for the product's print area).
`photo=True` templates embed the auto-selected hero photo.

The collection ("The Hours") is designed as keepsakes first, data second:
the birth's real data drawn as art — a radial labor clock, a quiet horizon
line, a story path — set in Cormorant Garamond with Montserrat caps labels.
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
    photo: bool  # embed the single auto-selected hero photo
    scene: str | None = None  # richer data scene: "hours" | "story" | None
    # center of the labor clock, for scene == "hours" (defaults to canvas center)
    clock_cx: float | None = None
    clock_cy: float | None = None


TEMPLATES: dict[str, GiftTemplate] = {
    # ── mugs — wrap print area ≈ 2475 × 1155 px at 300 DPI ────────────────
    # The labor clock on one face, name and one quiet data line on the other.
    "mug_hours": GiftTemplate(
        template_id="mug_hours",
        product_kind="mug",
        svg="mug_hours.svg.j2",
        width=2475,
        height=1155,
        dpi=300,
        photo=False,
        scene="hours",
        clock_cx=640,
        clock_cy=577,
    ),
    # The labor clock with the hero photo at its center — the labor radiates
    # outward from the baby it produced.
    "mug_hours_photo": GiftTemplate(
        template_id="mug_hours_photo",
        product_kind="mug",
        svg="mug_hours_photo.svg.j2",
        width=2475,
        height=1155,
        dpi=300,
        photo=True,
        scene="hours_photo",
        clock_cx=640,
        clock_cy=577,
    ),
    # Hero photo with the contraction line wrapping the mug as a horizon.
    "mug_horizon": GiftTemplate(
        template_id="mug_horizon",
        product_kind="mug",
        svg="mug_horizon.svg.j2",
        width=2475,
        height=1155,
        dpi=300,
        photo=True,
    ),
    # ── cards — 5×7 in at 300 DPI = 1500 × 2100 px (portrait) ─────────────
    # The labor clock as an art print: the hours of labor around a clock
    # face, a star at the minute of birth.
    "card_hours": GiftTemplate(
        template_id="card_hours",
        product_kind="birth_announcement_cards",
        svg="card_hours.svg.j2",
        width=1500,
        height=2100,
        dpi=300,
        photo=False,
        scene="hours",
        clock_cx=750,
        clock_cy=940,
    ),
    # The labor clock with the hero photo at its center.
    "card_hours_photo": GiftTemplate(
        template_id="card_hours_photo",
        product_kind="birth_announcement_cards",
        svg="card_hours_photo.svg.j2",
        width=1500,
        height=2100,
        dpi=300,
        photo=True,
        scene="hours_photo",
        clock_cx=750,
        clock_cy=940,
    ),
    # The clock with the timeline's photos orbiting outside the ring, each
    # at the clock angle of the moment it was taken.
    "card_orbit": GiftTemplate(
        template_id="card_orbit",
        product_kind="birth_announcement_cards",
        svg="card_orbit.svg.j2",
        width=1500,
        height=2100,
        dpi=300,
        photo=False,
        scene="orbit",
        clock_cx=750,
        clock_cy=920,
    ),
    # The family's own comments as the artwork, with attribution.
    "card_words": GiftTemplate(
        template_id="card_words",
        product_kind="birth_announcement_cards",
        svg="card_words.svg.j2",
        width=1500,
        height=2100,
        dpi=300,
        photo=False,
        scene="words",
    ),
    # Classic photo announcement with the labor horizon beneath the name.
    "card_welcome": GiftTemplate(
        template_id="card_welcome",
        product_kind="birth_announcement_cards",
        svg="card_welcome.svg.j2",
        width=1500,
        height=2100,
        dpi=300,
        photo=True,
    ),
    # The story of the day: a thread rising from "where it began" through
    # Polaroid moments to a star, with the family's own words beneath.
    "card_story": GiftTemplate(
        template_id="card_story",
        product_kind="birth_announcement_cards",
        svg="card_story.svg.j2",
        width=1500,
        height=2100,
        dpi=300,
        photo=False,
        scene="story",
    ),
}


def get(template_id: str) -> GiftTemplate | None:
    return TEMPLATES.get(template_id)


def for_product(product_kind: str) -> list[GiftTemplate]:
    return [t for t in TEMPLATES.values() if t.product_kind == product_kind]
