"""Framed prints: a card design composed onto a bigger sheet."""
from __future__ import annotations

import io

from PIL import Image

import gift_artwork
import gift_templates
import gift_themes
from fulfillment import products as fp


def test_the_frames_are_the_mug_designs():
    frames = [t.template_id for t in gift_templates.for_product("framed_print")]
    assert frames == ["frame_hours", "frame_reel", "frame_pool"]
    for t in map(gift_templates.get, frames):
        assert (t.width, t.height, t.dpi) == (3600, 4800, 300)  # 12×16 in
        inner = gift_templates.get(t.inner)
        # everything about *how* it's drawn is the card's
        assert (t.photo, t.editable_text, t.photo_slots, t.scene) == (
            inner.photo, inner.editable_text, inner.photo_slots, inner.scene
        )


def test_layout_of_a_frame_is_the_card_on_its_own_canvas():
    frame = gift_templates.get("frame_pool")
    layout = gift_artwork._layout_of(frame)
    assert (layout.width, layout.height) == (1500, 2100)
    assert layout.svg == gift_templates.get("card_pool").svg
    assert layout.template_id == "frame_pool"  # still knows what it is
    # a plain template is its own layout
    mug = gift_templates.get("mug_hours")
    assert gift_artwork._layout_of(mug) is mug


def test_the_sheet_is_filled_with_the_theme_background():
    """The card is 5:7 and the sheet is 3:4, so there's margin either side.
    It must be the theme's page colour, not white and not transparent —
    the mat covers most of it, and what peeks out should look like paper."""
    palette = gift_themes.for_theme("lily")
    # a tiny stand-in "design": solid accent so the paste is unmistakable
    art = Image.new("RGB", (150, 210), palette.accent)
    buf = io.BytesIO(); art.save(buf, format="PNG")
    layout = gift_templates.get("card_pool")
    sheet = gift_templates.get("frame_pool")
    out = gift_artwork._compose(buf.getvalue(), layout, sheet, palette.bg, 360, 480)
    im = Image.open(io.BytesIO(out)).convert("RGB")
    assert im.size == (360, 480)
    bg = tuple(int(palette.bg.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    accent = tuple(int(palette.accent.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    assert im.getpixel((5, 240)) == bg          # left margin: page colour
    assert im.getpixel((354, 240)) == bg        # right margin
    assert im.getpixel((180, 240)) == accent    # the design, centred


def test_one_frame_product_per_colour_and_all_the_same_price():
    frames = fp.for_product_kind("framed_print")
    assert [p.variant_id for p in frames] == [20256, 20257, 20258]
    assert {p.surcharge_cents for p in frames} == {0}
    assert fp.default_for_product_kind("framed_print").key == "frame_black_12x16"
    # a mug key can't be shipped as a frame
    assert fp.for_rendering("latte_mug", "framed_print").key == "frame_black_12x16"
