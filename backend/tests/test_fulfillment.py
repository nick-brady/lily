"""Printful adapter tests — drive the create-task → poll → download flow
against a mocked httpx transport (no real Printful calls)."""
from __future__ import annotations

import httpx
import pytest

import fulfillment
from fulfillment.base import MockupError
from fulfillment.printful import PrintfulAdapter

_MUG_MAP = {"mug": {"product_id": 19, "variant_id": 1320, "placement": "default"}}


def _adapter(handler, **kw):
    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.printful.com"
    )
    return PrintfulAdapter(
        api_key="test-key",
        product_map=dict(_MUG_MAP),
        client=client,
        poll_interval_seconds=0,
        **kw,
    )


def test_supports_requires_full_mapping():
    a = _adapter(lambda r: httpx.Response(200))
    assert a.supports("mug") is True
    assert a.supports("birth_announcement_cards") is False  # not in this map
    assert a.supports("unknown") is False


def test_generate_mockup_happy_path(monkeypatch):
    state = {"polls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST" and req.url.path == "/mockup-generator/create-task/19":
            assert "Bearer test-key" in req.headers["authorization"]
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
    res = _adapter(handler).generate_mockup(
        artwork_url="https://art.test/a.png", product_kind="mug"
    )
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
        _adapter(handler).generate_mockup(artwork_url="u", product_kind="mug")


def test_generate_mockup_times_out():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"result": {"task_key": "abc"}})
        return httpx.Response(200, json={"result": {"status": "pending"}})

    with pytest.raises(MockupError):
        _adapter(handler, poll_attempts=3).generate_mockup(
            artwork_url="u", product_kind="mug"
        )


def test_generate_mockup_unsupported_product():
    a = _adapter(lambda r: httpx.Response(200))
    with pytest.raises(MockupError):
        a.generate_mockup(artwork_url="u", product_kind="birth_announcement_cards")


def test_get_adapter_gated_on_env(monkeypatch):
    monkeypatch.delenv("PRINTFUL_API_KEY", raising=False)
    assert fulfillment.get_adapter() is None
    monkeypatch.setenv("PRINTFUL_API_KEY", "test-key")
    assert isinstance(fulfillment.get_adapter(), PrintfulAdapter)
