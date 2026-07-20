"""Printful fulfillment adapter — product mockups via the Mockup Generator API.

Flow (https://developers.printful.com, Mockup Generator API):
  1. POST /mockup-generator/create-task/{product_id}  → returns a task_key
  2. GET  /mockup-generator/task?task_key=...          → poll until completed
  3. download the returned mockup image

Auth is a Bearer token (a private/store token from the Printful dashboard);
account-level tokens also send an X-PF-Store-Id header.

The product/variant to render onto is chosen by the caller from the curated
shortlist (`fulfillment.products`) and passed explicitly.
"""
from __future__ import annotations

import time

import httpx

from fulfillment.base import (
    FulfillmentAdapter,
    MockupError,
    MockupResult,
    OrderError,
    OrderResult,
)

_BASE_URL = "https://api.printful.com"

_POLL_ATTEMPTS = 12
_POLL_INTERVAL_SECONDS = 3
_REQUEST_TIMEOUT = 30.0


class PrintfulAdapter(FulfillmentAdapter):
    name = "printful"

    def __init__(
        self,
        *,
        api_key: str,
        store_id: str | None = None,
        client: httpx.Client | None = None,
        poll_attempts: int = _POLL_ATTEMPTS,
        poll_interval_seconds: float = _POLL_INTERVAL_SECONDS,
    ) -> None:
        self._poll_attempts = poll_attempts
        self._poll_interval = poll_interval_seconds
        headers = {"Authorization": f"Bearer {api_key}"}
        if store_id:
            headers["X-PF-Store-Id"] = str(store_id)
        # The injected client (tests) is used as-is; otherwise build a default.
        self._client = client or httpx.Client(
            base_url=_BASE_URL, headers=headers, timeout=_REQUEST_TIMEOUT
        )
        # When a client is injected we still need auth headers on it.
        if client is not None:
            self._client.headers.update(headers)

    def generate_mockup(
        self,
        *,
        artwork_url: str,
        product_id: int,
        variant_id: int,
        artwork_width: int,
        artwork_height: int,
        placement: str = "default",
    ) -> MockupResult:
        task_key = self._create_task(
            product_id=product_id,
            variant_id=variant_id,
            placement=placement,
            artwork_url=artwork_url,
            artwork_width=artwork_width,
            artwork_height=artwork_height,
        )
        mockup_url = self._poll_for_mockup(task_key)
        return self._download(mockup_url)

    def create_order(
        self,
        *,
        recipient: dict,
        items: list[dict],
        external_id: str,
        confirm: bool,
        gift: dict | None = None,
    ) -> OrderResult:
        """POST /orders. confirm=0 leaves the order as a dashboard draft
        (no charge until a human approves it); `gift` prints a note on the
        packing slip."""
        body: dict = {
            "external_id": external_id,
            "recipient": recipient,
            "items": items,
        }
        if gift:
            body["gift"] = gift
        try:
            resp = self._client.post(
                f"/orders?confirm={'1' if confirm else '0'}", json=body
            )
            resp.raise_for_status()
            result = (resp.json() or {}).get("result") or {}
            order_id = result.get("id")
            if order_id is None:
                raise OrderError("printful order response missing id")
            return OrderResult(order_id=str(order_id), status=result.get("status", ""))
        except httpx.HTTPError as exc:
            raise OrderError(f"printful order: {exc}") from exc

    def _create_task(
        self,
        *,
        product_id: int,
        variant_id: int,
        placement: str,
        artwork_url: str,
        artwork_width: int,
        artwork_height: int,
    ) -> str:
        body = {
            "variant_ids": [variant_id],
            "format": "png",
            "files": [
                {
                    "placement": placement,
                    "image_url": artwork_url,
                    # Required by the API (MG-4 without it). Our templates are
                    # drawn at the product's full print area, so the artwork
                    # covers the area edge to edge.
                    "position": {
                        "area_width": artwork_width,
                        "area_height": artwork_height,
                        "width": artwork_width,
                        "height": artwork_height,
                        "top": 0,
                        "left": 0,
                    },
                }
            ],
        }
        resp = self._client.post(
            f"/mockup-generator/create-task/{product_id}", json=body
        )
        resp.raise_for_status()
        task_key = (resp.json().get("result") or {}).get("task_key")
        if not task_key:
            raise MockupError("Printful create-task returned no task_key")
        return task_key

    def _poll_for_mockup(self, task_key: str) -> str:
        for _ in range(self._poll_attempts):
            resp = self._client.get(
                "/mockup-generator/task", params={"task_key": task_key}
            )
            resp.raise_for_status()
            result = resp.json().get("result") or {}
            status = result.get("status")
            if status == "completed":
                mockups = result.get("mockups") or []
                if not mockups or not mockups[0].get("mockup_url"):
                    raise MockupError("Printful task completed without a mockup_url")
                return mockups[0]["mockup_url"]
            if status == "failed":
                raise MockupError("Printful mockup task failed")
            time.sleep(self._poll_interval)
        raise MockupError("Printful mockup task timed out")

    def _download(self, url: str) -> MockupResult:
        resp = httpx.get(url, timeout=_REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return MockupResult(
            image_bytes=resp.content,
            content_type=resp.headers.get("content-type", "image/png"),
            source_url=url,
        )
