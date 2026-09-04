"""Tell Printful where to send its webhooks.

    # on the box, with the app's environment (never `source` the .env):
    sudo systemd-run --wait --pipe --uid=lily --gid=lily \\
        --property=EnvironmentFile=/opt/lily/backend/.env \\
        --working-directory=/opt/lily/backend \\
        /opt/lily/venv/bin/python scripts/register_printful_webhook.py

Printful keeps one webhook configuration per store; POST /webhooks replaces
it, so this is safe to run again after a change. The URL carries
PRINTFUL_WEBHOOK_TOKEN because Printful does not sign its webhooks — the
token in the path is the only thing that says a request is theirs.
"""
from __future__ import annotations

import os
import sys

import httpx

EVENTS = ["package_shipped", "order_failed", "order_canceled", "order_put_hold", "order_remove_hold"]


def main() -> int:
    key = os.environ.get("PRINTFUL_API_KEY")
    token = os.environ.get("PRINTFUL_WEBHOOK_TOKEN")
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if not (key and token and base):
        print("need PRINTFUL_API_KEY, PRINTFUL_WEBHOOK_TOKEN and FRONTEND_URL", file=sys.stderr)
        return 2
    headers = {"Authorization": f"Bearer {key}"}
    if os.environ.get("PRINTFUL_STORE_ID"):
        headers["X-PF-Store-Id"] = os.environ["PRINTFUL_STORE_ID"]
    url = f"{base}/api/webhooks/printful/{token}"
    resp = httpx.post(
        "https://api.printful.com/webhooks",
        headers=headers,
        json={"url": url, "types": EVENTS},
        timeout=30,
    )
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    result = body.get("result")
    masked = lambda text: str(text).replace(token, token[:4] + "…")  # noqa: E731 - the token is a secret
    if resp.status_code != 200 or not isinstance(result, dict):
        # Printful answers errors with a string in `result`; the common one is
        # a token missing the webhooks/read and webhooks/write scopes
        print(resp.status_code, masked(result or body), file=sys.stderr)
        return 1
    print(resp.status_code, masked(result.get("url") or url), result.get("types"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
