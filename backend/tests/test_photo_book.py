"""The photo book: what fills twenty-four pages, for stories of every size."""
from __future__ import annotations

import gift_artwork as ga
import gift_templates
from fulfillment import products as fp


def _kinds(plan):
    return [p["kind"] for p in plan]


def test_always_twenty_four_pages_whatever_the_story():
    for n_photos in (0, 1, 4, 11, 30, 80):
        for n_notes in (0, 3, 9, 20):
            for pool in (True, False):
                plan = ga.plan_book(n_photos=n_photos, n_notes=n_notes, has_pool=pool, has_milestones=True)
                assert len(plan) == ga.BOOK_PAGES
                assert [p["key"] for p in plan] == [f"page_{i}" for i in range(1, 25)]


def test_the_running_order():
    plan = ga.plan_book(n_photos=11, n_notes=9, has_pool=True, has_milestones=True)
    kinds = _kinds(plan)
    assert kinds[:3] == ["title", "clock", "pool"]
    assert kinds[-3:] == ["write_in", "write_in", "closing"]
    # the milestones close the day, before the pages for a pen
    assert kinds.index("milestones") < kinds.index("write_in")
    assert kinds.index("milestones") > max(i for i, k in enumerate(kinds) if k in ("gallery", "notes"))
    day = [k for k in kinds if k in ("gallery", "notes")]
    assert day[0] == "gallery" and day[-1] == "gallery"   # notes sit among the photos


def test_photos_spread_about_three_to_a_page_and_slots_run_in_order():
    plan = ga.plan_book(n_photos=11, n_notes=0, has_pool=True, has_milestones=True)
    galleries = [p for p in plan if p["kind"] == "gallery"]
    assert len(galleries) == 11 and all(p["count"] == 1 for p in galleries)   # a photo a page while pages last
    slots = [s for p in galleries for s in p["slots"]]
    assert slots == list(range(11))
    # more photos than pages: they share
    plan = ga.plan_book(n_photos=30, n_notes=0, has_pool=True, has_milestones=True)
    galleries = [p for p in plan if p["kind"] == "gallery"]
    assert sum(p["count"] for p in galleries) == 30 and max(p["count"] for p in galleries) == 2
    # a page never holds more than four
    busy = ga.plan_book(n_photos=80, n_notes=0, has_pool=False, has_milestones=False)
    assert max(p["count"] for p in busy if p["kind"] == "gallery") <= ga.BOOK_MAX_PER_GALLERY


def test_a_thin_story_gets_pages_to_write_in_not_blank_ones():
    plan = ga.plan_book(n_photos=2, n_notes=0, has_pool=False, has_milestones=False)
    kinds = _kinds(plan)
    assert kinds.count("gallery") == 2   # a photo a page
    assert kinds.count("write_in") >= 10
    assert "closing" == kinds[-1]
    # the two pages meant for a pen close the book; the extra ruled pages
    # before them cycle through the other headings rather than repeat one
    headings = [p["heading"] for p in plan if p["kind"] == "write_in"]
    assert headings[-2:] == [0, 1]
    assert headings[:4] == [2, 3, 4, 5]


def test_no_photos_still_makes_a_book():
    plan = ga.plan_book(n_photos=0, n_notes=0, has_pool=False, has_milestones=False)
    assert "gallery" not in _kinds(plan)
    assert len(plan) == 24


def test_the_book_is_matte_first_and_the_same_price_either_way():
    books = fp.for_product_kind("photo_book")
    assert [b.key for b in books] == ["book_8x8_matte", "book_8x8_glossy"]
    assert fp.default_for_product_kind("photo_book").key == "book_8x8_matte"
    assert {b.surcharge_cents for b in books} == {0}
    assert gift_templates.get("book_8x8").scene == "book"
