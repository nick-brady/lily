"""Short signed URLs for gift artwork.

Printful fetches artwork by URL — for mockup generation and for order
print files. Presigned S3 URLs won't do: on the prod box they're signed
with the EC2 instance role, which embeds a session token that blows past
Printful's 1000-character URL cap, and they can't outlive the role session
anyway (order drafts sit in the dashboard for days). Instead the app
serves the artwork itself through a compact HMAC link: ~120 characters,
explicit expiry, no auth — possession of a valid signature is the
credential (same trust model as a presigned URL, minus the bulk).
"""
from __future__ import annotations

import os

import hashlib
import hmac
import time
import uuid

from auth import FRONTEND_URL, JWT_SECRET_KEY

# Where the partner fetches artwork from. Normally the site itself; in local
# dev it's a tunnel (scripts/dev-tunnel.sh), because Printful can't reach
# localhost and every mockup here used to fail with "Invalid URL". Kept apart
# from FRONTEND_URL on purpose: that one also decides cookie security and
# Stripe's return address, and pointing it at a tunnel would break login.
ARTWORK_PUBLIC_URL = os.environ.get("ARTWORK_PUBLIC_URL") or FRONTEND_URL


def _sig(rendering_id: str, exp: int, page: str | None = None) -> str:
    subject = f"{rendering_id}/{page}" if page else rendering_id
    mac = hmac.new(
        JWT_SECRET_KEY.encode(),
        f"gift-artwork:{subject}:{exp}".encode(),
        hashlib.sha256,
    )
    return mac.hexdigest()[:32]


def signed_artwork_url(
    rendering_id: uuid.UUID | str, *, expires_in: int, page: str | None = None
) -> str:
    """Public URL for a rendering's artwork, fetchable by Printful.
    Routed via the site's /api prefix (nginx strips it). `page` addresses one
    file of a many-file design (the book's cover or a page)."""
    rid = str(rendering_id)
    exp = int(time.time()) + expires_in
    if page:
        return f"{ARTWORK_PUBLIC_URL}/api/gift-artwork/{rid}/{page}.png?exp={exp}&sig={_sig(rid, exp, page)}"
    return f"{ARTWORK_PUBLIC_URL}/api/gift-artwork/{rid}.png?exp={exp}&sig={_sig(rid, exp)}"


def verify_artwork_sig(
    rendering_id: uuid.UUID | str, exp: int, sig: str, page: str | None = None
) -> bool:
    if exp < time.time():
        return False
    return hmac.compare_digest(_sig(str(rendering_id), exp, page), sig)
