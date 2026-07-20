"""Signed gift-artwork links — the short URLs Printful fetches artwork
through (mockups + order print files). The whole point is staying under
Printful's 1000-character URL cap, so length is part of the contract."""
from __future__ import annotations

import uuid

from artwork_links import signed_artwork_url, verify_artwork_sig


def _parse(url: str) -> tuple[str, int, str]:
    path, _, query = url.partition("?")
    rid = path.rsplit("/", 1)[1].removesuffix(".png")
    params = dict(p.split("=") for p in query.split("&"))
    return rid, int(params["exp"]), params["sig"]


def test_roundtrip_and_length():
    rid = uuid.uuid4()
    url = signed_artwork_url(rid, expires_in=3600)
    parsed_rid, exp, sig = _parse(url)
    assert parsed_rid == str(rid)
    assert verify_artwork_sig(parsed_rid, exp, sig)
    # Printful rejects URLs over 1000 chars — the cap that broke presigned S3
    assert len(url) < 250


def test_tampered_id_or_sig_fails():
    url = signed_artwork_url(uuid.uuid4(), expires_in=3600)
    _, exp, sig = _parse(url)
    assert not verify_artwork_sig(str(uuid.uuid4()), exp, sig)
    assert not verify_artwork_sig(_parse(url)[0], exp, "0" * 32)
    # extending the expiry invalidates the signature
    assert not verify_artwork_sig(_parse(url)[0], exp + 999, sig)


def test_expired_fails():
    rid = uuid.uuid4()
    url = signed_artwork_url(rid, expires_in=-10)
    parsed_rid, exp, sig = _parse(url)
    assert not verify_artwork_sig(parsed_rid, exp, sig)
