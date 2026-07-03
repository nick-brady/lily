"""Render every gift template with realistic fake data — no DB, no S3.

Dev/design tool: lets you iterate on the SVG templates and see actual pixels
without seeding a birth. Run inside the backend container (it has the bundled
fonts + cairo):

    docker compose run --rm --no-deps backend python scripts/render_gift_previews.py [theme ...]

Outputs PNGs to /app/preview_out/ (i.e. backend/preview_out/ on the host).
"""
from __future__ import annotations

import base64
import io
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

import gift_themes  # noqa: E402
from gift_artwork import (  # noqa: E402
    CLOCK_PHOTO_R,
    CLOCK_PRESETS,
    _fmt_date,
    _fmt_hms,
    _fmt_interval,
    _fmt_ms,
    _fmt_time,
    _spark_area_path,
    _spark_last,
    _spark_path,
    build_hours_clock,
    build_orbit_scene,
    build_story_scene,
    build_words_scene,
    render_context,
)
from gift_templates import TEMPLATES  # noqa: E402

OUT_DIR = Path("/app/preview_out")

rng = random.Random(42)

LABOR_START = datetime(2026, 6, 20, 18, 32)
BORN_AT = datetime(2026, 6, 21, 4, 12)


def fake_labor(n: int = 58) -> tuple[list[int], list[int]]:
    """(durations, offsets): contractions ramp ~45s → ~95s and arrive closer
    together as labor progresses, like the real thing."""
    total = int((BORN_AT - LABOR_START).total_seconds()) - 15 * 60
    # intervals shrink from ~18 min to ~4 min; normalize onto the labor span
    raw_gaps = [18 * 60 * (1 - 0.75 * i / (n - 1)) * rng.uniform(0.8, 1.2) for i in range(n - 1)]
    scale = total / sum(raw_gaps)
    offsets = [0]
    for g in raw_gaps:
        offsets.append(offsets[-1] + int(g * scale))
    durations = []
    for i in range(n):
        t = i / (n - 1)
        durations.append(int(45 + t * 50 + rng.gauss(0, 9)))
    return durations, offsets


def fake_photo(w: int = 900, h: int = 900, hue: tuple = (233, 213, 220)) -> str:
    """A soft gradient placeholder standing in for a baby photo."""
    im = Image.new("RGB", (w, h))
    top = hue
    bottom = (max(0, hue[0] - 60), max(0, hue[1] - 55), max(0, hue[2] - 45))
    px = im.load()
    for y in range(h):
        t = y / (h - 1)
        row = tuple(int(top[c] + t * (bottom[c] - top[c])) for c in range(3))
        for x in range(w):
            px[x, y] = row
    d = ImageDraw.Draw(im)
    # a vague sleeping-baby blob so the crop/framing reads
    d.ellipse((w * 0.30, h * 0.34, w * 0.70, h * 0.62), fill=(250, 244, 240))
    d.ellipse((w * 0.38, h * 0.55, w * 0.62, h * 0.80), fill=(246, 238, 232))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    durations, offsets = fake_labor()
    themes = sys.argv[1:] or ["lily"]

    hues = [(233, 213, 220), (214, 226, 235), (236, 228, 212), (222, 232, 222), (230, 220, 235)]
    captions = ["first signs", "heading in", "almost there", "she's here", "going home"]
    story_photos = [
        {
            "uri": fake_photo(hue=hues[i % len(hues)]),
            "caption": cap,
            # spread across the labor for the orbit placement
            "occurred_at": LABOR_START + (BORN_AT - LABOR_START) * ((i + 0.5) / len(captions)),
        }
        for i, cap in enumerate(captions)
    ]
    quotes = [
        {"body": "She's perfect. Welcome to the world, little one!", "who": "Janet", "when": "4:31 am"},
        {"body": "Crying at my desk. So proud of you, Sarah.", "who": "Lisa", "when": "9:02 am"},
        {"body": "We've been waiting for you, sweet girl.", "who": "Grandpa", "when": "11:11 am"},
    ]

    labor_seconds = int((BORN_AT - LABOR_START).total_seconds())
    spark_last = _spark_last(durations)

    for theme in themes:
        palette = gift_themes.for_theme(theme)
        for template in TEMPLATES.values():
            context = {
                "w": template.width,
                "h": template.height,
                "p": palette,
                "child_name": "Lily",
                "birth_date": _fmt_date(BORN_AT),
                "birth_time": _fmt_time(BORN_AT),
                "count": len(durations),
                "labor_duration": _fmt_hms(labor_seconds),
                "avg_contraction": _fmt_ms(sum(durations) / len(durations)),
                "avg_interval": _fmt_interval(offsets[-1] / (len(offsets) - 1)),
                "has_sparkline": True,
                "labor_start_time": _fmt_time(LABOR_START),
                "spark_path": _spark_path(durations),
                "spark_area_path": _spark_area_path(durations),
                "spark_last_x": spark_last[0] if spark_last else 0,
                "spark_last_y": spark_last[1] if spark_last else 0,
                "photo_data_uri": fake_photo() if template.photo else None,
            }
            if template.scene in ("hours", "hours_photo", "orbit"):
                context["clock_cx"] = template.clock_cx or template.width / 2
                context["clock_cy"] = template.clock_cy or template.height / 2
            if template.scene in ("hours", "hours_photo"):
                context.update(
                    build_hours_clock(
                        durations=durations,
                        offsets_seconds=offsets,
                        first_contraction_at=LABOR_START,
                        born_at=BORN_AT,
                        cx=context["clock_cx"],
                        cy=context["clock_cy"],
                        **CLOCK_PRESETS[template.scene],
                    )
                )
                context["clock_photo_r"] = CLOCK_PHOTO_R
            elif template.scene == "orbit":
                context.update(
                    build_orbit_scene(
                        story_photos,
                        durations=durations,
                        offsets_seconds=offsets,
                        first_contraction_at=LABOR_START,
                        born_at=BORN_AT,
                        cx=context["clock_cx"],
                        cy=context["clock_cy"],
                    )
                )
            elif template.scene == "story":
                scene = build_story_scene(
                    story_photos, width=template.width, height=template.height
                )
                scene["reaction_summary"] = "47 reactions · 12 notes"
                scene["notes"] = [
                    "She's perfect. Welcome, little one!",
                    "We can't wait to meet her.",
                ]
                context.update(scene)
            elif template.scene == "words":
                context.update(
                    build_words_scene(
                        quotes,
                        width=template.width,
                        height=template.height,
                        reactions_total=47,
                    )
                )
            png = render_context(template, context)
            out = OUT_DIR / f"{template.template_id}_{theme}.png"
            out.write_bytes(png)
            print(f"wrote {out} ({len(png) // 1024} KB)")


if __name__ == "__main__":
    main()
