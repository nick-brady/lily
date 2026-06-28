"""Generate gift artwork (the design that goes ON a product) as SVG → PNG.

Pure Python, no browser: compute the birth's stats, pick a theme palette,
auto-select a hero photo, fill a Jinja2 SVG template, and rasterize with
cairosvg at the template's exact print pixels.
"""
from __future__ import annotations

import base64
from datetime import datetime

import cairosvg
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

import gift_stats
import gift_themes
from gift_templates import GiftTemplate
from models import Birth, MediaAsset, MediaKind, TimelineEvent
from storage import get_object_bytes

_TEMPLATE_DIR = "templates/gifts"

# Sparkline is drawn in this normalized coordinate space; templates place it
# with a nested <svg viewBox="0 0 1000 240" preserveAspectRatio="none">.
_SPARK_W = 1000
_SPARK_H = 240


class ArtworkError(Exception):
    """Rendering failed for a reason worth recording on the rendering row."""


_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["svg", "j2", "xml"], default=True),
)


def render(
    birth: Birth, template: GiftTemplate, db: Session
) -> tuple[bytes, dict]:
    """Render `template` for `birth`. Returns (png_bytes, rendering_metadata)."""
    events = list(
        db.scalars(
            select(TimelineEvent).where(
                TimelineEvent.birth_id == birth.id,
                TimelineEvent.deleted_at.is_(None),
            )
        ).all()
    )
    stats = gift_stats.compute(birth, events)
    palette = gift_themes.for_theme(birth.theme)

    photo = _select_hero_photo(db, birth) if template.photo else None
    photo_data_uri = _photo_data_uri(photo) if photo else None
    if template.photo and photo_data_uri is None:
        raise ArtworkError("missing-photo")

    when = birth.child_dob or birth.birth_completed_at
    context = {
        "w": template.width,
        "h": template.height,
        "p": palette,
        "child_name": (birth.child_name or "").strip() or "Baby",
        "birth_date": _fmt_date(when),
        "birth_time": _fmt_time(when),
        "count": stats.contraction_count,
        "labor_duration": _fmt_hms(stats.labor_duration_seconds),
        "avg_contraction": _fmt_ms(stats.avg_contraction_seconds),
        "avg_interval": _fmt_interval(stats.avg_interval_seconds),
        "has_sparkline": len(stats.durations) >= 2,
        "spark_line": _sparkline_polyline(stats.durations),
        "spark_area": _sparkline_area(stats.durations),
        "photo_data_uri": photo_data_uri,
    }

    png = render_context(template, context)

    metadata = {
        "template_id": template.template_id,
        "theme": birth.theme,
        "selected_media_id": str(photo.id) if photo else None,
        "stats": stats.as_metadata(),
        "child": {
            "name": birth.child_name,
            "when": when.isoformat() if when else None,
        },
        "dimensions": {"w": template.width, "h": template.height, "dpi": template.dpi},
    }
    return png, metadata


def render_context(template: GiftTemplate, context: dict) -> bytes:
    """Render a template's SVG with `context` and rasterize to PNG at the
    template's exact pixels. Split out from `render` so the template +
    rasterization path is testable without a DB or S3."""
    svg = _env.get_template(template.svg).render(**context)
    try:
        return cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            output_width=template.width,
            output_height=template.height,
        )
    except Exception as exc:  # cairosvg raises a grab-bag of errors
        raise ArtworkError(f"rasterize: {exc}") from exc


# ── photo selection ──────────────────────────────────────────────────────


def _select_hero_photo(db: Session, birth: Birth) -> MediaAsset | None:
    """First viewer-visible photo at/after the birth moment; else the first
    visible photo overall."""
    rows = list(
        db.scalars(
            select(MediaAsset)
            .where(
                MediaAsset.birth_id == birth.id,
                MediaAsset.kind == MediaKind.photo,
                MediaAsset.is_visible_to_viewers.is_(True),
                MediaAsset.archived_at.is_(None),
            )
            .order_by(MediaAsset.created_at.asc())
        ).all()
    )
    if not rows:
        return None
    if birth.birth_completed_at is not None:
        for asset in rows:
            if asset.created_at >= birth.birth_completed_at:
                return asset
    return rows[0]


def _photo_data_uri(asset: MediaAsset) -> str | None:
    try:
        raw = get_object_bytes(asset.original_s3_key)
    except Exception:
        return None
    mime = asset.mime_type or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


# ── sparkline geometry ───────────────────────────────────────────────────


def _spark_xy(durations: list[int]) -> list[tuple[float, float]]:
    if len(durations) < 2:
        return []
    hi = max(durations)
    lo = min(durations)
    span = (hi - lo) or 1
    pad = 16  # keep the line off the top/bottom edges
    points = []
    n = len(durations)
    for i, d in enumerate(durations):
        x = (i / (n - 1)) * _SPARK_W
        # taller = longer contraction; invert because SVG y grows downward
        norm = (d - lo) / span
        y = _SPARK_H - pad - norm * (_SPARK_H - 2 * pad)
        points.append((round(x, 1), round(y, 1)))
    return points


def _sparkline_polyline(durations: list[int]) -> str:
    return " ".join(f"{x},{y}" for x, y in _spark_xy(durations))


def _sparkline_area(durations: list[int]) -> str:
    pts = _spark_xy(durations)
    if not pts:
        return ""
    body = " ".join(f"{x},{y}" for x, y in pts)
    return f"{pts[0][0]},{_SPARK_H} {body} {pts[-1][0]},{_SPARK_H}"


# ── formatting ───────────────────────────────────────────────────────────


def _fmt_date(dt: datetime | None) -> str:
    if dt is None:
        return ""
    # cross-platform: avoid %-d / %-I (not on all libc)
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def _fmt_time(dt: datetime | None) -> str:
    if dt is None:
        return ""
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.minute:02d} {ampm}"


def _fmt_hms(seconds: int | None) -> str:
    if not seconds:
        return "—"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _fmt_ms(seconds: float | None) -> str:
    if not seconds:
        return "—"
    total = round(seconds)
    minutes, secs = divmod(total, 60)
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _fmt_interval(seconds: float | None) -> str:
    if not seconds:
        return "—"
    return f"{seconds / 60:.1f} min"
