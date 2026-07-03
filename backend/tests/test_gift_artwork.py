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
    if template.scene == "hours":
        ctx.update(
            gift_artwork.build_hours_clock(
                durations=durations,
                offsets_seconds=_OFFSETS,
                first_contraction_at=_FIRST_AT,
                born_at=_BORN_AT,
                cx=template.clock_cx or template.width / 2,
                cy=template.clock_cy or template.height / 2,
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
