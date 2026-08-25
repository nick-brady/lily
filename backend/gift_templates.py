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

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class GiftTemplate:
    template_id: str
    product_kind: str
    svg: str  # filename under templates/gifts/
    width: int
    height: int
    dpi: int
    photo: bool  # this design shows a photo of the baby
    # Whether it can render *without* one. `card_welcome` can't — it's a
    # full-bleed hero in a keyline mat, so removing the photo leaves an empty
    # framed box. Designs where the photo is an accent render fine without it,
    # and only those offer "remove" in the picker.
    photo_required: bool = False
    # Where the photo sits in the artwork, as a fraction of the canvas
    # (cx, cy, r). The editor lays a "change photo" hotspot over exactly this
    # spot, so you click her face on the design instead of a link in a list.
    # Fractions rather than pixels: the client is looking at a scaled image.
    photo_spot: tuple[float, float, float] | None = None
    # Text slots a parent may edit on this design, by key. Deliberately short:
    # everything else on a keepsake is derived from the birth, and "97
    # CONTRACTIONS · 26H 56M" is a fact — making it a text field would invite
    # someone to type a number that isn't true, which is the one thing these
    # are for. The name can be shortened to the one people actually use, and
    # anything else they want to say goes on a line that was always theirs.
    editable_text: tuple[str, ...] = ()
    # How many photo panels this design carries (the filmstrip templates).
    # Each is separately replaceable in the editor; 0 means the design has no
    # panels and any single photo goes through `photo` above instead.
    photo_slots: int = 0
    # How much room each set line has, keyed by slot: (width with a photo
    # beside it, width without). Per line, not per template — the photo only
    # crowds the lines level with it. On the mug it sits across the name but
    # ends well above the parent's own line, which therefore gets the whole
    # width whether the photo is there or not.
    text_widths: dict[str, tuple[float, float]] | None = None
    # Another template whose artwork fills this one, fitted and centred with
    # the theme background around it. This is how the framed prints work:
    # the card designs are already drawn, and a frame is a bigger sheet with
    # the same picture on it. Vector stays crisp at any size; only embedded
    # photos need more pixels, and the renderer scales their budget.
    inner: str | None = None
    # Where on the sheet the design must land, as fractions (x, y, w, h).
    # None means the whole sheet. The matted frames need it: the 12×16 sheet
    # shows through a mat opening of roughly 7.5×11.5 in, measured off a
    # mockup of an inch grid — so the design fits a 7×11 box in the middle
    # and the rest is page colour under the mat.
    safe_box: tuple[float, float, float, float] | None = None
    scene: str | None = None  # richer data scene: "hours" | "story" | None
    # center of the labor clock, for scene == "hours" (defaults to canvas center)
    clock_cx: float | None = None
    clock_cy: float | None = None


TEMPLATES: dict[str, GiftTemplate] = {
    # ── mugs — wrap print area ≈ 2475 × 1155 px at 300 DPI ────────────────
    # The labor clock on one face, name, one quiet data line and her picture
    # on the other. The right third of the wrap was empty.
    "mug_hours": GiftTemplate(
        template_id="mug_hours",
        product_kind="mug",
        svg="mug_hours.svg.j2",
        width=2475,
        height=1155,
        dpi=300,
        photo=True,
        photo_spot=(2235 / 2475, 490 / 1155, 150 / 2475),
        editable_text=("child_name", "custom_line"),
        text_widths={"child_name": (673, 1025), "custom_line": (1025, 1025)},
        scene="hours",
        clock_cx=640,
        clock_cy=577,
    ),
    # The guessing jar: everyone's guesses vs. what actually happened — the
    # winner's trophy mug.
    "mug_pool": GiftTemplate(
        template_id="mug_pool",
        product_kind="mug",
        svg="mug_pool.svg.j2",
        width=2475,
        height=1155,
        dpi=300,
        photo=False,
        scene="pool",
    ),
    # The reel: the day as a filmstrip — rotating the mug plays the story.
    "mug_reel": GiftTemplate(
        template_id="mug_reel",
        product_kind="mug",
        svg="mug_reel.svg.j2",
        width=2475,
        height=1155,
        dpi=300,
        photo=False,
        photo_slots=4,
        scene="reel",
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
        photo_spot=(320 / 1500, 1700 / 2100, 150 / 1500),
        editable_text=("child_name", "custom_line"),
        text_widths={"child_name": (850, 1320), "custom_line": (850, 1320)},
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
    # The reel, read downward: a photo essay of the day.
    "card_reel": GiftTemplate(
        template_id="card_reel",
        product_kind="birth_announcement_cards",
        svg="card_reel.svg.j2",
        width=1500,
        height=2100,
        dpi=300,
        photo=False,
        photo_slots=3,
        scene="reel",
    ),
    # The guessing-jar leaderboard as a keepsake card.
    "card_pool": GiftTemplate(
        template_id="card_pool",
        product_kind="birth_announcement_cards",
        svg="card_pool.svg.j2",
        width=1500,
        height=2100,
        dpi=300,
        photo=False,
        scene="pool",
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
        # The hero panel, not a circle — the spot is a hit area, and a
        # generous one over a full-bleed photo is exactly right.
        photo_spot=(0.5, 660 / 2100, 0.42),
        # The photo *is* this design — without one it's an empty keyline mat.
        photo_required=True,
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


# ── framed prints — 12×16 in at 300 DPI = 3600 × 4800 px (portrait) ────
# The same three designs as the mug, on a matted framed poster. Each wraps a
# card design rather than redrawing it, fitted to the mat's opening; the theme
# background fills the rest of the sheet, which the mat covers.
def _framed(template_id: str, inner: str) -> GiftTemplate:
    base = TEMPLATES[inner]
    return replace(
        base,
        template_id=template_id,
        product_kind="framed_print",
        width=3600,
        height=4800,
        inner=inner,
        safe_box=(2.5 / 12, 2.5 / 16, 7 / 12, 11 / 16),
    )


for _fid, _inner in (
    ("frame_hours", "card_hours_photo"),
    ("frame_reel", "card_reel"),
    ("frame_pool", "card_pool"),
):
    TEMPLATES[_fid] = _framed(_fid, _inner)


def get(template_id: str) -> GiftTemplate | None:
    return TEMPLATES.get(template_id)


def for_product(product_kind: str) -> list[GiftTemplate]:
    return [t for t in TEMPLATES.values() if t.product_kind == product_kind]
