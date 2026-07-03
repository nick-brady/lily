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


def test_hours_clock_star_and_strokes():
    clock = gift_artwork.build_hours_clock(
        durations=_DURATIONS,
        offsets_seconds=_OFFSETS,
        first_contraction_at=_FIRST_AT,
        born_at=_BORN_AT,
        cx=750,
        cy=940,
    )
    assert len(clock["clock_strokes"]) == len(_DURATIONS)
    assert clock["clock_star"] is not None
    assert clock["clock_start_dot"] is not None
    # opacity deepens as labor progresses
    opacities = [s["o"] for s in clock["clock_strokes"]]
    assert opacities == sorted(opacities)


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


def test_hours_clock_handles_missing_times():
    clock = gift_artwork.build_hours_clock(
        durations=[],
        offsets_seconds=[],
        first_contraction_at=None,
        born_at=None,
        cx=100,
        cy=100,
    )
    assert clock["clock_strokes"] == []
    assert clock["clock_star"] is None
    assert clock["clock_start_dot"] is None
