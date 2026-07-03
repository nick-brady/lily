"""Theme palettes for gift artwork — a small, stable subset of
`frontend/src/utils/themes.js`.

Artwork only needs a few tokens (background, ink, accent, a secondary
"dot" accent) plus fonts. We use the light-mode tokens (except `starry`,
which is dark-only). Fonts are the same pairing for every theme in v1:
Cormorant Garamond (vendored in assets/fonts, installed by Dockerfile.dev)
for names and display lines, Montserrat (Debian package) for letterspaced
caps labels and numerals — Cormorant/EB Garamond's old-style figures are
unreadable at stat sizes ("1" renders like a small-caps ɪ).
"""
from __future__ import annotations

from dataclasses import dataclass

# Family names of fonts installed in the backend image (see Dockerfile.dev).
DISPLAY_FONT = "Cormorant Garamond"
BODY_FONT = "Montserrat"


@dataclass(frozen=True)
class GiftPalette:
    bg: str
    ink: str
    accent: str
    dot: str
    display_font: str = DISPLAY_FONT
    body_font: str = BODY_FONT


# light-mode tokens lifted from themes.js (starry uses its dark tokens).
_PALETTES: dict[str, GiftPalette] = {
    "lily": GiftPalette(bg="#faf7fc", ink="#44364a", accent="#a21caf", dot="#d946ef"),
    "blossom": GiftPalette(bg="#fdf6f6", ink="#4a3438", accent="#e11d48", dot="#fb7185"),
    "dino": GiftPalette(bg="#f4f8ef", ink="#35443a", accent="#2f9e63", dot="#4cb87a"),
    "ocean": GiftPalette(bg="#f3f9fc", ink="#2e4a57", accent="#0284c7", dot="#38bdf8"),
    "golden": GiftPalette(bg="#fbf5ec", ink="#4a3b28", accent="#b45309", dot="#e9a23b"),
    "starry": GiftPalette(bg="#101a33", ink="#dde4f5", accent="#c9a23f", dot="#e8cd8a"),
}

_DEFAULT = "lily"


def for_theme(theme: str | None) -> GiftPalette:
    return _PALETTES.get(theme or _DEFAULT, _PALETTES[_DEFAULT])
