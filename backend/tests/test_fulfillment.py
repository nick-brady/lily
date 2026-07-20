"""Fulfillment tests.

The Printful adapter is driven against a mocked httpx transport (no real
Printful calls). The product-mockup get-or-create semantics are exercised with
a lightweight fake session so we don't need a live database.
"""
from __future__ import annotations

import json

import httpx
import pytest

import fulfillment
from fulfillment import products as fulfillment_products
from fulfillment.base import MockupError
from fulfillment.printful import PrintfulAdapter

# White Glossy Mug 11oz — Printful's own docs example.
_MUG = {
    "product_id": 19,
    "variant_id": 1320,
    "placement": "default",
    "artwork_width": 2475,
    "artwork_height": 1155,
}


def _adapter(handler, **kw):
    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.printful.com"
    )
    return PrintfulAdapter(
        api_key="test-key", client=client, poll_interval_seconds=0, **kw
    )


# ── Printful adapter ──────────────────────────────────────────────────────


def test_generate_mockup_happy_path(monkeypatch):
    state = {"polls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST" and req.url.path == "/mockup-generator/create-task/19":
            assert "Bearer test-key" in req.headers["authorization"]
            # the API rejects tasks without a position block (MG-4)
            body = json.loads(req.read())
            assert body["files"][0]["position"] == {
                "area_width": 2475,
                "area_height": 1155,
                "width": 2475,
                "height": 1155,
                "top": 0,
                "left": 0,
            }
            return httpx.Response(200, json={"result": {"task_key": "abc"}})
        if req.method == "GET" and req.url.path == "/mockup-generator/task":
            state["polls"] += 1
            if state["polls"] < 2:
                return httpx.Response(200, json={"result": {"status": "pending"}})
            return httpx.Response(
                200,
                json={
                    "result": {
                        "status": "completed",
                        "mockups": [{"mockup_url": "https://m.test/x.png"}],
                    }
                },
            )
        return httpx.Response(404)

    monkeypatch.setattr(
        "fulfillment.printful.httpx.get",
        lambda url, **kw: httpx.Response(
            200,
            content=b"\x89PNG\r\n\x1a\nDATA",
            headers={"content-type": "image/png"},
            request=httpx.Request("GET", url),
        ),
    )
    res = _adapter(handler).generate_mockup(artwork_url="https://art.test/a.png", **_MUG)
    assert res.image_bytes.startswith(b"\x89PNG")
    assert res.source_url == "https://m.test/x.png"
    assert res.content_type == "image/png"
    assert state["polls"] >= 2


def test_generate_mockup_failed_status():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"result": {"task_key": "abc"}})
        return httpx.Response(200, json={"result": {"status": "failed"}})

    with pytest.raises(MockupError):
        _adapter(handler).generate_mockup(artwork_url="u", **_MUG)


def test_generate_mockup_times_out():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"result": {"task_key": "abc"}})
        return httpx.Response(200, json={"result": {"status": "pending"}})

    with pytest.raises(MockupError):
        _adapter(handler, poll_attempts=3).generate_mockup(artwork_url="u", **_MUG)


def test_get_adapter_gated_on_env(monkeypatch):
    monkeypatch.delenv("PRINTFUL_API_KEY", raising=False)
    assert fulfillment.get_adapter() is None
    monkeypatch.setenv("PRINTFUL_API_KEY", "test-key")
    assert isinstance(fulfillment.get_adapter(), PrintfulAdapter)


# ── Product shortlist registry ──────────────────────────────────────────────


def test_shortlist_mug_products():
    keys = {p.key for p in fulfillment_products.for_product_kind("mug")}
    assert {"white_glossy_11oz", "latte_mug", "black_glossy_11oz"} <= keys
    assert fulfillment_products.for_product_kind("unknown_kind") == []


def test_default_product_for_mug():
    default = fulfillment_products.default_for_product_kind("mug")
    assert default is not None and default.key == "white_glossy_11oz"
    assert fulfillment_products.default_for_product_kind("storage_5yr") is None


def test_get_unknown_product_is_none():
    assert fulfillment_products.get("does_not_exist") is None
    assert fulfillment_products.get("latte_mug").product_id == 837


# ── Product-mockup get-or-create ────────────────────────────────────────────


class _FakeRendering:
    def __init__(self, rid="r1"):
        self.id = rid


class _FakeMockupRow:
    def __init__(self, status):
        self.status = status
        self.mockup_s3_key = "some/key" if status == "ready" else None


class _FakeSession:
    """Records add/commit and returns a fixed row from `scalar` regardless of
    the statement — enough to exercise get_or_create's branching."""

    def __init__(self, existing=None):
        self._existing = existing
        self.added = []
        self.commits = 0

    def scalar(self, _stmt):
        return self._existing

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):  # pragma: no cover - not hit in these tests
        pass


def test_get_or_create_creates_when_absent():
    from repositories import gifts as gifts_repo

    db = _FakeSession(existing=None)
    row, should_render = gifts_repo.get_or_create_product_mockup(
        db, rendering=_FakeRendering(), product_key="latte_mug"
    )
    assert should_render is True
    assert len(db.added) == 1
    assert row.status == "pending"
    assert row.product_key == "latte_mug"


def test_get_or_create_returns_cached_ready_without_scheduling():
    from repositories import gifts as gifts_repo

    cached = _FakeMockupRow(status="ready")
    db = _FakeSession(existing=cached)
    row, should_render = gifts_repo.get_or_create_product_mockup(
        db, rendering=_FakeRendering(), product_key="latte_mug"
    )
    assert row is cached
    assert should_render is False
    assert db.added == []


def test_get_or_create_retries_failed_row():
    from repositories import gifts as gifts_repo

    cached = _FakeMockupRow(status="failed")
    db = _FakeSession(existing=cached)
    row, should_render = gifts_repo.get_or_create_product_mockup(
        db, rendering=_FakeRendering(), product_key="latte_mug"
    )
    assert row is cached
    assert should_render is True
    assert row.status == "pending"
    assert row.mockup_s3_key is None
