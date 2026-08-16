"""Contact sheet of the milestone marks, drawn from the real registry.

Every mark at the size it actually prints on the artwork, beside a 4x
blow-up, so a new one can be judged as a mark rather than hunted for inside
the dial. Reads `gift_artwork` directly — if it renders here it renders on
the mug, and the sheet can't drift from what ships.

    docker compose run --rm --no-deps backend python scripts/_proto_icon_sheet.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cairosvg  # noqa: E402

import gift_artwork as art  # noqa: E402
import gift_themes  # noqa: E402

# `born` isn't in the registries — it's the heart, drawn larger, placed by
# build_hours_clock itself — so it's listed explicitly.
ROWS = [
    ("water_broke", "water broke"),
    ("arrived", "arrived"),
    ("active_labor", "active labor"),
    ("transition", "transition"),
    ("pushing", "pushing"),
    ("born", "born  ·  the arrival"),
    ("first_feed", "first feed"),
    ("going_home", "going home"),
]

BLOW = 4
ROW_H = 132
W = 980
PAD = 60


def mark_svg(kind: str, mx: float, my: float, scale: float, p) -> str:
    """One mark at `scale` x its true size, through the same code the
    artwork uses."""
    if kind == "born":
        d = art._heart_path(mx, my, art.BORN_MARK_R * scale)
        return (
            f'<path d="{d}" fill="none" stroke="{p.accent}" '
            f'stroke-width="{art.BORN_STROKE * scale}" stroke-linejoin="round" '
            f'stroke-linecap="round" opacity="0.9"/>'
        )
    if kind in art._ICON_GLYPHS:
        d, transform, rule = art._icon_transform(kind, mx, my, art.MARK_R * scale)
        return (
            f'<g transform="{transform}"><path d="{d}" fill="{p.accent}" '
            f'fill-rule="{rule}" opacity="0.85"/></g>'
        )
    d = art._STROKE_GLYPHS[kind](mx, my, art.MARK_R * scale)
    return (
        f'<path d="{d}" fill="none" stroke="{p.accent}" '
        f'stroke-width="{art.MARK_STROKE * scale}" stroke-linejoin="round" '
        f'stroke-linecap="round" opacity="0.9"/>'
    )


def main() -> None:
    p = gift_themes.for_theme("lily")
    h = PAD * 2 + ROW_H * len(ROWS)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
        f'viewBox="0 0 {W} {h}">',
        f'<rect width="{W}" height="{h}" fill="{p.bg}"/>',
        f'<text x="{PAD}" y="{PAD - 14}" font-family="{p.body_font}" font-size="22" '
        f'letter-spacing="4" fill="{p.ink}" opacity="0.45">'
        f'MILESTONE MARKS &#183; TRUE SIZE, THEN {BLOW}&#215;</text>',
    ]
    for i, (kind, label) in enumerate(ROWS):
        cy = PAD + ROW_H * i + ROW_H / 2
        out.append(
            f'<line x1="{PAD}" y1="{cy - ROW_H / 2:.0f}" x2="{W - PAD}" '
            f'y2="{cy - ROW_H / 2:.0f}" stroke="{p.ink}" stroke-width="1" opacity="0.10"/>'
        )
        out.append(mark_svg(kind, PAD + 40, cy, 1.0, p))
        out.append(mark_svg(kind, PAD + 200, cy, BLOW, p))
        out.append(
            f'<text x="{PAD + 420}" y="{cy + 9:.0f}" font-family="{p.body_font}" '
            f'font-size="26" letter-spacing="3" fill="{p.ink}" opacity="0.7">{label}</text>'
        )
    out.append("</svg>")

    outdir = Path("/app/preview_out")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "_icons.png"
    path.write_bytes(
        cairosvg.svg2png(bytestring="".join(out).encode(), output_width=W, output_height=h)
    )
    print(f"wrote {path}")

    unmarked = [
        k for k in ("first_hold", "name_announced", "other")
        if not art.has_mark(k)
    ]
    print("no mark by design:", ", ".join(unmarked))


if __name__ == "__main__":
    main()
