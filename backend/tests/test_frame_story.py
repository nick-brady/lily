"""The story frame: the timeline wrapping the opening, by beat not by clock."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import gift_artwork as ga
import gift_templates

T0 = datetime(2026, 6, 1, 19, 4)
W, H = 2250, 3450


def _straight():
    edges = ga._story_edges(W, H)
    return sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b, _ in edges)


def _photo(i, when):
    return {"kind": "photo", "uri": "data:,", "when": when, "media_id": f"m{i}"}


def test_the_story_is_second_and_drawn_for_the_opening():
    frames = [t.template_id for t in gift_templates.for_product("framed_print")]
    assert frames == ["frame_wall", "frame_story", "frame_pool"]
    story = gift_templates.get("frame_story")
    assert story.inner == "opening_story" and story.safe_box == gift_templates.MAT_OPENING


def test_photos_are_an_inch_and_the_count_follows():
    """Forty photos don't fit at an inch each; the line thins them evenly and
    keeps every milestone. Six photos all stay."""
    many = [_photo(i, T0 + timedelta(minutes=10 * i)) for i in range(40)]
    many.append({"kind": "water_broke", "when": T0 + timedelta(hours=1)})
    kept = ga.story_thin(many, _straight())
    photos = [m for m in kept if m["kind"] == "photo"]
    assert ga.STORY_MIN_PHOTOS < len(photos) < 40
    assert any(m["kind"] == "water_broke" for m in kept)
    # evenly: first and last survive
    assert photos[0]["media_id"] == "m0" and photos[-1]["media_id"] == "m39"
    few = [_photo(i, T0 + timedelta(hours=i)) for i in range(6)]
    assert len(ga.story_thin(few, _straight())) == 6


def test_notes_are_capped_before_photos_are_touched():
    ms = [_photo(i, T0 + timedelta(hours=i)) for i in range(5)]
    ms += [{"kind": "note", "text": f"note {i}", "when": T0 + timedelta(minutes=i)} for i in range(20)]
    kept = ga.story_thin(ms, _straight())
    assert sum(1 for m in kept if m["kind"] == "note") == ga.STORY_MAX_NOTES
    assert sum(1 for m in kept if m["kind"] == "photo") == 5


def test_nothing_sits_on_a_corner():
    """A picture on a corner arc overlaps its neighbours, so moments live on
    the four straight runs only."""
    ms = [_photo(i, T0 + timedelta(hours=i)) for i in range(20)]
    sc = ga.build_frame_story_scene(moments=ms, labor_start=T0, due_date=None, width=W, height=H)
    inset, r = ga.STORY_INSET, ga.STORY_CORNER
    for ph in sc["story_photos"]:
        cx, cy = ph["x"] + ph["size"] / 2, ph["y"] + ph["size"] / 2
        on_x_edge = abs(cx - inset) < 1 or abs(cx - (W - inset)) < 1
        on_y_edge = abs(cy - inset) < 1 or abs(cy - (H - inset)) < 1
        assert on_x_edge or on_y_edge
        # and not within a corner's reach along that edge
        if on_y_edge:
            assert inset + r <= cx <= W - inset - r
        if on_x_edge:
            assert inset + r <= cy <= H - inset - r


def test_it_starts_top_left_and_runs_clockwise():
    ms = [_photo(i, T0 + timedelta(hours=i)) for i in range(8)]
    sc = ga.build_frame_story_scene(moments=ms, labor_start=T0, due_date=None, width=W, height=H)
    first, last = sc["story_photos"][0], sc["story_photos"][-1]
    assert abs(first["y"] + first["size"] / 2 - ga.STORY_INSET) < 1       # on the top edge
    assert abs(last["x"] + last["size"] / 2 - ga.STORY_INSET) < 1         # back on the left edge
    assert sc["slot_media_ids"] == [f"m{i}" for i in range(8)]


def test_pregnancy_moments_are_labelled_by_week_then_days_take_over():
    due = date(2026, 6, 8)
    ms = [
        _photo(0, datetime(2026, 3, 30, 10, 0)),   # 30 weeks
        _photo(1, datetime(2026, 5, 11, 10, 0)),   # 36 weeks
        _photo(2, T0 + timedelta(hours=1)),        # in labor: a date
        {"kind": "born", "when": T0 + timedelta(hours=9)},
    ]
    sc = ga.build_frame_story_scene(moments=ms, labor_start=T0, due_date=due, width=W, height=H)
    assert [d["label"] for d in sc["story_day_labels"]] == ["30 WEEKS", "36 WEEKS", "JUN 1", "JUN 2"]
    # without a due date, dates all the way
    sc = ga.build_frame_story_scene(moments=ms, labor_start=T0, due_date=None, width=W, height=H)
    assert sc["story_day_labels"][0]["label"] == "MAR 30"


def test_notes_carry_their_time_and_side_notes_stay_short():
    ms = [_photo(i, T0 + timedelta(hours=i)) for i in range(3)]
    ms.append({"kind": "note", "text": "Midwife said she was getting close to transition", "when": T0 + timedelta(hours=1, minutes=30)})
    sc = ga.build_frame_story_scene(moments=ms, labor_start=T0, due_date=None, width=W, height=H)
    (n,) = sc["story_notes"]
    assert n["when"] == "8:34 pm"
    if n["side"]:
        assert len(n["lines"]) == 1 and len(n["lines"][0]) <= ga.STORY_NOTE_SIDE_CHARS
    else:
        assert 1 <= len(n["lines"]) <= 3


def test_the_born_heart_is_on_the_line_where_it_happened():
    ms = [_photo(0, T0), {"kind": "born", "when": T0 + timedelta(hours=9)}, _photo(1, T0 + timedelta(hours=10))]
    sc = ga.build_frame_story_scene(moments=ms, labor_start=T0, due_date=None, width=W, height=H)
    assert sc["story_born"]["label"] == "4:04 AM"
    # on the line: one of the four straight edges
    bx, by = sc["story_born"]["x"], sc["story_born"]["y"]
    inset = ga.STORY_INSET
    assert min(abs(bx - inset), abs(bx - (W - inset)), abs(by - inset), abs(by - (H - inset))) < 1


def test_the_pool_divides_the_dial_from_the_name():
    ms = [_photo(i, T0 + timedelta(hours=i)) for i in range(6)]
    plain = ga.build_frame_story_scene(moments=ms, labor_start=T0, due_date=None, width=W, height=H)
    ruled = ga.build_frame_story_scene(
        moments=ms, labor_start=T0, due_date=None, width=W, height=H, pool=([7.5, 8.0, 9.1], 8.4375)
    )
    assert plain["pool_ruler"] is None
    r = ruled["pool_ruler"]
    assert r is not None and len(r["dots"]) == 3 and [t["label"] for t in r["ticks"]] == ["8 LB", "9 LB"]
    # between the dial and the name, and the pair moves apart to make room
    dial_bottom = ruled["story_clock_cy"] + ga.STORY_CLOCK_R
    assert dial_bottom < r["y"] < ruled["story_name_y"]
    assert ruled["story_clock_cy"] < plain["story_clock_cy"]
    assert ruled["story_name_y"] > plain["story_name_y"]
    # centred on the page
    assert abs((r["x1"] + r["x2"]) / 2 - W / 2) < 1


def test_guesses_wear_their_names_without_overlapping():
    """Three people at the same weight get three rows, not one smear."""
    r = ga.weight_ruler(
        [7.5, 7.5, 7.5, 9.0], 8.4, x1=0, x2=860, y=100, names=["Nina", "Copa", "Kim", "Nathan"]
    )
    tagged = [d for d in r["dots"] if d.get("label")]
    assert sorted(d["label"] for d in tagged) == ["Copa", "Kim", "Nathan", "Nina"]
    same_x = [d for d in tagged if d["x"] == tagged[0]["x"]]
    assert sorted(d["row"] for d in same_x) == [0, 1, 2]
    # a lone guess goes on the bottom row
    assert next(d for d in tagged if d["label"] == "Nathan")["row"] == 0
    # no names, no tags — the pool card's ruler is unchanged
    assert all("label" not in d for d in ga.weight_ruler([7.5], 8.4, x1=0, x2=860, y=100)["dots"])


# ── the photo roll: ticks, not slots ──────────────────────────────────────


def test_a_pinned_photo_survives_the_thinning():
    """Forty photos, one the parent ticked on: the line thins around it."""
    many = [_photo(i, T0 + timedelta(minutes=10 * i)) for i in range(40)]
    without = ga.story_thin(many, _straight())
    # m17 is an odd one out that the even sample normally drops
    assert not any(m["media_id"] == "m17" for m in without)
    kept = ga.story_thin(many, _straight(), pinned={"m17"})
    assert any(m["media_id"] == "m17" for m in kept)
    # pinning didn't buy extra room — the count is the same
    assert sum(1 for m in kept if m["kind"] == "photo") == sum(
        1 for m in without if m["kind"] == "photo"
    )


def test_capacity_is_the_count_the_line_holds():
    many = [_photo(i, T0 + timedelta(minutes=10 * i)) for i in range(40)]
    many.append({"kind": "water_broke", "when": T0 + timedelta(hours=1)})
    cap = ga.story_capacity(many, _straight())
    assert cap == sum(1 for m in ga.story_thin(many, _straight()) if m["kind"] == "photo")
    # six photos: the line holds all six, so the capacity is six
    few = [_photo(i, T0 + timedelta(hours=i)) for i in range(6)]
    assert ga.story_capacity(few, _straight()) == 6


def test_ticks_are_read_off_the_layout_and_off_beats_on():
    class R:
        layout_overrides = {"story": {"off": ["a", "b"], "on": ["b", "c"]}}

    off, on = ga.story_overrides(R())
    assert off == {"a", "b"} and on == {"c"}
    assert ga.story_overrides(None) == (set(), set())
    assert ga.story_overrides(type("R", (), {"layout_overrides": {}})()) == (set(), set())
