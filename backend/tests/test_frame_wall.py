"""The wall: the labor as a border around the mat opening."""
from __future__ import annotations

from datetime import datetime, timedelta

import gift_artwork as ga
import gift_templates

START = datetime(2026, 6, 1, 19, 4)
END = START + timedelta(hours=9, minutes=38)
W, H = 2250, 3450


def _scene(**over):
    kw = dict(
        contractions=[(START + timedelta(minutes=14 * i), 45 + (i * 7) % 50) for i in range(40)],
        milestones=[("water_broke", START + timedelta(hours=3))],
        pulse=[(START + timedelta(hours=1), "comment"), (START + timedelta(hours=2), "reaction")],
        photos=[{"uri": "data:,", "occurred_at": START + timedelta(hours=i), "media_id": f"m{i}"} for i in range(7)],
        start=START, end=END, width=W, height=H,
    )
    kw.update(over)
    return ga.build_wall_scene(**kw)


def test_the_wall_leads_the_frames():
    frames = [t.template_id for t in gift_templates.for_product("framed_print")]
    assert frames[0] == "frame_wall"
    wall = gift_templates.get("frame_wall")
    # drawn for the opening itself, so the border can hug the mat
    assert wall.inner == "opening_wall" and wall.safe_box == gift_templates.MAT_OPENING
    assert (gift_templates.get("opening_wall").width, gift_templates.get("opening_wall").height) == (2250, 3450)
    # the opening design never appears on its own
    assert not any(t.template_id == "opening_wall" for t in gift_templates.for_product("framed_print"))
    assert gift_artwork_fit_is_exact()


def gift_artwork_fit_is_exact():
    wall = gift_templates.get("frame_wall")
    # 7.5 in wide at 300 DPI = 2250: the opening design lands 1:1 on the sheet
    return ga._fit(ga._layout_of(wall), wall, 3600, 4800) == (675, 675, 2250, 3450)


def test_every_contraction_is_a_tick_and_it_points_inward():
    sc = _scene()
    assert len(sc["wall_ticks"]) == 40
    for t in sc["wall_ticks"]:
        # the far end of every tick is nearer the centre than the near end
        d_near = (t["x1"] - W / 2) ** 2 + (t["y1"] - H / 2) ** 2
        d_far = (t["x2"] - W / 2) ** 2 + (t["y2"] - H / 2) ** 2
        assert d_far < d_near


def test_the_line_starts_left_of_centre_and_arrives_right_of_it():
    sc = _scene()
    assert sc["wall_first"]["x"] < W / 2 < sc["wall_born"]["x"]
    assert sc["wall_first"]["y"] == sc["wall_born"]["y"] == H - ga.WALL_INSET
    assert sc["wall_born"]["label"] == "4:42 AM"


def test_the_family_dots_sit_outside_the_line():
    sc = _scene()
    assert len(sc["wall_pulse"]) == 2
    # outside: further from the centre than the border itself
    for d in sc["wall_pulse"]:
        assert min(d["cx"], W - d["cx"], d["cy"], H - d["cy"]) < ga.WALL_INSET


def test_time_marks_every_six_hours_and_midnight_carries_the_date():
    sc = _scene()  # 7:04 pm → 4:42 am the next day
    labels = [m["label"] for m in sc["wall_time_marks"]]
    assert labels == ["JUN 2"]  # midnight is the only six-hour mark not within 50 min of an end
    sc = _scene(end=START + timedelta(hours=30))
    labels = [m["label"] for m in sc["wall_time_marks"]]
    assert labels == ["JUN 2", "6 AM", "NOON", "6 PM", "JUN 3"]


def test_seven_pictures_read_the_day_in_order():
    sc = _scene()
    tiles = sc["wall_tiles"]
    assert len(tiles) == 7
    assert sc["slot_media_ids"] == [f"m{i}" for i in range(7)]
    ys = [t["y"] for t in tiles]
    assert ys == sorted(ys)  # rows top to bottom
    # inside the border on every side
    for t in tiles:
        assert t["x"] > ga.WALL_INSET and t["x"] + t["w"] < W - ga.WALL_INSET


def test_fewer_photos_means_fewer_pictures_not_empty_mats():
    sc = _scene(photos=[{"uri": "data:,", "occurred_at": START, "media_id": "only"}])
    assert len(sc["wall_tiles"]) == 1


def test_legend_only_when_both_tones_show():
    assert _scene()["clock_legend"] is not None  # 7 pm → 4 am crosses midnight
    morning = [(START.replace(hour=8) + timedelta(minutes=10 * i), 40) for i in range(10)]
    sc = _scene(contractions=morning, start=START.replace(hour=8), end=START.replace(hour=11))
    assert sc["clock_legend"] is None
