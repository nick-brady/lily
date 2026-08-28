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


def test_the_parent_can_arrange_the_middle_of_the_book():
    day = [{"kind": "gallery", "count": 3}, {"kind": "notes"}, {"kind": "gallery", "count": 4}, {"kind": "write_in"}]
    plan = ga.plan_book(n_photos=11, n_notes=9, has_pool=True, has_milestones=True, day=day)
    assert len(plan) == 24
    kinds = _kinds(plan)
    assert kinds[:3] == ["title", "clock", "pool"]                 # the fixed head stays
    assert kinds[3:7] == ["gallery", "notes", "gallery", "write_in"]  # theirs, in their order
    assert kinds[-3:] == ["write_in", "write_in", "closing"]       # and the fixed tail
    galleries = [p for p in plan if p["kind"] == "gallery"]
    assert [p["count"] for p in galleries] == [3, 4]
    assert galleries[1]["slots"] == [3, 4, 5, 6]                   # slots run on in order
    # what's theirs to change: their pages and the ruled ones filling the room;
    # the fixed pages — title, clock, pool, milestones, the two for a pen,
    # the closing — are not
    editable = [p for p in plan if p.get("editable")]
    assert [p["kind"] for p in editable][:4] == ["gallery", "notes", "gallery", "write_in"]
    assert all(p["kind"] in ("gallery", "notes", "write_in") for p in editable)
    assert not any(p.get("editable") for p in plan if p["kind"] in ("title", "clock", "pool", "milestones", "closing"))
    assert not plan[-2].get("editable") and not plan[-3].get("editable")   # the two for a pen


def test_an_arrangement_is_cut_to_the_book_and_counts_are_sane():
    day = [{"kind": "gallery", "count": 9}] * 40 + [{"kind": "mystery"}]
    plan = ga.plan_book(n_photos=80, n_notes=0, has_pool=False, has_milestones=False, day=day)
    assert len(plan) == 24
    assert all(p["count"] <= ga.BOOK_MAX_PER_GALLERY for p in plan if p["kind"] == "gallery")
    assert "mystery" not in _kinds(plan)


# ── the ruled pages' own words ─────────────────────────────────────────────


def test_a_ruled_page_says_what_the_parent_wrote_else_the_books_words():
    day = [{"kind": "write_in", "heading": "  for grandma ", "subheading": "a line each visit"}, {"kind": "write_in"}]
    plan = ga.plan_book(n_photos=2, n_notes=0, has_pool=False, has_milestones=False, day=day)
    ruled = [p for p in plan if p["kind"] == "write_in" and p.get("editable")]
    assert ga.write_in_text(ruled[0], "Lily") == ("for grandma", "a line each visit")
    # the second keeps the book's heading for its position, with the name in it
    h, sub = ga.write_in_text(ruled[1], "Lily")
    assert h == "FOR LATER" and sub  # the second ruled page of the day takes the fourth heading


def test_either_half_alone_can_be_the_parents():
    plan = ga.plan_book(n_photos=2, n_notes=0, has_pool=False, has_milestones=False, day=[{"kind": "write_in", "heading": "x" * 60}])
    ruled = [p for p in plan if p["kind"] == "write_in" and p.get("editable")][0]
    h, sub = ga.write_in_text(ruled, "Lily")
    assert h == "x" * ga.WRITE_IN_HEADING_MAX  # capped
    assert sub == "how it went, in a few lines"  # the book's own, for that position


def test_the_two_pen_pages_at_the_back_take_their_own_words_by_position():
    plan = ga.plan_book(
        n_photos=2, n_notes=0, has_pool=False, has_milestones=False,
        pen_pages=[None, {"heading": "DEAR LILY", "subheading": "from mum"}],
    )
    pens = sorted([p for p in plan if p.get("pen") is not None], key=lambda p: p["pen"])
    assert ga.write_in_text(pens[0], "Lily") == ("A LETTER TO LILY", "from the ones who were there")
    assert ga.write_in_text(pens[1], "Lily") == ("DEAR LILY", "from mum")
    # and they're where they always were: just before the closing
    assert [p["kind"] for p in plan[-3:]] == ["write_in", "write_in", "closing"]


def test_spare_ruled_pages_sent_back_keep_their_place_and_their_words():
    """The editor round-trips every editable page. The fillers after the
    milestones must come back as fillers — not as day pages that push the
    milestones down the book — and words written on one stay on it."""
    plan = ga.plan_book(n_photos=3, n_notes=0, has_pool=True, has_milestones=True)
    day = [
        {"kind": p["kind"], "count": p.get("count"), **({"spare": True} if p.get("spare") else {})}
        for p in plan if p.get("editable")
    ]
    spares = [d for d in day if d.get("spare")]
    assert spares, "the small book has fillers"
    spares[0]["heading"] = "FOR GRANDMA"
    again = ga.plan_book(n_photos=3, n_notes=0, has_pool=True, has_milestones=True, day=day)
    assert [p["kind"] for p in again] == [p["kind"] for p in plan]
    first_spare = next(p for p in again if p.get("spare"))
    assert ga.write_in_text(first_spare, "Lily")[0] == "FOR GRANDMA"
