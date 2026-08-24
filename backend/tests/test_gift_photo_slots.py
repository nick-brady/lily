"""The filmstrip's per-slot photo choices, and the clock's AM/PM legend."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import gift_artwork
import gift_templates


# ── slot overrides: the parsing posture ───────────────────────────────────


def test_slot_overrides_keeps_only_real_slots():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    r = SimpleNamespace(
        photo_slots={"0": a, "3": b, "9": str(uuid.uuid4()), "nope": a, "1": ""}
    )
    # slot 9 is off the strip, "nope" isn't a slot, "" isn't a choice —
    # they fall away rather than failing the render, like text overrides do
    assert gift_artwork.slot_overrides(r, 4) == {0: a, 3: b}


def test_a_design_without_the_column_is_all_auto():
    assert gift_artwork.slot_overrides(SimpleNamespace(), 4) == {}
    assert gift_artwork.slot_overrides(None, 4) == {}


def test_the_filmstrips_declare_their_panel_counts():
    assert gift_templates.get("mug_reel").photo_slots == 4
    assert gift_templates.get("card_reel").photo_slots == 3
    # the single-photo designs stay on the single-photo path
    assert gift_templates.get("mug_hours").photo_slots == 0


# ── the AM/PM legend ──────────────────────────────────────────────────────


def _clock(offset_hours, start_hour=7):
    start = datetime(2026, 8, 10, start_hour, 0)
    offsets = [int(h * 3600) for h in offset_hours]
    return gift_artwork.build_hours_clock(
        durations=[45] * len(offsets),
        offsets_seconds=offsets,
        first_contraction_at=start,
        born_at=start + timedelta(seconds=offsets[-1] + 600),
        cx=640,
        cy=577,
        canvas_w=2475,
        **gift_artwork.CLOCK_PRESETS["hours"],
    )


def test_legend_names_the_tones_when_both_are_on_the_dial():
    out = _clock([1, 2, 8, 9])  # 8am–4pm: both tones
    labels = [it["label"] for it in out["clock_legend"]["items"]]
    assert labels == ["AM", "PM"]


def test_no_legend_for_a_single_tone_labor():
    # 7–11am: all AM — a legend would explain a distinction that isn't there
    assert _clock([1, 2, 3, 4])["clock_legend"] is None


def test_no_legend_when_day_rings_leave_it_no_room():
    # three days: the centre hole shrinks under the legend's width, and the
    # legend absent beats the legend lying across the innermost day's rays
    out = _clock([1, 5, 15, 30, 40, 55, 62])
    assert len(out["clock_rings"]) == 3
    assert out["clock_legend"] is None
