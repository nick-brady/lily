"""Render each gift template to a PNG and assert it's valid and exactly the
template's print dimensions. Exercises the Jinja SVG + cairosvg + font path
without a DB or S3 (a 1×1 transparent PNG stands in for the hero photo).
"""
from __future__ import annotations

import base64
import io

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


def _context(template):
    return {
        "w": template.width,
        "h": template.height,
        "p": gift_themes.for_theme("lily"),
        "child_name": "Lily Wren",
        "birth_date": "June 1, 2026",
        "birth_time": "8:42 AM",
        "count": 47,
        "labor_duration": "13h 24m",
        "avg_contraction": "1m 02s",
        "avg_interval": "5.0 min",
        "has_sparkline": True,
        "spark_line": "0,200 250,80 500,160 750,40 1000,120",
        "spark_area": "0,240 0,200 250,80 500,160 750,40 1000,120 1000,240",
        "photo_data_uri": _PIXEL if template.photo else None,
    }


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
    ctx.update(has_sparkline=False, spark_line="", spark_area="")
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


def test_sparkline_empty_for_short_series():
    assert gift_artwork._spark_xy([60]) == []
    assert gift_artwork._sparkline_polyline([]) == ""
