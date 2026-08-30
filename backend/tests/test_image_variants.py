"""Smaller copies of a photo: how they're made, which one gets served, and
what happens to a file we can't read.

A phone photo is ~3MB and gets drawn at 57px in a picker. These are the
pieces that stop the browser downloading the former to draw the latter.
"""
from __future__ import annotations

import io
import uuid
from types import SimpleNamespace

import pytest
from PIL import Image

import image_variants
from repositories import media as media_repo


def _jpeg(w=2000, h=1500, colour=(120, 90, 60), exif=None) -> bytes:
    buf = io.BytesIO()
    kw = {"exif": exif} if exif else {}
    Image.new("RGB", (w, h), colour).save(buf, "JPEG", **kw)
    return buf.getvalue()


def _size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


# ── making them ────────────────────────────────────────────────────────────


def test_build_makes_every_variant_and_reports_the_true_size():
    variants, (w, h) = image_variants.build(_jpeg(2000, 1500))
    assert set(variants) == {"display", "thumbnail"}
    assert (w, h) == (2000, 1500)
    assert _size(variants["display"]) == (1600, 1200)
    assert _size(variants["thumbnail"]) == (320, 240)
    # WebP, and each one smaller than the last
    assert all(v[:4] == b"RIFF" for v in variants.values())
    assert len(variants["thumbnail"]) < len(variants["display"])


def test_a_photo_smaller_than_a_variant_is_left_alone():
    """Upscaling adds bytes, not detail."""
    variants, size = image_variants.build(_jpeg(240, 180))
    assert size == (240, 180)
    assert _size(variants["display"]) == (240, 180)
    assert _size(variants["thumbnail"]) == (240, 180)


def test_a_sideways_phone_photo_comes_out_upright():
    """Cameras record orientation in EXIF rather than in the pixels. Without
    the transpose a portrait photo is served on its side — and the recorded
    width/height would be the wrong way round too."""
    exif = Image.Exif()
    exif[274] = 6  # rotate 90° CW
    variants, (w, h) = image_variants.build(_jpeg(2000, 1000, exif=exif.tobytes()))
    assert (w, h) == (1000, 2000)  # upright, not as stored
    assert _size(variants["display"]) == (800, 1600)


def test_transparency_is_flattened_onto_white_not_black():
    buf = io.BytesIO()
    Image.new("RGBA", (400, 400), (255, 0, 0, 0)).save(buf, "PNG")
    variants, _ = image_variants.build(buf.getvalue())
    out = Image.open(io.BytesIO(variants["thumbnail"])).convert("RGB")
    assert out.getpixel((10, 10)) == (255, 255, 255)


def test_bytes_that_are_not_an_image_raise_rather_than_return_junk():
    with pytest.raises(image_variants.UnreadableImage):
        image_variants.build(b"this is not a photograph")


def test_encode_one_swallows_a_bad_image_for_callers_who_can_live_without():
    """A gift page's thumbnail is a convenience; it must never be the reason
    a render fails."""
    assert image_variants.encode_one(b"not an image", 300, 85) is None
    assert image_variants.encode_one(_jpeg(800, 800), 300, 85) is not None


# ── which one gets served ──────────────────────────────────────────────────


def _asset(**kw):
    return SimpleNamespace(
        **{
            "id": uuid.uuid4(),
            "original_s3_key": "f/x/b/y/photo.jpg",
            "display_s3_key": None,
            "thumbnail_s3_key": None,
            **kw,
        }
    )


def test_a_variant_that_exists_is_the_one_served():
    asset = _asset(
        display_s3_key="f/x/b/y/variants/p-display.webp",
        thumbnail_s3_key="f/x/b/y/variants/p-thumbnail.webp",
    )
    assert media_repo.variant_key(asset, "display") == asset.display_s3_key
    assert media_repo.variant_key(asset, "thumbnail") == asset.thumbnail_s3_key
    # the original is always itself
    assert media_repo.variant_key(asset, "raw") == asset.original_s3_key
    assert media_repo.variant_key(asset, None) == asset.original_s3_key


def test_a_variant_the_worker_has_not_made_falls_back_to_the_original():
    """This is what makes the whole thing safe to ship ahead of the worker:
    every reader keeps working and simply gets lighter as copies appear."""
    asset = _asset()
    for variant in ("display", "thumbnail", "raw", None):
        assert media_repo.variant_key(asset, variant) == asset.original_s3_key
    # half done is fine too — the thumbnail exists, the display doesn't
    half = _asset(thumbnail_s3_key="f/x/b/y/variants/p-thumbnail.webp")
    assert media_repo.variant_key(half, "thumbnail") == half.thumbnail_s3_key
    assert media_repo.variant_key(half, "display") == half.original_s3_key


def test_a_kind_with_no_variants_serves_itself():
    """A voice memo has no display copy and never will."""
    memo = _asset(original_s3_key="f/x/b/y/memo.m4a")
    assert media_repo.variant_key(memo, "display") == memo.original_s3_key


# ── the endpoint ───────────────────────────────────────────────────────────


def test_the_media_route_takes_a_variant_and_refuses_an_unknown_one():
    from fastapi.testclient import TestClient
    from main import app

    route = next(r for r in app.routes if getattr(r, "path", "") == "/media/{media_id}")
    assert "variant" in {p.name for p in route.dependant.query_params}

    client = TestClient(app)
    fake = uuid.uuid4()
    # a smaller copy of a private photo is still a private photo: every
    # variant is behind the same auth, and anonymous gets 401 before the
    # variant is even looked at
    for variant in ("raw", "display", "thumbnail", "nonsense"):
        got = client.get(f"/media/{fake}?variant={variant}")
        assert got.status_code == 401, variant


def test_erasure_takes_the_variants_too():
    import account_deletion

    asset = _asset(
        display_s3_key="f/x/b/y/variants/p-display.webp",
        thumbnail_s3_key="f/x/b/y/variants/p-thumbnail.webp",
        hot_s3_key=None,
        cold_s3_key=None,
    )
    keys = account_deletion.collect_media_keys([asset])
    assert asset.display_s3_key in keys and asset.thumbnail_s3_key in keys


# ── the worker's loop ──────────────────────────────────────────────────────


class _FakeDB:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_a_file_pillow_cannot_read_is_retired_not_retried(monkeypatch):
    """Otherwise the worker spends forever on one corrupt upload."""
    from scripts import media_worker

    asset = _asset(variants_error=None)
    db = _FakeDB()
    monkeypatch.setattr(media_worker.media_repo, "claim_for_variants", lambda _db: asset)

    def boom(_db, _asset):
        raise image_variants.UnreadableImage("cannot identify image file")

    monkeypatch.setattr(media_worker.media_repo, "build_variants", boom)
    recorded = {}
    monkeypatch.setattr(
        media_worker.media_repo,
        "record_variant_failure",
        lambda _db, a, reason: recorded.update(id=a.id, reason=reason),
    )
    assert media_worker.process_one(db) is True
    assert recorded["id"] == asset.id and "unreadable" in recorded["reason"]


def test_a_passing_failure_leaves_the_row_to_be_tried_again(monkeypatch):
    """S3 being briefly unreachable is not the photo's fault — the claim is
    left to go stale and the row comes back around."""
    from scripts import media_worker

    asset = _asset()
    db = _FakeDB()
    monkeypatch.setattr(media_worker.media_repo, "claim_for_variants", lambda _db: asset)

    def boom(_db, _asset):
        raise OSError("connection reset")

    monkeypatch.setattr(media_worker.media_repo, "build_variants", boom)
    retired = []
    monkeypatch.setattr(
        media_worker.media_repo,
        "record_variant_failure",
        lambda _db, a, reason: retired.append(a.id),
    )
    assert media_worker.process_one(db) is True  # handled, loop continues
    assert retired == []                          # but not retired
    assert db.rollbacks == 1


def test_nothing_waiting_is_not_work(monkeypatch):
    from scripts import media_worker

    monkeypatch.setattr(media_worker.media_repo, "claim_for_variants", lambda _db: None)
    assert media_worker.process_one(_FakeDB()) is False


def test_the_claim_only_ever_offers_photos_that_still_need_copies():
    """The predicate is the queue. Reading it here means a change to it has
    to be deliberate."""
    import inspect

    sql = inspect.getsource(media_repo.claim_for_variants)
    assert "kind = 'photo'" in sql
    assert "archived_at IS NULL" in sql
    assert "display_s3_key IS NULL" in sql
    assert "variants_error IS NULL" in sql
    # two workers must never take the same row
    assert "FOR UPDATE SKIP LOCKED" in sql
    # and a claim is committed before any S3 work begins
    assert "db.commit()" in sql
