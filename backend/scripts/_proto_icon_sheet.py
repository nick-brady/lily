"""PROTOTYPE — contact sheet of the milestone marks.

Draws every glyph at the size it actually prints on the mug, beside a 4x
blow-up, so they can be judged as marks rather than hunted for in the dial.

    docker compose run --rm --no-deps backend python scripts/_proto_icon_sheet.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cairosvg  # noqa: E402

import gift_themes  # noqa: E402
import _proto_day_rings as proto  # noqa: E402

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

R_TRUE = 13          # the size they're drawn at on the mug
BLOW = 4             # magnification for the second column
ROW_H = 132
W = 980
PAD = 60


def mark(kind: str, mx: float, my: float, r: float, p) -> str:
    if kind == "born":
        return proto._stroked(proto._heart_path(mx, my, r * 18 / 13), p.accent, 3.0 * r / 13)
    if kind in proto.GLYPH_MARKUP:
        return proto.GLYPH_MARKUP[kind](mx, my, r, p.accent)
    d = proto.GLYPHS.get(kind, proto._sparkle_path)(mx, my, r)
    if kind in proto.HOLLOW:
        return proto._stroked(d, p.accent, proto.STROKE * r / 13)
    return f'<path d="{d}" fill="{p.accent}" opacity="0.85"/>'


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
        out.append(mark(kind, PAD + 40, cy, R_TRUE, p))
        out.append(mark(kind, PAD + 200, cy, R_TRUE * BLOW, p))
        out.append(
            f'<text x="{PAD + 420}" y="{cy + 9:.0f}" font-family="{p.body_font}" '
            f'font-size="26" letter-spacing="3" fill="{p.ink}" opacity="0.7">{label}</text>'
        )
    out.append("</svg>")

    path = proto.OUT / "_icons.png"
    path.write_bytes(
        cairosvg.svg2png(bytestring="".join(out).encode(), output_width=W, output_height=h)
    )
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
