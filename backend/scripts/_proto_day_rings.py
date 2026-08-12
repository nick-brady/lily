"""PROTOTYPE — day-ring labor clock. Throwaway design tool, not wired in.

Renders mug_hours-shaped previews for several labor shapes so the ring
scheme can be judged as pixels instead of prose. Nothing here imports from
build_hours_clock; the geometry is re-derived locally so the production
path stays untouched until the design is settled.

    docker compose run --rm --no-deps backend python scripts/_proto_day_rings.py
"""
from __future__ import annotations

import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cairosvg  # noqa: E402

import gift_themes  # noqa: E402
from gift_artwork import (  # noqa: E402
    _droplet_path,
    _heart_path,
    _house_path,
    _sparkle_path,
)


# The production set has four shapes for ten milestone kinds, so half of them
# fall through to a generic diamond. Symbols can only replace words if every
# kind has its own, so these fill the gaps — flat, single-colour, legible at
# the ~30px they're drawn at.

def _sunrise_path(cx: float, cy: float, r: float) -> str:
    """A half-disc over a baseline (active labor — it's begun in earnest)."""
    return (
        f"M {cx - r:.1f},{cy + r * 0.35:.1f} "
        f"A {r:.1f},{r:.1f} 0 0 1 {cx + r:.1f},{cy + r * 0.35:.1f} Z "
        f"M {cx - r * 1.25:.1f},{cy + r * 0.62:.1f} "
        f"L {cx + r * 1.25:.1f},{cy + r * 0.62:.1f} "
        f"L {cx + r * 1.25:.1f},{cy + r * 0.86:.1f} "
        f"L {cx - r * 1.25:.1f},{cy + r * 0.86:.1f} Z"
    )


def _chevrons_path(cx: float, cy: float, r: float) -> str:
    """Two stacked chevrons driving outward (pushing)."""
    def one(dy: float) -> str:
        return (
            f"M {cx - r:.1f},{cy + dy + r * 0.34:.1f} "
            f"L {cx:.1f},{cy + dy - r * 0.32:.1f} "
            f"L {cx + r:.1f},{cy + dy + r * 0.34:.1f} "
            f"L {cx + r * 0.72:.1f},{cy + dy + r * 0.6:.1f} "
            f"L {cx:.1f},{cy + dy + r * 0.06:.1f} "
            f"L {cx - r * 0.72:.1f},{cy + dy + r * 0.6:.1f} Z"
        )
    return f"{one(-r * 0.42)} {one(r * 0.42)}"


def _wave_path(cx: float, cy: float, r: float) -> str:
    """A single swell (transition)."""
    return (
        f"M {cx - r:.1f},{cy + r * 0.2:.1f} "
        f"Q {cx - r * 0.5:.1f},{cy - r * 0.75:.1f} {cx:.1f},{cy + r * 0.1:.1f} "
        f"Q {cx + r * 0.5:.1f},{cy + r * 0.95:.1f} {cx + r:.1f},{cy - r * 0.1:.1f} "
        f"L {cx + r:.1f},{cy + r * 0.62:.1f} "
        f"Q {cx + r * 0.5:.1f},{cy + r * 1.5:.1f} {cx:.1f},{cy + r * 0.62:.1f} "
        f"Q {cx - r * 0.5:.1f},{cy - r * 0.2:.1f} {cx - r:.1f},{cy + r * 0.78:.1f} Z"
    )


GLYPHS = {
    "water_broke": _droplet_path,
    "arrived": _house_path,
    "going_home": _house_path,
    "first_hold": _heart_path,
    "first_feed": _heart_path,
    "active_labor": _sunrise_path,
    "transition": _wave_path,
    "pushing": _chevrons_path,
}

W, H = 2475, 1155
CX, CY = 640.0, 577.0
R_RING = 460.0          # the tick ring — fixed, so the dial never moves
R_OUT = 430.0           # furthest a ray tip may reach
R_INNER = {1: 205.0, 2: 120.0, 3: 90.0}
GAP = 14.0              # keeps rings from touching
# AM and PM separate on three cues at once — value, opacity and weight.
# Hue alone wasn't enough: the two theme pinks are close to begin with, and a
# shared alpha washed the deep one out until it matched the light one.
AM_ALPHA, PM_ALPHA = 0.34, 0.74
AM_WIDTH, PM_WIDTH = 2.6, 4.2
BUILD = 0.16            # late labor deepens, on top of the AM/PM tone
OUT = Path("/app/preview_out/proto")

rng = random.Random(7)


# ── sample labors ────────────────────────────────────────────────────────

def make_labor(start: datetime, born: datetime, n: int, *, pauses=()):
    """(datetimes, durations). Contractions ramp 45s→95s and crowd together
    toward the birth. `pauses` are (start_frac, end_frac) spans with no
    contractions — prodromal labor that stops overnight and resumes."""
    total = (born - start).total_seconds() - 900
    times, durs = [], []
    for i in range(n):
        f = i / max(n - 1, 1)
        # ease the offsets so they bunch up near the end
        f_eased = f ** 1.45
        if any(a <= f_eased <= b for a, b in pauses):
            continue
        t = start + timedelta(seconds=f_eased * total * rng.uniform(0.985, 1.015))
        times.append(t)
        durs.append(int((45 + 50 * f) * rng.uniform(0.85, 1.15)))
    return times, durs


def clock_angle(dt: datetime) -> float:
    secs = (dt.hour % 12) * 3600 + dt.minute * 60 + dt.second
    return (secs / (12 * 3600)) * 2 * math.pi - math.pi / 2


# ── ring geometry ────────────────────────────────────────────────────────

def build_rings(times: list[datetime], durs: list[int]):
    """Rolling 24h windows from the first contraction. Newest day lands on
    the outermost ring; anything past three days folds into the innermost so
    a long prodromal labor is compressed rather than dropped."""
    t0 = times[0]
    day_of = [int((t - t0).total_seconds()) // 86400 for t in times]
    total_days = max(day_of) + 1
    n = min(total_days, 3)
    shift = total_days - n

    r_in = R_INNER[n]
    band = (R_OUT - r_in) / n
    usable = band - (GAP if n > 1 else 0.0)
    lo, hi = min(durs), max(durs)
    span = (hi - lo) or 1

    rings = [{"base": r_in + k * band, "usable": usable, "strokes": []} for k in range(n)]
    total_secs = (times[-1] - t0).total_seconds() or 1
    for t, d, dd in zip(times, durs, day_of):
        k = max(0, dd - shift)
        ring = rings[k]
        a = clock_angle(t)
        length = 0.36 * usable + ((d - lo) / span) * (usable - 0.36 * usable)
        r0, r1 = ring["base"], ring["base"] + length
        am = t.hour < 12
        progress = (t - t0).total_seconds() / total_secs
        ring["strokes"].append({
            "x1": CX + r0 * math.cos(a), "y1": CY + r0 * math.sin(a),
            "x2": CX + r1 * math.cos(a), "y2": CY + r1 * math.sin(a),
            "am": am,
            "o": round((AM_ALPHA if am else PM_ALPHA) + BUILD * progress, 3),
        })

    for k, ring in enumerate(rings):
        if total_days > 3 and k == 0:
            ring["label"] = "EARLIER"
        else:
            ring["label"] = f"DAY {k + 1 + shift}"
    return rings, n, total_days, t0, shift


def ring_for(t: datetime, t0: datetime, shift: int, n: int) -> int:
    """Which day's ring a moment belongs on — same rolling-24h rule the
    contractions use, so a milestone lands on the day it happened."""
    d = int((t - t0).total_seconds()) // 86400
    return max(0, min(n - 1, d - shift))


# ── svg ──────────────────────────────────────────────────────────────────

def svg_for(times, durs, born, name, headline, milestones=()):
    p = gift_themes.for_theme("lily")
    rings, n, total_days, t0, shift = build_rings(times, durs)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{p.bg}"/>',
    ]

    star_a = clock_angle(born)

    # dial: 60 unbroken ticks
    for i in range(60):
        a = (i / 60) * 2 * math.pi - math.pi / 2
        hour = i % 5 == 0
        r0 = R_RING - (22 if hour else 10)
        out.append(
            f'<line x1="{CX + r0 * math.cos(a):.1f}" y1="{CY + r0 * math.sin(a):.1f}" '
            f'x2="{CX + R_RING * math.cos(a):.1f}" y2="{CY + R_RING * math.sin(a):.1f}" '
            f'stroke="{p.ink}" stroke-width="{3 if hour else 1.6}" '
            f'opacity="{0.38 if hour else 0.16}"/>'
        )

    # THE MARK: quiet numerals so the face declares itself a 12-hour clock
    for numeral, ang in (("12", -math.pi / 2), ("3", 0.0), ("6", math.pi / 2), ("9", math.pi)):
        nx, ny = CX + (R_RING + 46) * math.cos(ang), CY + (R_RING + 46) * math.sin(ang)
        out.append(
            f'<text x="{nx:.1f}" y="{ny + 13:.1f}" text-anchor="middle" '
            f'font-family="{p.body_font}" font-size="34" letter-spacing="2" '
            f'fill="{p.ink}" opacity="0.42">{numeral}</text>'
        )

    # the ground each day's rays stand on — the concentric circles that make
    # the bands read as separate days instead of one fuzzy burst, and the line
    # the milestones hang on. Drawn even for a single day, so the one-ring mug
    # has somewhere to put them too.
    for ring in rings:
        out.append(
            f'<circle cx="{CX}" cy="{CY}" r="{ring["base"]:.1f}" fill="none" '
            f'stroke="{p.ink}" stroke-width="1.4" opacity="0.13"/>'
        )

    # the rays, AM light+fine / PM deep+heavy, translucent so overlaps stack
    for ring in rings:
        for s in ring["strokes"]:
            out.append(
                f'<line x1="{s["x1"]:.1f}" y1="{s["y1"]:.1f}" '
                f'x2="{s["x2"]:.1f}" y2="{s["y2"]:.1f}" '
                f'stroke="{p.dot if s["am"] else p.accent}" '
                f'stroke-width="{AM_WIDTH if s["am"] else PM_WIDTH}" '
                f'stroke-linecap="round" opacity="{s["o"]}"/>'
            )

    # day labels at the base of each ring, on a small ground so a 6 o'clock
    # ray can't run through the type
    if n > 1:
        for ring in rings:
            ly = CY + ring["base"]
            out.append(
                f'<rect x="{CX - 62}" y="{ly - 19}" width="124" height="34" rx="17" '
                f'fill="{p.bg}" opacity="0.92"/>'
                f'<text x="{CX}" y="{ly + 4:.1f}" text-anchor="middle" '
                f'font-family="{p.body_font}" font-size="21" letter-spacing="3" '
                f'fill="{p.ink}" opacity="0.55">{ring["label"]}</text>'
            )

    # milestones ride the grey line of the day they happened on — inside the
    # dial, on the ring that already means that day, rather than floating off
    # the outside where nothing anchored them. They cross a few rays; a label
    # that lands where the story is beats one parked in empty space.
    for kind, t in milestones:
        k = ring_for(t, t0, shift, n)
        a = clock_angle(t)
        r = rings[k]["base"]
        mx, my = CX + r * math.cos(a), CY + r * math.sin(a)
        glyph = GLYPHS.get(kind, _sparkle_path)
        # a ground of page colour so the mark reads clear of the rays it
        # crosses — the symbol has to survive without a label to lean on
        out.append(
            f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="26" fill="{p.bg}" opacity="0.9"/>'
            f'<path d="{glyph(mx, my, 16)}" fill="{p.accent}" opacity="0.85"/>'
        )

    # the birth — a heart, on the grey line with the rest. A sparkle is an
    # ornament; this is the one mark on the mug that is a person.
    r_star = rings[-1]["base"]
    sx, sy = CX + r_star * math.cos(star_a), CY + r_star * math.sin(star_a)
    out.append(
        f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="32" fill="{p.bg}" opacity="0.9"/>'
        f'<path d="{_heart_path(sx, sy, 22)}" fill="{p.accent}"/>'
    )

    # right face — name, date, and the AM/PM key
    out.append(
        f'<text x="1360" y="500" font-family="{p.display_font}" font-size="175" '
        f'font-weight="300" font-style="italic" fill="{p.ink}">{name}</text>'
        f'<text x="1366" y="600" font-family="{p.body_font}" font-size="38" '
        f'letter-spacing="2" fill="{p.ink}" opacity="0.62">'
        f'born {born.strftime("%B %-d, %Y")} at {born.strftime("%-I:%M %p").lower()}</text>'
        f'<line x1="1366" y1="690" x2="1526" y2="690" stroke="{p.ink}" '
        f'stroke-width="2" opacity="0.25"/>'
        f'<text x="1366" y="775" font-family="{p.body_font}" font-size="29" '
        f'letter-spacing="5" fill="{p.ink}" opacity="0.5">{headline}</text>'
    )
    # the key: one ray is one contraction, and what the two tones mean
    out.append(
        f'<line x1="1368" y1="862" x2="1368" y2="898" stroke="{p.dot}" '
        f'stroke-width="{AM_WIDTH}" stroke-linecap="round" opacity="{AM_ALPHA}"/>'
        f'<text x="1392" y="892" font-family="{p.body_font}" font-size="26" '
        f'letter-spacing="3" fill="{p.ink}" opacity="0.5">AM</text>'
        f'<line x1="1476" y1="862" x2="1476" y2="898" stroke="{p.accent}" '
        f'stroke-width="{PM_WIDTH}" stroke-linecap="round" opacity="{PM_ALPHA}"/>'
        f'<text x="1500" y="892" font-family="{p.body_font}" font-size="26" '
        f'letter-spacing="3" fill="{p.ink}" opacity="0.5">PM</text>'
    )

    out.append("</svg>")
    return "".join(out), n, total_days


SCENES = [
    # (key, first contraction, birth, n contractions, pauses)
    ("1_evening", datetime(2026, 6, 20, 18, 32), datetime(2026, 6, 21, 4, 12), 58, ()),
    ("1_fast", datetime(2026, 6, 21, 1, 40), datetime(2026, 6, 21, 4, 12), 20, ()),
    ("1_longday", datetime(2026, 6, 20, 8, 5), datetime(2026, 6, 21, 0, 40), 84, ()),
    ("2_day", datetime(2026, 6, 19, 21, 5), datetime(2026, 6, 21, 4, 12), 120, ((0.30, 0.52),)),
    ("3_day", datetime(2026, 6, 18, 14, 20), datetime(2026, 6, 21, 4, 12), 165, ((0.18, 0.33), (0.52, 0.66))),
    ("5_day", datetime(2026, 6, 16, 9, 0), datetime(2026, 6, 21, 4, 12), 210, ((0.15, 0.28), (0.40, 0.52), (0.63, 0.72))),
]


def make_milestones(start: datetime, born: datetime):
    """A plausible set — one early marker on long labors so a multi-day mug
    has something on its inner rings, then the three near the birth."""
    ms = []
    if born - start > timedelta(hours=20):
        ms.append(("active_labor", start + timedelta(hours=2)))
    ms += [
        ("water_broke", born - timedelta(hours=6)),
        ("arrived", born - timedelta(hours=4)),
        ("transition", born - timedelta(hours=2, minutes=30)),
        ("pushing", born - timedelta(minutes=40)),
    ]
    return ms


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, start, born, n, pauses in SCENES:
        times, durs = make_labor(start, born, n, pauses=pauses)
        hours = (born - start).total_seconds() / 3600
        span = f"{int(hours // 24)}D {int(hours % 24)}H" if hours >= 24 else f"{int(hours)}H {int(hours % 1 * 60)}M"
        headline = f"{len(times)} CONTRACTIONS · {span}"
        svg, rings, days = svg_for(
            times, durs, born, "Lily", headline, milestones=make_milestones(start, born)
        )
        path = OUT / f"{key}.png"
        path.write_bytes(cairosvg.svg2png(bytestring=svg.encode(), output_width=W, output_height=H))
        print(f"{key}: {len(times)} contractions, {days} day(s) -> {rings} ring(s)")


if __name__ == "__main__":
    main()
