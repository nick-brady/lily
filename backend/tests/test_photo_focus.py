"""Placing a photo in a frame while keeping its focal point."""
import gift_artwork as ga


def _ph(w, h, fx=0.5, fy=0.5):
    return {"uri": "data:,", "w": w, "h": h, "fx": fx, "fy": fy}


def test_centre_focus_is_the_plain_centre_crop():
    g = ga.place_photo(0, 0, 100, 100, _ph(300, 200))
    assert (g["width"], g["height"]) == (150, 100)   # covers the frame
    assert g["x"] == -25 and g["y"] == 0             # centred, like xMidYMid slice
    assert g["slice"] is False


def test_focus_shifts_the_crop_toward_the_point():
    # a tall photo in a square frame: focus near the top keeps the top
    g = ga.place_photo(0, 0, 100, 100, _ph(200, 400, fx=0.5, fy=0.15))
    assert g["y"] == 0                                # can't go higher than the frame's top
    g2 = ga.place_photo(0, 0, 100, 100, _ph(200, 400, fx=0.5, fy=0.5))
    assert g2["y"] == -50                             # centre crop shows the middle
    g3 = ga.place_photo(0, 0, 100, 100, _ph(200, 400, fx=0.5, fy=1.0))
    assert g3["y"] == -100                            # and the bottom stays covered


def test_the_frame_is_always_covered():
    for fx in (0, 0.3, 0.5, 0.9, 1):
        for fy in (0, 0.5, 1):
            g = ga.place_photo(10, 20, 80, 60, _ph(1000, 300, fx, fy))
            assert g["x"] <= 10 and g["x"] + g["width"] >= 90
            assert g["y"] <= 20 and g["y"] + g["height"] >= 80


def test_without_a_size_it_falls_back_to_slice():
    g = ga.place_photo(0, 0, 100, 50, {"uri": "data:,"})
    assert g["slice"] is True and (g["width"], g["height"]) == (100, 50)


def test_focus_is_read_from_the_arrangement_and_clamped():
    from types import SimpleNamespace
    r = SimpleNamespace(layout_overrides={"focus": {"hero": [0.5, 0.1], "3": [1.4, -2]}})
    assert ga.photo_focus(r, "hero") == (0.5, 0.1)
    assert ga.photo_focus(r, 3) == (1.0, 0.0)
    assert ga.photo_focus(r, 7) == (0.5, 0.5)
    assert ga.photo_focus(None, "hero") == (0.5, 0.5)
