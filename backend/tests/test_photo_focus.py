"""Placing a photo in a frame, showing the part the parent chose."""
import gift_artwork as ga


def _ph(w, h, crop=None):
    return {"uri": "data:,", "w": w, "h": h, "crop": crop}


def test_no_crop_is_the_centre_cover():
    g = ga.place_photo(0, 0, 100, 100, _ph(300, 200))
    assert (g["width"], g["height"]) == (150, 100)   # covers the frame
    assert g["x"] == -25 and g["y"] == 0             # centred, like xMidYMid slice
    assert g["slice"] is False


def test_the_region_has_the_frame_shape_and_stays_in_the_picture():
    # a square frame on a 2:1 picture: the widest region is half the width
    cx, cy, cw, ch = ga.crop_region(400, 200, 1.0, None)
    assert (cw, ch) == (0.5, 1.0) and (cx, cy) == (0.25, 0.0)
    # a tall frame on the same picture
    cx, cy, cw, ch = ga.crop_region(400, 200, 0.5, None)
    assert (cw, ch) == (0.25, 1.0)
    # the parent's region is clamped inside the picture and to the frame's shape
    cx, cy, cw, ch = ga.crop_region(400, 200, 1.0, (0.9, 0.9, 0.5))
    assert cx == 0.5 and cy == 0.0 and cw == 0.5 and ch == 1.0
    # zooming in shrinks the region; it can't shrink past a tenth
    cx, cy, cw, ch = ga.crop_region(400, 200, 1.0, (0.4, 0.4, 0.2))
    assert cw == 0.2 and ch == 0.4 and (cx, cy) == (0.4, 0.4)
    assert ga.crop_region(400, 200, 1.0, (0, 0, 0.01))[2] == 0.1


def test_a_zoomed_crop_shows_that_part_larger():
    whole = ga.place_photo(0, 0, 100, 100, _ph(400, 200))
    zoomed = ga.place_photo(0, 0, 100, 100, _ph(400, 200, crop=(0.5, 0.0, 0.25)))
    assert zoomed["width"] == 2 * whole["width"]     # a region half as wide, twice the scale
    assert zoomed["x"] == -200                        # the region's left edge lands on the frame's


def test_the_frame_is_always_covered():
    for crop in (None, (0, 0, 0.3), (0.9, 0.9, 0.3), (0.5, 0.5, 5), (-1, -1, 0.5)):
        g = ga.place_photo(10, 20, 80, 60, _ph(1000, 300, crop))
        assert g["x"] <= 10 + 1e-6 and g["x"] + g["width"] >= 90 - 1e-6
        assert g["y"] <= 20 + 1e-6 and g["y"] + g["height"] >= 80 - 1e-6


def test_without_a_size_it_falls_back_to_slice():
    g = ga.place_photo(0, 0, 100, 50, {"uri": "data:,"})
    assert g["slice"] is True and (g["width"], g["height"]) == (100, 50)


def test_crop_is_read_from_the_arrangement():
    from types import SimpleNamespace
    r = SimpleNamespace(layout_overrides={"crop": {"hero": [0.1, 0.2, 0.5], "3": [0, 0, 1]}})
    assert ga.photo_crop(r, "hero") == (0.1, 0.2, 0.5)
    assert ga.photo_crop(r, 3) == (0.0, 0.0, 1.0)
    assert ga.photo_crop(r, 7) is None
    assert ga.photo_crop(None, "hero") is None
