"""Printful fulfillment adapter — product mockups via the Mockup Generator API.

Flow (https://developers.printful.com, Mockup Generator API):
  1. POST /mockup-generator/create-task/{product_id}  → returns a task_key
  2. GET  /mockup-generator/task?task_key=...          → poll until completed
  3. download the returned mockup image, plus any `extra` angle/view
     mockups the same task produced (e.g. a mug's handle-from-left shot —
     not every product has these)

Auth is a Bearer token (a private/store token from the Printful dashboard);
account-level tokens also send an X-PF-Store-Id header.

The product/variant to render onto is chosen by the caller from the curated
shortlist (`fulfillment.products`) and passed explicitly.

Printful rate-limits the Mockup Generator to 2 calls per minute per store,
which a re-render of a birth's gallery blows straight through — one design
after another, seconds apart. Two defences, because either alone leaves a
design without a mockup: calls are spaced process-wide before they are sent
(`_mockup_rate_limit`), and a 429 that still gets through is waited out and
retried (`_request`).
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

import httpx

from fulfillment.base import (
    FulfillmentAdapter,
    MockupError,
    MockupExtra,
    MockupResult,
    OrderError,
    OrderResult,
)

_BASE_URL = "https://api.printful.com"

_POLL_ATTEMPTS = 12
_POLL_INTERVAL_SECONDS = 3
_REQUEST_TIMEOUT = 30.0

# Spacing between mockup tasks: 2 per minute is the documented limit, so 35s
# leaves headroom for clock skew and for the retry path below.
_MOCKUP_INTERVAL_SECONDS = 35.0
_RATE_LIMIT_RETRIES = 2
# A partner-supplied backoff is trusted only this far — a bogus Retry-After
# must not park a background thread for the afternoon.
_MAX_RETRY_WAIT_SECONDS = 90.0

# Module-level, not per-instance: `fulfillment.get_adapter()` builds a fresh
# adapter per call, and the limit is per store, not per object. A single
# uvicorn worker (see repositories/gifts.py) is what makes a process-local
# gate sufficient.
_mockup_gate = threading.Lock()
_last_mockup_task_at: float | None = None


@contextmanager
def _mockup_rate_limit(min_interval: float):
    """Serialize mockup tasks process-wide, `min_interval` seconds apart.
    The wait happens while holding the gate, so callers queue up rather than
    all waking at once."""
    global _last_mockup_task_at
    with _mockup_gate:
        if min_interval > 0 and _last_mockup_task_at is not None:
            wait = min_interval - (time.monotonic() - _last_mockup_task_at)
            if wait > 0:
                time.sleep(wait)
        try:
            yield
        finally:
            _last_mockup_task_at = time.monotonic()


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
        mockup_interval_seconds: float = _MOCKUP_INTERVAL_SECONDS,
    ) -> None:
        self._poll_attempts = poll_attempts
        self._poll_interval = poll_interval_seconds
        self._mockup_interval = mockup_interval_seconds
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
        try:
            with _mockup_rate_limit(self._mockup_interval):
                task_key = self._create_task(
                    product_id=product_id,
                    variant_id=variant_id,
                    placement=placement,
                    artwork_url=artwork_url,
                    artwork_width=artwork_width,
                    artwork_height=artwork_height,
                )
            mockup_url, extra = self._poll_for_mockup(task_key)
            result = self._download(mockup_url)
            for item in extra:
                url = item.get("url")
                if not url:
                    continue
                image_bytes, content_type = self._download_bytes(url)
                result.extra.append(
                    MockupExtra(
                        title=item.get("title") or "",
                        image_bytes=image_bytes,
                        content_type=content_type,
                    )
                )
            return result
        except httpx.HTTPError as exc:
            # The adapter contract is MockupError; a transport/status error
            # reaching the caller as httpx would leak the vendor.
            raise MockupError(f"printful mockup: {exc}") from exc

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
        resp = self._request(
            "POST", f"/mockup-generator/create-task/{product_id}", json=body
        )
        task_key = (resp.json().get("result") or {}).get("task_key")
        if not task_key:
            raise MockupError("Printful create-task returned no task_key")
        return task_key

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Send a mockup-generator request, waiting out a 429 and retrying.
        Printful's own Retry-After is the authority on how long; the
        X-RateLimit-Reset epoch is the fallback, and our own spacing the
        last resort."""
        for attempt in range(_RATE_LIMIT_RETRIES + 1):
            resp = self._client.request(method, url, **kwargs)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            if attempt == _RATE_LIMIT_RETRIES:
                break
            time.sleep(self._retry_after_seconds(resp))
        raise MockupError("Printful rate limit exceeded")

    def _retry_after_seconds(self, resp: httpx.Response) -> float:
        for value, is_deadline in (
            (resp.headers.get("retry-after"), False),
            (resp.headers.get("x-ratelimit-reset"), True),
        ):
            if not value:
                continue
            try:
                seconds = float(value) - (time.time() if is_deadline else 0.0)
            except ValueError:  # Retry-After may be an HTTP date
                continue
            return min(max(seconds, 0.0), _MAX_RETRY_WAIT_SECONDS)
        return min(
            self._mockup_interval or _MOCKUP_INTERVAL_SECONDS, _MAX_RETRY_WAIT_SECONDS
        )

    def _poll_for_mockup(self, task_key: str) -> tuple[str, list[dict]]:
        for _ in range(self._poll_attempts):
            resp = self._request(
                "GET", "/mockup-generator/task", params={"task_key": task_key}
            )
            result = resp.json().get("result") or {}
            status = result.get("status")
            if status == "completed":
                mockups = result.get("mockups") or []
                if not mockups or not mockups[0].get("mockup_url"):
                    raise MockupError("Printful task completed without a mockup_url")
                return mockups[0]["mockup_url"], mockups[0].get("extra") or []
            if status == "failed":
                raise MockupError("Printful mockup task failed")
            time.sleep(self._poll_interval)
        raise MockupError("Printful mockup task timed out")

    def _download_bytes(self, url: str) -> tuple[bytes, str]:
        resp = httpx.get(url, timeout=_REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", "image/png")

    def _download(self, url: str) -> MockupResult:
        image_bytes, content_type = self._download_bytes(url)
        return MockupResult(
            image_bytes=image_bytes, content_type=content_type, source_url=url
        )
