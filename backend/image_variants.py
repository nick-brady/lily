"""Smaller copies of an image, so a browser never downloads a 4000px photo
to draw a 57px tile.

One decode, many sizes. Every surface that shows a picture wants a different
one of them, and the difference is not small: a phone photo off the camera is
~3.4MB, the same photo at 1600px is ~223KB, and at 320px it's ~15KB.

    raw        the original upload, untouched — the lightbox, the export,
               anything printed
    display    1600px — the timeline, the crop box, what gift artwork embeds
    thumbnail  320px  — pickers, strips, glyphs; anything scanned, not read

`display` is 1600 because that is what the surfaces actually ask for: the
timeline photo is 736x384 CSS, which is 1472 device pixels on a 2x screen,
and gift_artwork caps its embedded photos at 1600 too. The one thing that
could want more is a full-screen lightbox on a big retina display — and that
is better served by the original, on demand, than by making every timeline
photo 60% heavier.
"""
from __future__ import annotations

import io
import logging

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# variant name -> (longest edge in px, WebP quality)
SIZES: dict[str, tuple[int, int]] = {
    "display": (1600, 82),
    "thumbnail": (320, 85),
}
CONTENT_TYPE = "image/webp"


class UnreadableImage(Exception):
    """The bytes we were given aren't an image we can work with."""


def _prepare(raw: bytes) -> Image.Image:
    """The image, upright and opaque, ready to be resized.

    Two corrections worth making once rather than per size: phone cameras
    record orientation in EXIF rather than in the pixels, so a portrait photo
    arrives on its side; and a PNG with transparency saved as WebP over a
    black default looks broken, so alpha is flattened onto white.
    """
    try:
        im = Image.open(io.BytesIO(raw))
        im = ImageOps.exif_transpose(im)
    except Exception as exc:  # noqa: BLE001 - Pillow raises a grab-bag
        raise UnreadableImage(str(exc)) from exc
    if im.mode in ("RGBA", "LA", "P"):
        if im.mode == "P":
            im = im.convert("RGBA")
        white = Image.new("RGB", im.size, (255, 255, 255))
        white.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
        return white
    return im.convert("RGB") if im.mode != "RGB" else im


def encode(im: Image.Image, size: int, quality: int) -> bytes:
    """One copy of an already-prepared image, no larger than `size` a side.
    Smaller than that is left alone — upscaling adds bytes, not detail."""
    copy = im.copy()
    copy.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    copy.save(buf, "WEBP", quality=quality, method=4)
    return buf.getvalue()


def build(raw: bytes, sizes: dict[str, tuple[int, int]] | None = None) -> tuple[dict[str, bytes], tuple[int, int]]:
    """Every variant of one image, and the original's true dimensions.

    Returns ({name: webp bytes}, (width, height)). The dimensions are the
    upright ones — after the EXIF rotation, which is what anything laying out
    the photo actually needs. Raises UnreadableImage, and nothing else.
    """
    im = _prepare(raw)
    out = {name: encode(im, size, quality) for name, (size, quality) in (sizes or SIZES).items()}
    return out, im.size


def encode_one(raw: bytes, size: int, quality: int) -> bytes | None:
    """A single smaller copy of some bytes, or None if they can't be read.

    For callers where a derivative is a convenience rather than the point —
    a gift page's thumbnail should never be the reason a render fails.
    """
    try:
        return encode(_prepare(raw), size, quality)
    except Exception:  # noqa: BLE001 - never fail a caller for a thumbnail
        logger.warning("variant failed", exc_info=True)
        return None
