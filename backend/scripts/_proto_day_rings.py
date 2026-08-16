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
    """Two stacked swells (transition). One on its own read as a tilde; the
    pair reads as water, the way ≈ does."""
    def swell(dy: float) -> str:
        return (
            f"M {cx - r:.1f},{cy + dy:.1f} "
            f"Q {cx - r * 0.5:.1f},{cy + dy - r * 0.62:.1f} {cx:.1f},{cy + dy:.1f} "
            f"Q {cx + r * 0.5:.1f},{cy + dy + r * 0.62:.1f} {cx + r:.1f},{cy + dy:.1f} "
            f"L {cx + r:.1f},{cy + dy + r * 0.30:.1f} "
            f"Q {cx + r * 0.5:.1f},{cy + dy + r * 0.92:.1f} {cx:.1f},{cy + dy + r * 0.30:.1f} "
            f"Q {cx - r * 0.5:.1f},{cy + dy - r * 0.32:.1f} {cx - r:.1f},{cy + dy + r * 0.30:.1f} Z"
        )
    return f"{swell(-r * 0.44)} {swell(r * 0.42)}"


# A proper car, from an icon set — it reads as a car far better than the
# silhouette I drew by hand. It lives in a 90-unit box with its ink between
# y 22.6 and 67.4, so the centre is (45, 45) and the shape is about 2:1.
# Unlike the other glyphs this needs its own transform, so it returns
# markup rather than a bare `d`.
_CAR_D = (
    "M 84.99 37.498 l -16.835 -2.571 c -0.428 -0.065 -0.824 -0.277 -1.115 -0.597 l -8.952 -9.805 c -1.115 -1.222 -2.703 -1.922 -4.357 -1.922 H 25.005 c -1.991 0 -3.833 0.993 -4.928 2.656 l -5.862 8.905 c -0.234 0.356 -0.586 0.625 -0.992 0.759 l -9.169 3.022 C 1.629 38.744 0 40.996 0 43.548 v 9.404 c 0 3.254 2.647 5.9 5.9 5.9 h 3.451 c 0.969 4.866 5.269 8.545 10.416 8.545 s 9.447 -3.679 10.416 -8.545 h 30.139 c 0.969 4.866 5.27 8.545 10.416 8.545 s 9.446 -3.679 10.415 -8.545 H 84.1 c 3.254 0 5.9 -2.646 5.9 -5.9 v -9.622 C 90 40.394 87.893 37.941 84.99 37.498 z M 19.767 63.397 c -3.652 0 -6.623 -2.971 -6.623 -6.622 c 0 -3.652 2.971 -6.623 6.623 -6.623 s 6.623 2.971 6.623 6.623 C 26.39 60.427 23.419 63.397 19.767 63.397 z M 70.738 63.397 c -3.652 0 -6.623 -2.971 -6.623 -6.622 c 0 -3.652 2.971 -6.623 6.623 -6.623 c 3.651 0 6.622 2.971 6.622 6.623 C 77.36 60.427 74.39 63.397 70.738 63.397 z M 86 52.952 c 0 1.048 -0.853 1.9 -1.9 1.9 h -2.922 c -0.908 -4.941 -5.239 -8.7 -10.439 -8.7 s -9.531 3.759 -10.44 8.7 H 30.207 c -0.909 -4.941 -5.24 -8.7 -10.44 -8.7 s -9.531 3.759 -10.439 8.7 H 5.9 c -1.048 0 -1.9 -0.853 -1.9 -1.9 v -9.404 c 0 -0.822 0.524 -1.547 1.306 -1.805 l 9.168 -3.021 c 1.26 -0.415 2.354 -1.253 3.083 -2.36 l 5.861 -8.905 c 0.353 -0.536 0.946 -0.855 1.587 -0.855 H 53.73 c 0.532 0 1.044 0.226 1.403 0.62 l 8.952 9.805 c 0.907 0.993 2.139 1.652 3.467 1.854 l 16.834 2.571 C 85.321 41.595 86 42.385 86 43.331 V 52.952 z"
)


_HOSPITAL_D = (
    "M 51.948 73.273 H 38.052 c -1.104 0 -2 -0.896 -2 -2 v -9.621 h -9.621 c -1.104 0 -2 -0.896 -2 -2 V 45.757 c 0 -1.104 0.896 -2 2 -2 h 9.621 v -9.62 c 0 -1.104 0.896 -2 2 -2 h 13.896 c 1.104 0 2 0.896 2 2 v 9.62 h 9.62 c 1.104 0 2 0.896 2 2 v 13.895 c 0 1.104 -0.896 2 -2 2 h -9.62 v 9.621 C 53.948 72.378 53.053 73.273 51.948 73.273 z M 40.052 69.273 h 9.896 v -9.621 c 0 -1.104 0.896 -2 2 -2 h 9.62 v -9.895 h -9.62 c -1.104 0 -2 -0.896 -2 -2 v -9.62 h -9.896 v 9.62 c 0 1.104 -0.896 2 -2 2 h -9.621 v 9.895 h 9.621 c 1.104 0 2 0.896 2 2 V 69.273 z M 78.113 84.056 H 11.887 c -1.104 0 -2 -0.896 -2 -2 V 30.312 c 0 -1.104 0.896 -2 2 -2 s 2 0.896 2 2 v 49.745 h 62.226 V 30.067 c 0 -1.104 0.896 -2 2 -2 s 2 0.896 2 2 v 51.989 C 80.113 83.161 79.218 84.056 78.113 84.056 z M 2.002 38.835 c -0.65 0 -1.287 -0.316 -1.671 -0.898 c -0.608 -0.922 -0.354 -2.163 0.568 -2.771 L 44.687 6.274 c 0.679 -0.449 1.561 -0.439 2.231 0.019 L 89.13 35.184 c 0.911 0.624 1.145 1.869 0.521 2.78 c -0.624 0.912 -1.867 1.146 -2.78 0.521 L 45.768 10.353 L 3.102 38.504 C 2.762 38.728 2.38 38.835 2.002 38.835 z"
)


def _icon(d: str, width_factor: float, rule: str = "nonzero"):
    """Wrap an imported icon (90-unit box, centred at 45,45) so it can be
    dropped on the dial like the hand-drawn glyphs. They need their own
    transform, so these return markup rather than a bare `d`."""
    def markup(mx: float, my: float, r: float, fill: str) -> str:
        s = (r * width_factor) / 90.0
        return (
            f'<g transform="translate({mx - 45 * s:.2f},{my - 45 * s:.2f}) '
            f'scale({s:.4f})"><path d="{d}" fill="{fill}" '
            f'fill-rule="{rule}" opacity="0.85"/></g>'
        )
    return markup


def _bottle_path(cx: float, cy: float, r: float) -> str:
    """A baby bottle — teat, collar, body (first feed)."""
    return (
        f"M {cx - r * 0.11:.1f},{cy - r * 0.98:.1f} "
        f"Q {cx:.1f},{cy - r * 1.30:.1f} {cx + r * 0.11:.1f},{cy - r * 0.98:.1f} "
        f"L {cx + r * 0.11:.1f},{cy - r * 0.80:.1f} "
        f"L {cx + r * 0.32:.1f},{cy - r * 0.80:.1f} "
        f"L {cx + r * 0.32:.1f},{cy - r * 0.58:.1f} "
        f"Q {cx + r * 0.60:.1f},{cy - r * 0.44:.1f} {cx + r * 0.60:.1f},{cy - r * 0.14:.1f} "
        f"L {cx + r * 0.60:.1f},{cy + r * 0.82:.1f} "
        f"Q {cx + r * 0.60:.1f},{cy + r * 1.04:.1f} {cx + r * 0.38:.1f},{cy + r * 1.04:.1f} "
        f"L {cx - r * 0.38:.1f},{cy + r * 1.04:.1f} "
        f"Q {cx - r * 0.60:.1f},{cy + r * 1.04:.1f} {cx - r * 0.60:.1f},{cy + r * 0.82:.1f} "
        f"L {cx - r * 0.60:.1f},{cy - r * 0.14:.1f} "
        f"Q {cx - r * 0.60:.1f},{cy - r * 0.44:.1f} {cx - r * 0.32:.1f},{cy - r * 0.58:.1f} "
        f"L {cx - r * 0.32:.1f},{cy - r * 0.80:.1f} "
        f"L {cx - r * 0.11:.1f},{cy - r * 0.80:.1f} Z"
    )


# The house was standing in for a hospital; now it is one. A birth centre
# is not a home, and `going_home` already has the car.
GLYPH_MARKUP = {
    "going_home": _icon(_CAR_D, 2.4),
    "arrived": _icon(_HOSPITAL_D, 2.0, rule="evenodd"),
}

GLYPHS = {
    "water_broke": _droplet_path,
    "first_feed": _bottle_path,
    "active_labor": _sunrise_path,
    "transition": _wave_path,
    "pushing": _chevrons_path,
}

# Drawn hollow, to match the imported icons. Solid marks were the heaviest
# thing on a dial made of hairlines; outlined, they sit with the ticks and the
# grey circles instead of punching through them. The abstract marks — the
# swell, the chevrons, the sunrise — stay solid: they're line-work already,
# and stroking a stroke reads as a mistake.
HOLLOW = {"water_broke", "first_feed", "born"}
STROKE = 2.6


def _stroked(d: str, colour: str, width: float = STROKE) -> str:
    return (
        f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" '
        f'stroke-linejoin="round" stroke-linecap="round" opacity="0.9"/>'
    )


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
        # a ground of page colour so the mark reads clear of the rays it
        # crosses — the symbol has to survive without a label to lean on
        if kind in GLYPH_MARKUP:
            mark = GLYPH_MARKUP[kind](mx, my, 13, p.accent)
        else:
            d = GLYPHS.get(kind, _sparkle_path)(mx, my, 13)
            mark = _stroked(d, p.accent) if kind in HOLLOW else (
                f'<path d="{d}" fill="{p.accent}" opacity="0.85"/>'
            )
        out.append(
            f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="21" fill="{p.bg}" opacity="0.9"/>'
            f'{mark}'
        )

    # the birth — a heart, on the grey line with the rest. A sparkle is an
    # ornament; this is the one mark on the mug that is a person.
    r_star = rings[-1]["base"]
    sx, sy = CX + r_star * math.cos(star_a), CY + r_star * math.sin(star_a)
    out.append(
        f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="26" fill="{p.bg}" opacity="0.9"/>'
        f'{_stroked(_heart_path(sx, sy, 18), p.accent, 3.0)}'
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
        # after the arrival — the mug doesn't stop at the birth
        ("first_feed", born + timedelta(hours=1, minutes=20)),
        ("going_home", born + timedelta(hours=7)),
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
