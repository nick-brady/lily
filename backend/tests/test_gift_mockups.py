"""The hero product mockup: which mug it photographs, and what stays on
screen when the partner refuses. DB-free — the session is a stub."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from fulfillment.base import MockupError, MockupResult
from models import Birth, GiftCatalogItem, GiftRendering, GiftRenderingStatus
from repositories import gifts as gifts_repo


class _FakeSession:
    """Just enough Session for `_try_generate_mockup`: it looks up the
    catalog item and the birth, and commits."""

    def __init__(self, rendering, item, birth):
        self._rows = {
            GiftCatalogItem: item,
            Birth: birth,
            GiftRendering: rendering,
        }

    def get(self, model, _id):
        return self._rows.get(model)

    def commit(self):
        pass

    def rollback(self):
        pass


def _fixtures(product_key):
    birth = Birth(id=uuid.uuid4(), family_id=uuid.uuid4())
    item = GiftCatalogItem(id=uuid.uuid4(), product_kind="mug")
    rendering = GiftRendering(
        id=uuid.uuid4(),
        birth_id=birth.id,
        gift_catalog_item_id=item.id,
        template_id="mug_hours",
        status=GiftRenderingStatus.ready,
        artwork_s3_key="art.png",
        product_key=product_key,
        mockup_status="none",
        mockup_extras=[],
    )
    return rendering, _FakeSession(rendering, item, birth)


@pytest.fixture
def partner(monkeypatch):
    """Stub the partner and storage, and record what was asked for."""
    asked = {}

    def generate_mockup(**kwargs):
        asked.update(kwargs)
        return MockupResult(
            image_bytes=b"png", content_type="image/png", source_url="https://m/x.png"
        )

    monkeypatch.setattr(
        gifts_repo.fulfillment,
        "get_adapter",
        lambda: SimpleNamespace(generate_mockup=generate_mockup),
    )
    monkeypatch.setattr(gifts_repo, "signed_artwork_url", lambda *a, **k: "https://a/x.png")
    monkeypatch.setattr(gifts_repo, "put_object", lambda **k: None)
    monkeypatch.setattr(gifts_repo, "object_key", lambda **k: "mock.png")
    return asked


def test_the_mockup_photographs_the_mug_they_chose(partner):
    """The whole point of letting someone pick a mug is that the photo they
    approve is that mug. This used to send the store default no matter what
    was chosen, so a latte-mug order was approved on a white 11 oz."""
    rendering, db = _fixtures("latte_mug")

    gifts_repo._try_generate_mockup(db, rendering)

    assert partner["product_id"] == 837
    assert partner["variant_id"] == 21352
    assert rendering.mockup_status == "ready"


def test_no_choice_photographs_the_default(partner):
    rendering, db = _fixtures(None)

    gifts_repo._try_generate_mockup(db, rendering)

    assert partner["variant_id"] == 1320  # white glossy 11 oz


def test_a_retired_choice_photographs_what_would_ship(partner):
    """Same fallback the order takes — the two can't disagree."""
    rendering, db = _fixtures("black_glossy_15oz")

    gifts_repo._try_generate_mockup(db, rendering)

    assert partner["variant_id"] == 1320


def test_a_refused_mockup_keeps_the_photo_we_already_had(monkeypatch):
    """A failed *refresh* is not a lost photograph. The gallery kept showing
    an empty space after one refused request, even though the earlier shot
    was still sitting in S3."""
    rendering, db = _fixtures("latte_mug")
    rendering.mockup_s3_key = "old-mockup.png"
    rendering.mockup_extras = [{"title": "Handle on Left", "s3_key": "old-extra.png"}]
    rendering.mockup_status = "ready"

    def refuse(**kwargs):
        raise MockupError("partner said no")

    monkeypatch.setattr(
        gifts_repo.fulfillment,
        "get_adapter",
        lambda: SimpleNamespace(generate_mockup=refuse),
    )
    monkeypatch.setattr(gifts_repo, "signed_artwork_url", lambda *a, **k: "https://a/x.png")
    monkeypatch.setattr(gifts_repo, "presigned_get_url", lambda key: f"https://s3/{key}")

    gifts_repo._try_generate_mockup(db, rendering)

    assert rendering.mockup_status == "failed"  # the status is honest…
    # …and the photograph is still there to look at.
    assert gifts_repo.mockup_url(rendering) == "https://s3/old-mockup.png"
    assert [e["url"] for e in gifts_repo.mockup_extras(rendering)] == [
        "https://s3/old-extra.png"
    ]


def test_nothing_to_show_before_a_mockup_ever_lands(monkeypatch):
    monkeypatch.setattr(gifts_repo, "presigned_get_url", lambda key: f"https://s3/{key}")
    rendering, _ = _fixtures(None)

    assert gifts_repo.mockup_url(rendering) is None
    assert gifts_repo.mockup_extras(rendering) == []
