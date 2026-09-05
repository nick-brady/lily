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


def test_mockup_links_are_signed_apart_from_artwork_links():
    import uuid
    from urllib.parse import parse_qs, urlparse

    from artwork_links import signed_mockup_url

    rid = uuid.uuid4()
    url = signed_mockup_url(rid, expires_in=3600)
    assert f"/api/gift-mockup/{rid}.jpg" in url
    q = parse_qs(urlparse(url).query)
    exp, sig = int(q["exp"][0]), q["sig"][0]
    assert verify_artwork_sig(rid, exp, sig, "mockup")
    assert not verify_artwork_sig(rid, exp, sig)  # not a valid artwork link


def test_the_email_shows_the_photograph_when_there_is_one():
    import uuid
    from types import SimpleNamespace

    import gift_receipt_email as rcpt

    rid = uuid.uuid4()
    with_photo = SimpleNamespace(id=rid, mockup_s3_key="mockups/x.jpg")
    design_only = SimpleNamespace(id=rid, mockup_s3_key=None)
    assert "/api/gift-mockup/" in rcpt.email_image_url(with_photo)
    assert "/api/gift-artwork/" in rcpt.email_image_url(design_only)
    assert rcpt.email_image_url(None) is None
    assert 'alt="Arrival Story"' in rcpt.WORDMARK_HTML and "wordmark-email.png" in rcpt.WORDMARK_HTML
