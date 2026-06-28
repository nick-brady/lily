"""Printful fulfillment adapter — product mockups via the Mockup Generator API.

Flow (https://developers.printful.com, Mockup Generator API):
  1. POST /mockup-generator/create-task/{product_id}  → returns a task_key
  2. GET  /mockup-generator/task?task_key=...          → poll until completed
  3. download the returned mockup image

Auth is a Bearer token (a private/store token from the Printful dashboard);
account-level tokens also send an X-PF-Store-Id header.

Product/variant IDs come from the Printful catalog and must be filled in for
each product (see PRODUCT_MAP / the PRINTFUL_PRODUCT_MAP env override). Until a
variant is mapped, `supports()` is False and the gallery keeps the flat
artwork.
"""
from __future__ import annotations

import json
import os
import time

import httpx

from fulfillment.base import FulfillmentAdapter, MockupError, MockupResult

_BASE_URL = "https://api.printful.com"

# product_kind -> Printful catalog ids. variant_id is intentionally None until
# you pick the exact product variant in the Printful catalog; override the
# whole map (or just the ids) with the PRINTFUL_PRODUCT_MAP env var (JSON).
DEFAULT_PRODUCT_MAP: dict[str, dict] = {
    "mug": {"product_id": 19, "variant_id": None, "placement": "default"},
    "birth_announcement_cards": {
        "product_id": None,
        "variant_id": None,
        "placement": "default",
    },
}

_POLL_ATTEMPTS = 12
_POLL_INTERVAL_SECONDS = 3
_REQUEST_TIMEOUT = 30.0


def _load_product_map() -> dict[str, dict]:
    raw = os.getenv("PRINTFUL_PRODUCT_MAP")
    if not raw:
        return dict(DEFAULT_PRODUCT_MAP)
    merged = dict(DEFAULT_PRODUCT_MAP)
    try:
        merged.update(json.loads(raw))
    except (ValueError, TypeError):
        pass  # malformed override → fall back to defaults
    return merged


class PrintfulAdapter(FulfillmentAdapter):
    name = "printful"

    def __init__(
        self,
        *,
        api_key: str,
        store_id: str | None = None,
        product_map: dict[str, dict] | None = None,
        client: httpx.Client | None = None,
        poll_attempts: int = _POLL_ATTEMPTS,
        poll_interval_seconds: float = _POLL_INTERVAL_SECONDS,
    ) -> None:
        self._product_map = product_map if product_map is not None else _load_product_map()
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

    def supports(self, product_kind: str) -> bool:
        m = self._product_map.get(product_kind)
        return bool(m and m.get("product_id") and m.get("variant_id"))

    def generate_mockup(self, *, artwork_url: str, product_kind: str) -> MockupResult:
        m = self._product_map.get(product_kind)
        if not (m and m.get("product_id") and m.get("variant_id")):
            raise MockupError(f"no Printful mapping for {product_kind}")

        task_key = self._create_task(
            product_id=m["product_id"],
            variant_id=m["variant_id"],
            placement=m.get("placement", "default"),
            artwork_url=artwork_url,
        )
        mockup_url = self._poll_for_mockup(task_key)
        return self._download(mockup_url)

    def _create_task(
        self, *, product_id: int, variant_id: int, placement: str, artwork_url: str
    ) -> str:
        body = {
            "variant_ids": [variant_id],
            "format": "png",
            "files": [{"placement": placement, "image_url": artwork_url}],
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
