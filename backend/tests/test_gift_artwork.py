"""Render each gift template to a PNG and assert it's valid and exactly the
template's print dimensions. Exercises the Jinja SVG + cairosvg + font path
without a DB or S3 (a small Pillow PNG stands in for photos).
"""
from __future__ import annotations

import base64
import io
from datetime import datetime, timedelta

import pytest
from PIL import Image

import gift_artwork
import gift_themes
from gift_templates import TEMPLATES


def _stub_photo_uri() -> str:
    """A small but valid PNG as a stand-in hero photo, built with Pillow."""
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (180, 140, 200)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


_PIXEL = _stub_photo_uri()

_FIRST_AT = datetime(2026, 6, 1, 19, 4)
_BORN_AT = _FIRST_AT + timedelta(hours=9, minutes=38)
_DURATIONS = [45 + (i * 7) % 50 for i in range(40)]
_OFFSETS = [i * 14 * 60 for i in range(40)]


def _context(template):
    durations = _DURATIONS
    spark_last = gift_artwork._spark_last(durations)
    ctx = {
        "w": template.width,
        "h": template.height,
        "p": gift_themes.for_theme("lily"),
        "child_name": "Lily Wren",
        "birth_date": "June 1, 2026",
        "birth_time": "4:42 am",
        "count": len(durations),
        "labor_duration": "9h 38m",
        "avg_contraction": "1m 02s",
        "avg_interval": "5.0 min",
        "has_sparkline": True,
        "spark_path": gift_artwork._spark_path(durations),
        "spark_area_path": gift_artwork._spark_area_path(durations),
        "spark_last_x": spark_last[0],
        "spark_last_y": spark_last[1],
        "labor_start_time": "7:04 pm",
        "photo_data_uri": _PIXEL if template.photo else None,
    }
    if template.scene in ("hours", "hours_photo", "orbit"):
        ctx["clock_cx"] = template.clock_cx or template.width / 2
        ctx["clock_cy"] = template.clock_cy or template.height / 2
    if template.scene in ("hours", "hours_photo"):
        ctx.update(
            gift_artwork.build_hours_clock(
                durations=durations,
                offsets_seconds=_OFFSETS,
                first_contraction_at=_FIRST_AT,
                born_at=_BORN_AT,
                cx=ctx["clock_cx"],
                cy=ctx["clock_cy"],
                **gift_artwork.CLOCK_PRESETS[template.scene],
            )
        )
        ctx["clock_photo_r"] = gift_artwork.CLOCK_PHOTO_R
    elif template.scene == "orbit":
        ctx.update(
            gift_artwork.build_orbit_scene(
                [
                    {"uri": _PIXEL, "occurred_at": _FIRST_AT + timedelta(hours=2)},
                    {"uri": _PIXEL, "occurred_at": _FIRST_AT + timedelta(hours=2, minutes=5)},
                    {"uri": _PIXEL, "occurred_at": _FIRST_AT + timedelta(hours=8)},
                ],
                durations=durations,
                offsets_seconds=_OFFSETS,
                first_contraction_at=_FIRST_AT,
                born_at=_BORN_AT,
                cx=ctx["clock_cx"],
                cy=ctx["clock_cy"],
            )
        )
    elif template.scene == "words":
        ctx.update(
            gift_artwork.build_words_scene(
                [
                    {"body": "She is absolutely perfect. Welcome to the world!", "who": "Janet", "when": "4:31 am"},
                    {"body": "So proud of you both.", "who": "Lisa", "when": "9:02 am"},
                ],
                width=template.width,
                height=template.height,
                reactions_total=12,
            )
        )
    elif template.scene == "pool":
        ctx.update(
            gift_artwork.build_pool_scene(
                [
                    {"name": "Janet", "weight_lbs": 8.4375, "length_in": 20.5},
                    {"name": "Lisa", "weight_lbs": 7.5, "length_in": None},
                    {"name": "Marco", "weight_lbs": None, "length_in": None},
                ],
                actual_weight_lbs=8.4375,
                actual_length_in=20.5,
                child_name="Lily Wren",
                layout="mug" if template.product_kind == "mug" else "card",
            )
        )
    elif template.scene == "reel":
        ctx.update(
            gift_artwork.build_reel_scene(
                [
                    {"uri": _PIXEL, "caption": "first signs", "occurred_at": _FIRST_AT},
                    {"uri": _PIXEL, "caption": "she's here", "occurred_at": _BORN_AT},
                ],
                width=template.width,
                height=template.height,
                layout="mug" if template.product_kind == "mug" else "card",
            )
        )
    elif template.scene == "story":
        scene = gift_artwork.build_story_scene(
            [
                {"uri": _PIXEL, "caption": "first look"},
                {"uri": _PIXEL, "caption": "so loved"},
            ],
            width=template.width,
            height=template.height,
        )
        scene["reaction_summary"] = "12 reactions · 3 notes"
        scene["notes"] = ["yay!", "welcome, little one"]
        ctx.update(scene)
    return ctx


@pytest.mark.parametrize("template_id", list(TEMPLATES))
def test_template_renders_to_exact_png(template_id):
    template = TEMPLATES[template_id]
    png = gift_artwork.render_context(template, _context(template))

    assert png[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    img = Image.open(io.BytesIO(png))
    assert img.size == (template.width, template.height)


@pytest.mark.parametrize("template_id", list(TEMPLATES))
def test_template_renders_without_sparkline(template_id):
    """Births with <2 contractions have no sparkline; templates must still
    render."""
    template = TEMPLATES[template_id]
    ctx = _context(template)
    ctx.update(has_sparkline=False, spark_path="", spark_area_path="")
    png = gift_artwork.render_context(template, ctx)
    assert Image.open(io.BytesIO(png)).size == (template.width, template.height)


def test_sparkline_geometry():
    pts = gift_artwork._spark_xy([60, 90, 30])
    assert len(pts) == 3
    assert pts[0][0] == 0 and pts[-1][0] == gift_artwork._SPARK_W
    # tallest duration (90) sits highest = smallest y; shortest (30) lowest
    ys = [y for _, y in pts]
    assert ys[1] == min(ys)
    assert ys[2] == max(ys)


def test_sparkline_resamples_long_series():
    pts = gift_artwork._spark_xy(list(range(200)))
    assert len(pts) == gift_artwork._SPARK_MAX_POINTS


def test_sparkline_empty_for_short_series():
    assert gift_artwork._spark_xy([60]) == []
    assert gift_artwork._spark_path([]) == ""


def _clock(durations, offsets, first_at=_FIRST_AT, born_at=_BORN_AT, **kw):
    return gift_artwork.build_hours_clock(
        durations=durations,
        offsets_seconds=offsets,
        first_contraction_at=first_at,
        born_at=born_at,
        cx=750,
        cy=940,
        **kw,
    )


def test_hours_clock_one_day_is_one_ring():
    clock = _clock(_DURATIONS, _OFFSETS)
    assert len(clock["clock_rings"]) == 1
    assert len(clock["clock_rings"][0]["strokes"]) == len(_DURATIONS)
    assert clock["clock_born_mark"] is not None
    # a single day doesn't name itself
    assert clock["clock_day_labels"] is False
    # the face declares itself a clock
    assert [n["t"] for n in clock["clock_numerals"]] == ["12", "3", "6", "9"]


def test_hours_clock_rings_follow_the_days():
    """One ring per day of labor, newest outermost, and past three the oldest
    fold inward rather than being dropped."""
    for days, expected in ((1, 1), (2, 2), (3, 3), (5, 3)):
        offsets = [i * 3600 for i in range(days * 24)]
        durations = [60] * len(offsets)
        rings = _clock(durations, offsets)["clock_rings"]
        assert len(rings) == expected, days
        # every contraction lands on a ring, whatever the fold
        assert sum(len(r["strokes"]) for r in rings) == len(offsets)
        # rings nest outward and never touch
        bases = [r["base"] for r in rings]
        assert bases == sorted(bases)

    # beyond three days the innermost stops claiming to be day one
    labels = [r["label"] for r in _clock([60] * 120, [i * 3600 for i in range(120)])["clock_rings"]]
    assert labels[0] == "EARLIER"


def test_hours_clock_keeps_clock_angles_past_twelve_hours():
    """The old geometry silently stopped meaning clock time past 11h31m and
    swept the strokes linearly instead. A moment's angle is now its angle on
    the face however long the labor ran."""
    long_offsets = [0, 30 * 3600]
    clock = _clock([60, 60], long_offsets)
    first, last = (s for r in clock["clock_rings"] for s in r["strokes"])
    # 30h apart is 6h on a 12-hour face — a quarter turn, not a full sweep
    import math

    def angle(s):
        return math.atan2(s["y1"] - 940, s["x1"] - 750)

    gap = abs((angle(last) - angle(first) + math.pi) % (2 * math.pi) - math.pi)
    assert abs(gap - math.pi) < 0.05


def test_hours_clock_am_and_pm_are_told_apart():
    # 8am and 8pm, same day
    morning = _FIRST_AT.replace(hour=8, minute=0)
    clock = _clock([60, 60], [0, 12 * 3600], first_at=morning)
    strokes = [s for r in clock["clock_rings"] for s in r["strokes"]]
    assert [s["am"] for s in strokes] == [True, False]
    assert strokes[0]["w"] < strokes[1]["w"]      # AM finer
    assert strokes[0]["o"] < strokes[1]["o"]      # AM paler


def test_orbit_thumbs_keep_min_separation():
    import math

    # two photos five minutes apart would overlap without the nudge
    scene = gift_artwork.build_orbit_scene(
        [
            {"uri": _PIXEL, "occurred_at": _FIRST_AT + timedelta(hours=2)},
            {"uri": _PIXEL, "occurred_at": _FIRST_AT + timedelta(hours=2, minutes=5)},
        ],
        durations=_DURATIONS,
        offsets_seconds=_OFFSETS,
        first_contraction_at=_FIRST_AT,
        born_at=_BORN_AT,
        cx=750,
        cy=920,
    )
    a, b = scene["orbit_thumbs"]
    dist = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
    assert dist >= 2 * gift_artwork._ORBIT_THUMB_R


def test_wrap_respects_width_and_line_cap():
    lines = gift_artwork._wrap(
        "We have been waiting so long to meet you sweet girl and we love you", 24
    )
    assert len(lines) == 2
    assert all(len(line) <= 24 for line in lines)
    assert lines[-1].endswith("…")
    assert gift_artwork._wrap("short", 40) == ["short"]


def test_reel_panels_fill_their_region():
    photos = [
        {"uri": _PIXEL, "caption": f"c{i}", "occurred_at": _FIRST_AT + timedelta(hours=i)}
        for i in range(6)
    ]
    mug = gift_artwork.build_reel_scene(photos, width=2475, height=1155, layout="mug")
    assert len(mug["reel_panels"]) == 4  # capped and evenly sampled
    last = mug["reel_panels"][-1]
    assert last["x"] + last["w"] == pytest.approx(2475, abs=1)
    # chronological order preserved, first and last photos kept
    assert mug["reel_panels"][0]["caption"] == "c0"
    assert last["caption"] == "c5"

    card = gift_artwork.build_reel_scene(photos, width=1500, height=2100, layout="card")
    assert len(card["reel_panels"]) == 3
    bottom = card["reel_panels"][-1]
    assert bottom["y"] + bottom["h"] <= card["reel_band_y"]


def test_pool_scoring_and_formats():
    scene = gift_artwork.build_pool_scene(
        [
            {"name": "Papa", "weight_lbs": 9.6, "length_in": 21.3},
            {"name": "Jena", "weight_lbs": 8.4375, "length_in": None},
            {"name": "Shrug", "weight_lbs": None, "length_in": None},
        ],
        actual_weight_lbs=8.4375,
        actual_length_in=20.5,
        child_name="Lily",
        layout="card",
    )
    rows = scene["pool_rows"]
    # exact weight guess wins; the guessless entry sinks to the bottom
    assert rows[0]["name"] == "Jena" and rows[0]["winner"]
    assert rows[-1]["name"] == "Shrug" and rows[-1]["guess"] == "—"
    assert rows[0]["guess"] == "8 lbs 7 oz"
    assert scene["pool_actual"]["guess"] == "8 lbs 7 oz · 20.5 in"
    assert scene["pool_winner"] == "Jena"
    # ruler covers all weights and stars the actual
    assert scene["pool_ruler"] is not None
    assert len(scene["pool_ruler"]["dots"]) == 2


def test_lbs_oz_carry():
    assert gift_artwork._fmt_lbs_oz(7.99) == "8 lbs"  # 15.84 oz rounds up and carries
    assert gift_artwork._fmt_lbs_oz(8.0) == "8 lbs"
    assert gift_artwork._fmt_lbs_oz(7.75) == "7 lbs 12 oz"


def test_localize_converts_aware_and_passes_naive():
    from datetime import timezone

    utc = datetime(2026, 4, 10, 14, 54, tzinfo=timezone.utc)
    local = gift_artwork._localize(utc)
    # America/New_York in April is EDT (UTC-4): 14:54 UTC → 10:54 am
    assert gift_artwork._fmt_time(local) == "10:54 am"
    naive = datetime(2026, 4, 10, 14, 54)
    assert gift_artwork._localize(naive) is naive
    assert gift_artwork._localize(None) is None


def test_hours_clock_handles_missing_times():
    clock = gift_artwork.build_hours_clock(
        durations=[],
        offsets_seconds=[],
        first_contraction_at=None,
        born_at=None,
        cx=100,
        cy=100,
    )
    assert clock["clock_rings"] == [
        {"base": clock["clock_rings"][0]["base"], "label": "DAY 1", "strokes": []}
    ]
    assert clock["clock_born_mark"] is None
    assert clock["clock_marks"] == []


# ── per-design photos ────────────────────────────────────────────────────
# The photo on a keepsake is chosen per design, Shutterfly-style: you're
# editing this mug, not every keepsake at once. Three states, because "guess
# for me, but let me override" needs all three.


class _FakeRendering:
    def __init__(self, media_id=None, removed=False):
        self.photo_media_id = media_id
        self.photo_removed = removed


class _FakeAsset:
    def __init__(self, ident):
        self.id = ident
        self.archived_at = None


class _FakeDB:
    """Just enough session for `_photo_for` — it only ever does a `get`."""

    def __init__(self, assets=None):
        self._assets = assets or {}

    def get(self, _model, ident):
        return self._assets.get(ident)


def test_photo_choice_falls_back_to_the_guess(monkeypatch):
    """Nothing chosen means we still show something — a keepsake shouldn't be
    blank while it waits for someone to have an opinion."""
    guess = _FakeAsset("guessed")
    monkeypatch.setattr(gift_artwork, "_select_hero_photo", lambda db, birth: guess)
    template = TEMPLATES["mug_hours"]

    assert gift_artwork._photo_for(_FakeDB(), None, template, None) is guess
    assert (
        gift_artwork._photo_for(_FakeDB(), None, template, _FakeRendering()) is guess
    )


def test_photo_choice_uses_the_chosen_photo(monkeypatch):
    guess = _FakeAsset("guessed")
    chosen = _FakeAsset("chosen")
    monkeypatch.setattr(gift_artwork, "_select_hero_photo", lambda db, birth: guess)
    db = _FakeDB({"chosen": chosen})

    got = gift_artwork._photo_for(
        db, None, TEMPLATES["mug_hours"], _FakeRendering(media_id="chosen")
    )
    assert got is chosen


def test_photo_choice_survives_a_deleted_photo(monkeypatch):
    """A photo removed from the birth after it was chosen must not break the
    render — fall back to the guess rather than failing."""
    guess = _FakeAsset("guessed")
    monkeypatch.setattr(gift_artwork, "_select_hero_photo", lambda db, birth: guess)

    got = gift_artwork._photo_for(
        _FakeDB(), None, TEMPLATES["mug_hours"], _FakeRendering(media_id="gone")
    )
    assert got is guess


def test_removal_is_honoured_only_where_the_design_survives_it(monkeypatch):
    """`card_welcome` is a full-bleed hero in a keyline mat — without a photo
    it's an empty frame, so a removal flag there falls back to the guess
    instead of rendering nothing."""
    guess = _FakeAsset("guessed")
    monkeypatch.setattr(gift_artwork, "_select_hero_photo", lambda db, birth: guess)
    removed = _FakeRendering(removed=True)

    assert TEMPLATES["mug_hours"].photo_required is False
    assert gift_artwork._photo_for(_FakeDB(), None, TEMPLATES["mug_hours"], removed) is None

    assert TEMPLATES["card_welcome"].photo_required is True
    assert (
        gift_artwork._photo_for(_FakeDB(), None, TEMPLATES["card_welcome"], removed)
        is guess
    )


@pytest.mark.parametrize("template_id", ["mug_hours", "card_hours_photo"])
def test_photo_optional_templates_render_without_one(template_id):
    """The designs that offer "remove" have to lay out around the absence."""
    template = TEMPLATES[template_id]
    ctx = _context(template)
    ctx["photo_data_uri"] = None
    png = gift_artwork.render_context(template, ctx)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# ── the mockup budget ────────────────────────────────────────────────────
# The fulfillment partner allows 2 mockups a minute for the whole store, so
# they're generated once per design and then only on request.


class _FakeRow:
    def __init__(self, status, key=None):
        self.mockup_status = status
        self.mockup_s3_key = key


def test_mockups_are_generated_once_then_only_on_request():
    from repositories.gifts import should_generate_mockup

    # the first render of a design — this is what fills the gallery
    assert should_generate_mockup(_FakeRow("none")) is True

    # every render after that leaves the partner alone
    assert should_generate_mockup(_FakeRow("ready", "k.png")) is False
    assert should_generate_mockup(_FakeRow("stale", "k.png")) is False
    assert should_generate_mockup(_FakeRow("pending")) is False
    assert should_generate_mockup(_FakeRow("failed")) is False

    # a row that claims "none" but already has a file is not a first render
    assert should_generate_mockup(_FakeRow("none", "k.png")) is False


def test_preview_scales_the_picture_not_the_canvas():
    """A preview must show the whole design, smaller — not a corner of it.

    Every coordinate in these SVGs is absolute at full size: the clock sits at
    cx=640 with a 460 radius, the name at x=1360. Shrinking the template's
    width/height shrinks the *viewBox*, which crops rather than scales, so
    previews have to go through cairosvg's output size instead.
    """
    from PIL import Image
    import io

    template = TEMPLATES["mug_hours"]
    ctx = _context(template)
    ctx["photo_data_uri"] = None

    full = Image.open(io.BytesIO(gift_artwork.render_context(template, ctx)))
    small = Image.open(
        io.BytesIO(gift_artwork.render_context(template, ctx, output_width=900))
    )

    assert full.size == (template.width, template.height)
    assert small.size[0] == 900
    # same picture, fewer pixels — the aspect ratio is the tell for a crop
    assert abs(small.size[0] / small.size[1] - full.size[0] / full.size[1]) < 0.01


# ── the product choice ───────────────────────────────────────────────────
# Which mug a design is for. It has to reach both the order and the charge:
# approving a mockup of a black 15oz and being shipped a white 11oz is the
# bug this closed.


def test_chosen_product_is_what_ships():
    from fulfillment import products as fp

    default = fp.default_for_product_kind("mug")
    assert fp.for_rendering(None, "mug") is default
    assert fp.for_rendering("black_glossy_15oz", "mug").key == "black_glossy_15oz"
    # a key we've since retired falls back rather than failing
    assert fp.for_rendering("no_such_mug", "mug") is default
    # a mug key can't leak into another kind — it falls back to that kind's
    # own default, which today is None: the shortlist is mugs only, so cards
    # have nothing mapped to fulfil them.
    assert fp.for_rendering("black_glossy_15oz", "birth_announcement_cards") is None


def test_only_the_default_mug_is_free():
    from fulfillment import products as fp

    default = fp.default_for_product_kind("mug")
    assert fp.surcharge_for(default.key) == 0
    assert fp.surcharge_for(None) == 0
    assert fp.surcharge_for("no_such_mug") == 0
    for key, product in fp.SHORTLIST.items():
        if key != default.key:
            assert fp.surcharge_for(key) == 300, key


def test_every_shortlist_product_is_profitable():
    """The surcharge exists so the bigger mugs don't eat the margin — this
    pins that none of them is sold below cost."""
    from fulfillment import products as fp

    item_price = 1800  # the Birth Story Mug's list price
    for product in fp.SHORTLIST.values():
        charged = item_price + product.surcharge_cents
        assert product.cost_cents > 0, product.key
        assert charged > product.cost_cents, product.key


def test_shortlist_products_have_a_blank_photo():
    """The chooser shows blank product photos so picking a mug costs no
    mockups. A missing one would silently render an empty tile."""
    from fulfillment import products as fp

    for product in fp.SHORTLIST.values():
        assert product.blank_image_url.startswith("https://"), product.key


def test_effective_photo_is_what_rendered_not_todays_guess():
    """The editor seeds its draft from the photo the artwork actually used.

    "Auto" is re-resolved on every render, so a draft that merely said "auto"
    let an unrelated edit — changing the mug, typing a letter — swap the
    picture underneath someone. This is the value that prevents it, and it
    must come from what rendered, never from re-running the guess.
    """

    class Row:
        def __init__(self, chosen=None, used=None):
            self.photo_media_id = chosen
            self.rendering_metadata = {"selected_media_id": used} if used else {}

    # an explicit choice wins
    assert gift_artwork.effective_photo_id(Row(chosen="chosen")) == "chosen"
    # on auto, it's whatever the artwork on screen was rendered with
    assert gift_artwork.effective_photo_id(Row(used="what-rendered")) == "what-rendered"
    # a design that has never rendered has nothing to pin
    assert gift_artwork.effective_photo_id(Row()) is None
    assert gift_artwork.effective_photo_id(None) is None


def test_long_names_shrink_instead_of_running_under_the_photo():
    """The artwork has no wrapping and no reflow, so a name that doesn't fit
    used to run straight under the photo beside it. Type is the only thing
    that can yield."""
    from gift_templates import TEMPLATES

    room, roomier = TEMPLATES["mug_hours"].text_widths["child_name"]

    # a short name keeps the size the design was drawn at
    assert gift_artwork.fit_name_size("Lily", room, 175, 46) == 175
    # a long one comes down
    small = gift_artwork.fit_name_size("Lily Wren Bradfsdf", room, 175, 46)
    assert small < 175
    # and it fits once it has
    assert gift_artwork._measure("Lily Wren Bradfsdf", small) <= room
    # taking the photo away gives it more room, not the same shrunk size
    assert gift_artwork.fit_name_size("Lily Wren Bradfsdf", roomier, 175, 46) > small
    # it only ever shrinks — nothing is scaled up to fill space
    assert gift_artwork.fit_name_size("Lily", roomier, 175, 46) == 175
    # and it stops at the floor rather than becoming unreadable
    assert gift_artwork.fit_name_size("M" * 40, room, 175, 46) == 46


def test_your_own_line_shrinks_as_far_as_it_has_to():
    """The name holds a floor so it never sets smaller than the date line
    under it. Your own line has no such duty — the guarantee that matters is
    that it never runs under the photo, at any length the field accepts."""
    from gift_templates import TEMPLATES

    for tid in ("mug_hours", "card_hours_photo"):
        room = min(TEMPLATES[tid].text_widths["custom_line"])
        for text in ("worth every hour", "W" * 80, "M" * 80, "e" * 80):
            size = gift_artwork.fit_name_size(text, room, 42, 10)
            assert gift_artwork._measure(text, size) <= room, (tid, text[:12])


def test_each_line_gets_the_room_it_actually_has():
    """A photo only crowds the lines level with it. On the mug it crosses the
    name and ends well above the parent's own line, so that line keeps the
    full width whether the photo is there or not — it was being shrunk to
    clear something that isn't beside it."""
    widths = TEMPLATES["mug_hours"].text_widths

    name_with, name_without = widths["child_name"]
    line_with, line_without = widths["custom_line"]

    assert name_with < name_without, "the photo has to crowd the name"
    assert line_with == line_without, "nothing sits beside the line below it"
    assert line_with == name_without, "so it gets the same width the name gets free"
