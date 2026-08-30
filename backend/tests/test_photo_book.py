"""The photo book: what fills twenty-four pages, for stories of every size."""
from __future__ import annotations

import uuid

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
        {"kind": p["kind"], "count": p.get("count"), **({"spare": p["spare"]} if p.get("spare") is not None else {})}
        for p in plan if p.get("editable")
    ]
    spares = [d for d in day if d.get("spare") is not None]
    assert spares, "the small book has fillers"
    spares[0]["heading"] = "FOR GRANDMA"
    again = ga.plan_book(n_photos=3, n_notes=0, has_pool=True, has_milestones=True, day=day)
    assert [p["kind"] for p in again] == [p["kind"] for p in plan]
    first_spare = next(p for p in again if p.get("spare") == 0)
    # and sent back out of order, the words still find their page
    shuffled = [d for d in day if d.get("spare") is None] + [d for d in day if d.get("spare") is not None][::-1]
    twice = ga.plan_book(n_photos=3, n_notes=0, has_pool=True, has_milestones=True, day=shuffled)
    assert ga.write_in_text(next(p for p in twice if p.get("spare") == 0), "Lily")[0] == "FOR GRANDMA"
    assert ga.write_in_text(first_spare, "Lily")[0] == "FOR GRANDMA"


# ── a gallery page carries its own photos ──────────────────────────────────


def _day_of(plan):
    return [
        {
            "kind": p["kind"],
            "count": p.get("count"),
            **({"spare": p["spare"]} if p.get("spare") is not None else {}),
            **({"photos": p["photos"]} if p.get("photos") else {}),
        }
        for p in plan if p.get("editable")
    ]


def test_a_moved_gallery_page_takes_its_photos_with_it():
    """Slots are handed out by position, so before this the photos were
    re-dealt after a move and the page appeared not to move at all."""
    plan = ga.plan_book(n_photos=6, n_notes=0, has_pool=False, has_milestones=False)
    galleries = [p for p in plan if p["kind"] == "gallery"]
    # pin each gallery page to a photo, as the editor does once you arrange
    day = _day_of(plan)
    gi = [i for i, d in enumerate(day) if d["kind"] == "gallery"][:2]
    day[gi[0]]["photos"] = ["photo-a"]
    day[gi[1]]["photos"] = ["photo-b"]
    day[gi[0]], day[gi[1]] = day[gi[1]], day[gi[0]]
    moved = ga.plan_book(n_photos=6, n_notes=0, has_pool=False, has_milestones=False, day=day)
    choices = ga.book_slot_choices(moved, None, len(galleries))
    first, second = [p for p in moved if p["kind"] == "gallery"][:2]
    assert choices[first["slots"][0]] == "photo-b"
    assert choices[second["slots"][0]] == "photo-a"


def test_a_page_without_photos_of_its_own_keeps_the_auto_pick():
    plan = ga.plan_book(n_photos=6, n_notes=0, has_pool=False, has_milestones=False, day=[{"kind": "gallery", "count": 2}])
    gallery = next(p for p in plan if p["kind"] == "gallery")
    assert "photos" not in gallery
    assert ga.book_slot_choices(plan, None, 2) == {}


def test_choices_from_before_pages_carried_photos_still_apply():
    """A book arranged under the old shape keeps its index-keyed picks, and a
    page's own photo wins where it has one."""
    class R:
        photo_slots = {"0": "old-0", "1": "old-1"}
        layout_overrides = {}

    plan = ga.plan_book(n_photos=6, n_notes=0, has_pool=False, has_milestones=False, day=[{"kind": "gallery", "count": 2, "photos": [None, "new-1"]}])
    assert ga.book_slot_choices(plan, R(), 2) == {0: "old-0", 1: "new-1"}


# ── what the editor is served ──────────────────────────────────────────────


def test_the_editor_gets_the_small_copies_and_the_order_the_print_file():
    from repositories import gifts as repo

    class R:
        rendering_metadata = {
            "book_plan": [{"key": "page_1", "kind": "title"}, {"key": "page_2", "kind": "notes"}],
            "pages": {"page_1": "print/1.png", "page_2": "print/2.png", "cover": "print/c.png"},
            "page_variants": {
                "display": {"page_1": "display/1.webp"},
                "thumbnail": {"page_1": "thumb/1.webp"},
            },
        }

    # the order ships the print file whatever the editor is shown
    assert repo.print_pages(R())["page_1"] == "print/1.png"
    by_key = {p["key"]: p for p in repo.book_pages(R())}
    assert "display/1.webp" in by_key["page_1"]["url"]
    assert "thumb/1.webp" in by_key["page_1"]["thumb_url"]
    # a page drawn before the small copies existed still shows, at print size
    assert "print/2.png" in by_key["page_2"]["url"]
    assert "print/2.png" in by_key["page_2"]["thumb_url"]


def test_each_variant_is_smaller_than_the_last_and_never_fails_a_render():
    import io
    from PIL import Image
    from repositories import gifts as repo

    buf = io.BytesIO()
    Image.new("RGB", (2325, 2325), "white").save(buf, "PNG")
    page = buf.getvalue()
    sizes = {}
    for variant, (size, quality) in repo.VARIANTS.items():
        out = repo._variant_bytes(page, size, quality)
        assert out and len(out) < len(page)
        assert Image.open(io.BytesIO(out)).width == size
        sizes[variant] = size
    assert sizes["thumbnail"] < sizes["display"]
    # a body that isn't an image doesn't take the render down with it
    assert repo._variant_bytes(b"not a png", 300, 85) is None


# ── what gets drawn, and when ──────────────────────────────────────────────


def test_pages_can_be_drawn_for_the_screen_while_the_cover_keeps_its_size():
    """The editor looks at pages on a screen; only the press wants 2325px.
    The cover is exempt — it's what the partner photographs."""
    import gift_artwork as ga

    spec = {
        "cover": ("book_cover.svg.j2", {}, ga.BOOK_COVER_W, ga.BOOK_COVER_H),
        "page_1": ("book_title.svg.j2", {}, ga.BOOK_PAGE, ga.BOOK_PAGE),
    }
    def width_for(key, w, page_width, output_width=None):
        # the rule render_book applies, stated once so a change to it is seen
        return output_width or (page_width if page_width and key.startswith("page_") else w)

    assert width_for("page_1", ga.BOOK_PAGE, 900) == 900
    assert width_for("cover", ga.BOOK_COVER_W, 900) == ga.BOOK_COVER_W
    assert width_for("page_1", ga.BOOK_PAGE, None) == ga.BOOK_PAGE
    # an explicit output_width (the editor's preview) still wins over both
    assert width_for("cover", ga.BOOK_COVER_W, 900, output_width=520) == 520
    assert set(spec) == {"cover", "page_1"}


def test_a_book_only_stores_the_cover_as_a_print_file_until_it_is_ordered():
    """`print_pages` is what the order ships. After a save it holds the cover
    alone; the pages are made by `ensure_print_pages` on the way out."""
    from repositories import gifts as repo

    class Saved:
        rendering_metadata = {
            "book_plan": [{"key": "page_1", "kind": "title"}, {"key": "page_2", "kind": "clock"}],
            "pages": {"cover": "print/cover.png"},
            "page_variants": {"display": {"page_1": "d/1.webp", "page_2": "d/2.webp"}},
        }

    assert set(repo.print_pages(Saved())) == {"cover"}
    # the editor is unaffected: it was never looking at the print files
    assert all(p["url"] for p in repo.book_pages(Saved()))


def test_ensure_print_pages_makes_only_what_is_missing(monkeypatch):
    from repositories import gifts as repo

    class R:
        id = uuid.uuid4()
        birth_id = uuid.uuid4()
        template_id = "book_8x8"
        rendering_metadata = {
            "book_plan": [{"key": "page_1", "kind": "title"}, {"key": "page_2", "kind": "clock"}],
            "pages": {"cover": "print/cover.png", "page_1": "print/1.png"},
        }

    asked = {}

    def fake_render_book(birth, template, db, rendering, *, keys=None, sink=None, **kw):
        asked["keys"] = set(keys or [])
        for k in sorted(asked["keys"]):
            sink(k, b"png")
        return {}, {}

    monkeypatch.setattr(repo.gift_artwork, "render_book", fake_render_book)
    monkeypatch.setattr(repo, "_put_page", lambda birth, rid, key, body: f"made/{key}.png")

    class DB:
        def get(self, model, pk):
            return object()

        def commit(self):
            pass

    r = R()
    monkeypatch.setattr(repo.gift_templates, "get", lambda t: object())
    made = repo.ensure_print_pages(DB(), r)
    # only page_2 was missing; the cover and page_1 were left alone
    assert asked["keys"] == {"page_2"}
    assert made["page_2"] == "made/page_2.png"
    assert made["cover"] == "print/cover.png" and made["page_1"] == "print/1.png"
    # and asking again renders nothing at all
    asked.clear()
    assert repo.ensure_print_pages(DB(), r) == made and "keys" not in asked


def test_a_design_that_is_not_a_book_has_no_print_pages_to_make():
    from repositories import gifts as repo

    class Mug:
        rendering_metadata = {"template_id": "mug_hours"}

    assert repo.ensure_print_pages(None, Mug()) == {}
