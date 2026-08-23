"""Fulfillment tests.

The Printful adapter is driven against a mocked httpx transport (no real
Printful calls). The product-mockup get-or-create semantics are exercised with
a lightweight fake session so we don't need a live database.
"""
from __future__ import annotations

import json
import time
import uuid
from types import SimpleNamespace

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
    kw.setdefault("mockup_interval_seconds", 0)  # don't wait out the real spacing
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
                        "mockups": [
                            {
                                "mockup_url": "https://m.test/x.png",
                                "extra": [
                                    {
                                        "title": "Handle from left",
                                        "url": "https://m.test/extra1.png",
                                        "option": "left",
                                        "option_group": "angle",
                                    },
                                    {
                                        "title": "Wrinkled front",
                                        "url": "https://m.test/extra2.png",
                                        "option": "wrinkled",
                                        "option_group": "angle",
                                    },
                                ],
                            }
                        ],
                    }
                },
            )
        return httpx.Response(404)

    monkeypatch.setattr(
        "fulfillment.printful.httpx.get",
        lambda url, **kw: httpx.Response(
            200,
            content=b"\x89PNG\r\n\x1a\nDATA:" + str(url).encode(),
            headers={"content-type": "image/png"},
            request=httpx.Request("GET", url),
        ),
    )
    res = _adapter(handler).generate_mockup(artwork_url="https://art.test/a.png", **_MUG)
    assert res.image_bytes.startswith(b"\x89PNG")
    assert res.source_url == "https://m.test/x.png"
    assert res.content_type == "image/png"
    assert state["polls"] >= 2
    assert [e.title for e in res.extra] == ["Handle from left", "Wrinkled front"]
    assert res.extra[0].image_bytes.endswith(b"https://m.test/extra1.png")
    assert res.extra[0].content_type == "image/png"


def test_generate_mockup_without_extra(monkeypatch):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"result": {"task_key": "abc"}})
        return httpx.Response(
            200,
            json={
                "result": {
                    "status": "completed",
                    "mockups": [{"mockup_url": "https://m.test/x.png"}],
                }
            },
        )

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
    assert res.extra == []


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


# ── rate limiting ─────────────────────────────────────────────────────────
# Printful allows 2 mockup tasks a minute; a gallery re-render fires one per
# design, seconds apart. Both defences are covered: spacing before the call,
# and waiting out a 429 that lands anyway.


def _completed_task_handler(calls: list[str], rate_limited: int = 0):
    """A transport where the first `rate_limited` create-task calls come back
    429 and the rest succeed."""

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            calls.append(str(req.url))
            if len(calls) <= rate_limited:
                return httpx.Response(
                    429, headers={"retry-after": "0"}, json={"code": 429}
                )
            return httpx.Response(200, json={"result": {"task_key": "abc"}})
        return httpx.Response(
            200,
            json={
                "result": {
                    "status": "completed",
                    "mockups": [{"mockup_url": "https://m.test/x.png"}],
                }
            },
        )

    return handler


def _stub_download(monkeypatch):
    monkeypatch.setattr(
        "fulfillment.printful.httpx.get",
        lambda url, **kw: httpx.Response(
            200,
            content=b"\x89PNG\r\n\x1a\nDATA",
            headers={"content-type": "image/png"},
            request=httpx.Request("GET", url),
        ),
    )


def test_rate_limited_create_task_is_retried(monkeypatch):
    _stub_download(monkeypatch)
    calls: list[str] = []
    res = _adapter(_completed_task_handler(calls, rate_limited=1)).generate_mockup(
        artwork_url="https://art.test/a.png", **_MUG
    )
    assert res.image_bytes.startswith(b"\x89PNG")
    assert len(calls) == 2  # first 429, second accepted


def test_persistent_rate_limit_raises_mockup_error(monkeypatch):
    _stub_download(monkeypatch)
    calls: list[str] = []
    with pytest.raises(MockupError):
        _adapter(_completed_task_handler(calls, rate_limited=99)).generate_mockup(
            artwork_url="u", **_MUG
        )
    assert len(calls) == 3  # the attempt plus two retries, then give up


def test_retry_after_prefers_header_then_reset_then_default():
    adapter = _adapter(_completed_task_handler([]), mockup_interval_seconds=35)

    def resp(headers):
        return httpx.Response(429, headers=headers)

    assert adapter._retry_after_seconds(resp({"retry-after": "12"})) == 12
    # X-RateLimit-Reset is an epoch deadline, not a duration
    soon = time.time() + 20
    assert 15 <= adapter._retry_after_seconds(resp({"x-ratelimit-reset": str(soon)})) <= 21
    assert adapter._retry_after_seconds(resp({})) == 35
    # a partner can't park a worker for the afternoon
    assert adapter._retry_after_seconds(resp({"retry-after": "99999"})) == 90
    # Retry-After may be an HTTP date — fall back rather than crash
    assert adapter._retry_after_seconds(
        resp({"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"})
    ) == 35


def test_mockup_tasks_are_spaced_process_wide(monkeypatch):
    """Two back-to-back mockups must not both hit the partner at once — the
    second waits out the interval before its create-task."""
    _stub_download(monkeypatch)
    slept: list[float] = []
    monkeypatch.setattr("fulfillment.printful.time.sleep", lambda s: slept.append(s))
    monkeypatch.setattr("fulfillment.printful._last_mockup_task_at", None)

    calls: list[str] = []
    adapter = _adapter(_completed_task_handler(calls), mockup_interval_seconds=35)
    adapter.generate_mockup(artwork_url="https://art.test/a.png", **_MUG)
    adapter.generate_mockup(artwork_url="https://art.test/b.png", **_MUG)

    assert len(calls) == 2
    assert slept and 30 < slept[0] <= 35


def test_get_adapter_gated_on_env(monkeypatch):
    monkeypatch.delenv("PRINTFUL_API_KEY", raising=False)
    assert fulfillment.get_adapter() is None
    monkeypatch.setenv("PRINTFUL_API_KEY", "test-key")
    assert isinstance(fulfillment.get_adapter(), PrintfulAdapter)


# ── Product shortlist registry ──────────────────────────────────────────────


def test_shortlist_mug_products():
    keys = {p.key for p in fulfillment_products.for_product_kind("mug")}
    assert {"white_glossy_11oz", "latte_mug", "white_glossy_20oz"} <= keys
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


# ── hero-mockup retry ───────────────────────────────────────────────────────
# The regression: a gallery re-render fired three mug mockups inside 20s, the
# partner rate-limited the third, and that design showed its flat wrap
# artwork from then on — nothing ever tried again.


def _rendering_row(mockup_status, *, status=None, artwork_key="k"):
    from models import GiftRenderingStatus

    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status or GiftRenderingStatus.ready,
        artwork_s3_key=artwork_key,
        mockup_status=mockup_status,
    )


def _retryable(monkeypatch, rows):
    from repositories import gifts as gifts_repo

    monkeypatch.setenv("PRINTFUL_API_KEY", "test-key")
    monkeypatch.setattr(
        gifts_repo, "list_renderings_for_birth", lambda db, *, birth_id: rows
    )
    return gifts_repo.ids_needing_mockup_retry(None, birth_id=uuid.uuid4())


def test_failed_and_orphaned_mockups_are_retried(monkeypatch):
    from models import GiftRenderingStatus

    failed = _rendering_row("failed")
    orphaned = _rendering_row("pending")  # a restart killed its render
    done = _rendering_row("ready")
    never_had_one = _rendering_row("none")  # no product mapped for its kind
    no_artwork = _rendering_row("failed", artwork_key=None)
    still_rendering = _rendering_row("failed", status=GiftRenderingStatus.pending)

    ids = _retryable(
        monkeypatch,
        [failed, orphaned, done, never_had_one, no_artwork, still_rendering],
    )
    assert ids == [failed.id, orphaned.id]


def test_no_retries_without_a_configured_partner(monkeypatch):
    monkeypatch.delenv("PRINTFUL_API_KEY", raising=False)
    from repositories import gifts as gifts_repo

    monkeypatch.setattr(
        gifts_repo,
        "list_renderings_for_birth",
        lambda db, *, birth_id: [_rendering_row("failed")],
    )
    assert gifts_repo.ids_needing_mockup_retry(None, birth_id=uuid.uuid4()) == []


def test_retries_back_off_so_a_polling_gallery_cant_hammer_the_partner():
    """The gallery polls every few seconds; a design that keeps failing must
    not turn that into a request per poll."""
    from repositories import gifts as gifts_repo

    rid = uuid.uuid4()
    assert gifts_repo._mockup_retry_due(rid)  # never tried — go now
    try:
        gifts_repo._record_mockup_retry(rid, succeeded=False)
        assert not gifts_repo._mockup_retry_due(rid)

        first = gifts_repo._mockup_retries[rid][1]
        gifts_repo._record_mockup_retry(rid, succeeded=False)
        assert gifts_repo._mockup_retries[rid][1] > first  # widening

        gifts_repo._record_mockup_retry(rid, succeeded=True)
        assert rid not in gifts_repo._mockup_retries
        assert gifts_repo._mockup_retry_due(rid)
    finally:
        gifts_repo._mockup_retries.pop(rid, None)


def test_backoff_is_capped():
    from repositories import gifts as gifts_repo

    rid = uuid.uuid4()
    try:
        for _ in range(20):
            gifts_repo._record_mockup_retry(rid, succeeded=False)
        wait = gifts_repo._mockup_retries[rid][1] - time.monotonic()
        assert wait <= gifts_repo._MOCKUP_RETRY_BACKOFF_MAX.total_seconds()
    finally:
        gifts_repo._mockup_retries.pop(rid, None)


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
