"""Generate gift artwork (the design that goes ON a product) as SVG → PNG.

Pure Python, no browser: compute the birth's stats, pick a theme palette,
auto-select a hero photo, fill a Jinja2 SVG template, and rasterize with
cairosvg at the template's exact print pixels.
"""
from __future__ import annotations

import base64
import io
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import cairosvg
from PIL import Image
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import gift_stats
import gift_themes
from gift_templates import GiftTemplate
from models import (
    AudienceScope,
    Birth,
    MediaAsset,
    MediaKind,
    ReactionKind,
    TimelineEvent,
    TimelineEventComment,
    TimelineEventReaction,
    TimelineEventType,
    User,
)
from storage import get_object_bytes

_TEMPLATE_DIR = "templates/gifts"

# Sparkline is drawn in this normalized coordinate space; templates place it
# with a nested <svg viewBox="0 0 1000 240" preserveAspectRatio="none">.
_SPARK_W = 1000
_SPARK_H = 240


class ArtworkError(Exception):
    """Rendering failed for a reason worth recording on the rendering row."""


# Timestamps are stored UTC; keepsakes must show the family's wall-clock time
# ("born at 10:54 am", the clock angles, photo stamps). Until births carry
# their own timezone, render in a configurable one.
_RENDER_TZ = ZoneInfo(os.getenv("GIFT_RENDER_TZ", "America/New_York"))


def _localize(dt: datetime | None) -> datetime | None:
    """UTC (or any aware) datetime → the render timezone; naive passes
    through untouched (tests, fixtures)."""
    if dt is None or dt.tzinfo is None:
        return dt
    return dt.astimezone(_RENDER_TZ)


_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["svg", "j2", "xml"], default=True),
)
# `sparkle(cx, cy, r)` is available in templates — the four-point star that
# marks the moment of arrival across the collection.
_env.globals["sparkle"] = lambda cx, cy, r: _sparkle_path(cx, cy, r)


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

    when = _localize(birth.child_dob or birth.birth_completed_at)
    first_at_local = _localize(stats.first_contraction_at)
    spark_last = _spark_last(stats.durations)
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
        "spark_path": _spark_path(stats.durations),
        "spark_area_path": _spark_area_path(stats.durations),
        "spark_last_x": spark_last[0] if spark_last else 0,
        "spark_last_y": spark_last[1] if spark_last else 0,
        "spark_callouts": _spark_callouts(stats.durations),
        "labor_start_time": _fmt_time(first_at_local),
        "photo_data_uri": photo_data_uri,
    }

    if template.scene in ("hours", "hours_photo", "orbit"):
        context["clock_cx"] = template.clock_cx or template.width / 2
        context["clock_cy"] = template.clock_cy or template.height / 2
    if template.scene in ("hours", "hours_photo"):
        context.update(
            build_hours_clock(
                durations=stats.durations,
                offsets_seconds=stats.offsets_seconds,
                # local wall-clock time — the clock angles are literal
                first_contraction_at=first_at_local,
                born_at=when,
                cx=context["clock_cx"],
                cy=context["clock_cy"],
                milestones=_gather_milestones(db, birth, stats),
                canvas_w=template.width,
                **CLOCK_PRESETS[template.scene],
            )
        )
        context["clock_photo_r"] = CLOCK_PHOTO_R
    elif template.scene == "orbit":
        context.update(_build_orbit_scene(db, birth, template, stats))
    elif template.scene == "story":
        context.update(_build_story_scene(db, birth, template))
    elif template.scene == "words":
        context.update(_build_words_scene(db, birth, template))
    elif template.scene == "reel":
        context.update(_build_reel_scene(db, birth, template))
    elif template.scene == "pool":
        context.update(_build_pool_scene(db, birth, template))

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


def _photo_data_uri(asset: MediaAsset, *, max_px: int | None = None) -> str | None:
    try:
        raw = get_object_bytes(asset.original_s3_key)
    except Exception:
        return None
    mime = asset.mime_type or "image/jpeg"
    # Re-encode every photo: apply the EXIF orientation (phone photos are
    # usually stored rotated + a tag, and cairosvg ignores the tag — without
    # this, portraits render sideways) and downscale so the SVG stays light.
    # Hero photos keep enough pixels for full-bleed print panels.
    try:
        from PIL import ImageOps

        im = Image.open(io.BytesIO(raw))
        im = ImageOps.exif_transpose(im)
        im.thumbnail((max_px or 1600, max_px or 1600))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=88)
        raw = buf.getvalue()
        mime = "image/jpeg"
    except Exception:
        pass  # fall back to the original bytes
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


# ── timeline "moments" for the rising template ────────────────────────────


# Punctuation beyond Latin we still want to keep (curly quotes, dashes, …, ·).
_ALLOWED_EXTRA = set("’‘“”…–—·•")


def _clean_text(s: str | None) -> str:
    """Drop characters the bundled fonts can't render (emoji, CJK, symbols)
    so they don't show up as tofu boxes. Keeps Latin + common punctuation."""
    if not s:
        return ""
    return "".join(
        c for c in s if ord(c) < 0x0250 or c in _ALLOWED_EXTRA
    ).strip()


def _truncate(s: str, max_len: int) -> str:
    s = s.strip()
    return s if len(s) <= max_len else s[: max_len - 1].rstrip() + "…"


def _sample_spaced(items: list, n: int) -> list:
    """Evenly sample up to n items across the list (keeps order)."""
    if n <= 0 or not items:
        return []
    if len(items) <= n:
        return items
    if n == 1:
        return [items[len(items) // 2]]
    return [items[round(i * (len(items) - 1) / (n - 1))] for i in range(n)]


def _gather_photos(db: Session, birth: Birth, *, limit: int) -> list[dict]:
    """Up to `limit` viewer-visible photos spaced across the timeline, each
    with a data URI and caption, in chronological order."""
    events = list(
        db.scalars(
            select(TimelineEvent)
            .where(
                TimelineEvent.birth_id == birth.id,
                TimelineEvent.event_type == TimelineEventType.photo,
                TimelineEvent.deleted_at.is_(None),
            )
            .order_by(TimelineEvent.occurred_at.asc())
        ).all()
    )
    out: list[dict] = []
    for e in events:
        media_id = (e.payload or {}).get("media_id")
        if not media_id:
            continue
        asset = db.get(MediaAsset, media_id)
        if (
            asset is None
            or asset.kind != MediaKind.photo
            or not asset.is_visible_to_viewers
            or asset.archived_at is not None
        ):
            continue
        uri = _photo_data_uri(asset, max_px=900)
        if uri is None:
            continue
        caption = _truncate(_clean_text((e.payload or {}).get("caption")), 18)
        out.append(
            {"uri": uri, "caption": caption, "occurred_at": _localize(e.occurred_at)}
        )
    return _sample_spaced(out, limit)


def _humanize_kind(kind: str | None) -> str:
    return (kind or "milestone").replace("_", " ")


def _gather_milestones(db: Session, birth: Birth, stats) -> list[dict]:
    """Public milestones that happened during labor (first contraction →
    birth), as {kind, label, offset_seconds} for the clock. 'born' is
    excluded — the star already marks it. Capped and evenly sampled so a
    heavily-annotated labor doesn't crowd the ring."""
    if stats.first_contraction_at is None:
        return []
    born = birth.child_dob or birth.birth_completed_at
    events = list(
        db.scalars(
            select(TimelineEvent)
            .where(
                TimelineEvent.birth_id == birth.id,
                TimelineEvent.event_type == TimelineEventType.milestone,
                # Anything the parents kept to themselves stays off a product
                # a relative will hold. Written as "not parents_only" rather
                # than "== public" because `public` is retired: matching on it
                # would quietly empty the ring of every new milestone.
                TimelineEvent.audience_scope != AudienceScope.parents_only,
                TimelineEvent.deleted_at.is_(None),
            )
            .order_by(TimelineEvent.occurred_at.asc())
        ).all()
    )
    out = []
    for e in events:
        payload = e.payload or {}
        kind = payload.get("kind")
        if kind == "born":
            continue
        if e.occurred_at < stats.first_contraction_at:
            continue
        if born is not None and e.occurred_at > born:
            continue
        label = _truncate(
            _clean_text(payload.get("title")) or _humanize_kind(kind), 22
        )
        offset = (e.occurred_at - stats.first_contraction_at).total_seconds()
        out.append({"kind": kind, "label": label, "offset_seconds": int(offset)})
    return _sample_spaced(out, 4)


def _reaction_counts(db: Session, birth: Birth) -> dict:
    rows = db.execute(
        select(TimelineEventReaction.kind, func.count())
        .join(TimelineEvent, TimelineEvent.id == TimelineEventReaction.event_id)
        .where(TimelineEvent.birth_id == birth.id)
        .group_by(TimelineEventReaction.kind)
    ).all()
    counts = {k: 0 for k in ReactionKind}
    for kind, n in rows:
        counts[kind] = n
    return counts


def _short_comments(db: Session, birth: Birth, *, limit: int, max_len: int) -> list[str]:
    rows = list(
        db.scalars(
            select(TimelineEventComment.body)
            .join(TimelineEvent, TimelineEvent.id == TimelineEventComment.event_id)
            .where(
                TimelineEvent.birth_id == birth.id,
                TimelineEventComment.deleted_at.is_(None),
            )
            .order_by(TimelineEventComment.created_at.asc())
        ).all()
    )
    cleaned = [_clean_text(b) for b in rows]
    cleaned = [b for b in cleaned if b]
    short = [b for b in cleaned if len(b) <= max_len]
    pool = short or [_truncate(b, max_len) for b in cleaned]
    return _sample_spaced(pool, limit)


def _reaction_summary(counts: dict, comment_total: int) -> str:
    """Single separator-joined line. SVG collapses whitespace runs, so
    separators must be real characters — and words, not symbols: the bundled
    fonts have no ♥, and cairosvg won't fall back per-glyph (it renders
    tofu)."""
    total = sum(counts.values())
    parts = []
    if total:
        parts.append(f"{total} reaction{'s' if total != 1 else ''}")
    if comment_total:
        parts.append(f"{comment_total} note{'s' if comment_total != 1 else ''}")
    return " · ".join(parts)


def _polaroid_rotations(n: int) -> list[int]:
    base = [-7, 6, -4, 8, -6, 5, -8]
    return [base[i % len(base)] for i in range(n)]


def build_story_scene(
    photos: list[dict], *, width: float, height: float
) -> dict:
    """Geometry for the story card: a path rising from "where it began" at
    the bottom to a sparkle star at the top, with Polaroids hanging off it.
    Each photo's moment is a dot ON the path with a short connector to the
    Polaroid, so the thread and the photos read as one object. Pure geometry
    — the DB wrapper below gathers the content."""
    cx = width / 2
    amp = 190.0
    y_bottom = height - 420
    y_top = 660
    waves = 1.6

    def path_x(t: float) -> float:
        return cx + amp * math.sin(t * waves * 2 * math.pi)

    steps = 200
    pts = []
    for i in range(steps + 1):
        t = i / steps
        y = y_bottom - t * (y_bottom - y_top)
        pts.append((path_x(t), y))
    path_d = _smooth_path(pts)

    rotations = _polaroid_rotations(len(photos))
    polaroids = []
    moments = []
    n = len(photos)
    for i, ph in enumerate(photos):
        t = (i + 0.5) / n if n else 0
        y = y_bottom - t * (y_bottom - y_top)
        px = path_x(t)
        side = -1 if i % 2 == 0 else 1
        x = cx + side * 355
        moments.append(
            {
                "x": round(px, 1),
                "y": round(y, 1),
                # connector from the dot toward the polaroid's near edge
                "x2": round(x - side * 175, 1),
            }
        )
        polaroids.append(
            {
                "x": round(x, 1),
                "y": round(y, 1),
                "rot": rotations[i],
                "href": ph["uri"],
                "caption": ph["caption"],
            }
        )

    return {
        "path_d": path_d,
        "polaroids": polaroids,
        "moments": moments,
        "y_start": y_bottom,
        "star": _sparkle_path(path_x(1.0), y_top - 60, 44),
    }


def _build_story_scene(db: Session, birth: Birth, template: GiftTemplate) -> dict:
    photos = _gather_photos(db, birth, limit=5)
    counts = _reaction_counts(db, birth)
    comments = _short_comments(db, birth, limit=2, max_len=60)
    scene = build_story_scene(
        photos, width=template.width, height=template.height
    )
    scene["reaction_summary"] = _reaction_summary(counts, len(comments))
    scene["notes"] = comments
    return scene


# ── the horizon: labor as a smooth line ──────────────────────────────────
# Drawn in a normalized 1000×240 space; templates place it with a nested
# <svg viewBox="0 0 1000 240" preserveAspectRatio="none">. Cubic béziers
# stay smooth under the non-uniform stretch, and vector-effect:
# non-scaling-stroke keeps the line weight even.


_SPARK_MAX_POINTS = 40


def _resample(durations: list[int], n: int) -> list[int]:
    """Bucket-average down to at most n points, so a long labor draws a calm
    horizon instead of a nervous scribble. The labor clock is the
    every-contraction-truthful piece; the horizon is the rhythm."""
    if len(durations) <= n:
        return durations
    out = []
    for b in range(n):
        lo = round(b * len(durations) / n)
        hi = round((b + 1) * len(durations) / n) or 1
        bucket = durations[lo:hi] or durations[lo : lo + 1]
        out.append(round(sum(bucket) / len(bucket)))
    return out


def _spark_xy(durations: list[int]) -> list[tuple[float, float]]:
    if len(durations) < 2:
        return []
    durations = _resample(durations, _SPARK_MAX_POINTS)
    hi = max(durations)
    lo = min(durations)
    span = (hi - lo) or 1
    top_pad = 20
    points = []
    n = len(durations)
    for i, d in enumerate(durations):
        x = (i / (n - 1)) * _SPARK_W
        # taller = longer contraction; invert because SVG y grows downward.
        # The quietest moment sits on the baseline so the area fill hugs the
        # line instead of leaving a solid band beneath it.
        norm = (d - lo) / span
        y = _SPARK_H - norm * (_SPARK_H - top_pad)
        points.append((round(x, 1), round(y, 1)))
    return points


def _smooth_path(pts: list[tuple[float, float]]) -> str:
    """Catmull-Rom through the points, emitted as cubic béziers — the organic
    line a hand would draw, instead of a jagged polyline."""
    if len(pts) < 2:
        return ""
    d = [f"M {pts[0][0]},{pts[0][1]}"]
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(
            f"C {c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} "
            f"{p2[0]:.1f},{p2[1]:.1f}"
        )
    return " ".join(d)


def _spark_path(durations: list[int]) -> str:
    return _smooth_path(_spark_xy(durations))


def _spark_area_path(durations: list[int]) -> str:
    pts = _spark_xy(durations)
    if not pts:
        return ""
    line = _smooth_path(pts)
    return f"{line} L {pts[-1][0]},{_SPARK_H} L {pts[0][0]},{_SPARK_H} Z"


def _spark_last(durations: list[int]) -> tuple[float, float] | None:
    pts = _spark_xy(durations)
    return pts[-1] if pts else None


def _spark_callouts(durations: list[int]) -> list[dict]:
    """Points along the horizon worth naming: the tallest peak and the
    deepest valley in the line's middle stretch, each with a dot, a hairline
    connector, and the true duration of a wave in that bucket. The ends are
    excluded on purpose — the start label and the arrival star own them, and
    in a ramping labor the global max is usually the final wave anyway.
    Peak labels drop below the point, valley labels rise above it — that's
    where the empty space is."""
    pts = _spark_xy(durations)
    if len(pts) < 3 or not durations:
        return []
    resampled = _resample(durations, _SPARK_MAX_POINTS)
    n = len(resampled)

    def bucket_extreme(i: int, fn) -> int:
        lo = round(i * len(durations) / n)
        hi = round((i + 1) * len(durations) / n) or 1
        return fn(durations[lo:hi] or durations[lo : lo + 1])

    def anchor(x: float) -> str:
        if x > 820:
            return "end"
        if x < 180:
            return "start"
        return "middle"

    mid = [
        (i, p) for i, p in enumerate(pts) if 110 <= p[0] <= 880
    ]
    if not mid:
        return []

    peak_i, peak = min(mid, key=lambda ip: ip[1][1])
    callouts = [
        {
            "x": peak[0],
            "y": peak[1],
            "dir": "down",
            "anchor": anchor(peak[0]),
            "label": f"longest wave · {_fmt_ms(bucket_extreme(peak_i, max))}",
        }
    ]
    valley_i, valley = max(mid, key=lambda ip: ip[1][1])
    if abs(valley[0] - peak[0]) > 140:
        callouts.append(
            {
                "x": valley[0],
                "y": valley[1],
                "dir": "up",
                "anchor": anchor(valley[0]),
                "label": f"shortest wave · {_fmt_ms(bucket_extreme(valley_i, min))}",
            }
        )
    return callouts


# ── the labor clock: contractions around a clock face ────────────────────


def _sparkle_path(cx: float, cy: float, r: float) -> str:
    """A four-point sparkle star (the arrival mark)."""
    w = r * 0.22  # waist — how pinched the points are
    return (
        f"M {cx:.1f},{cy - r:.1f} "
        f"Q {cx + w:.1f},{cy - w:.1f} {cx + r:.1f},{cy:.1f} "
        f"Q {cx + w:.1f},{cy + w:.1f} {cx:.1f},{cy + r:.1f} "
        f"Q {cx - w:.1f},{cy + w:.1f} {cx - r:.1f},{cy:.1f} "
        f"Q {cx - w:.1f},{cy - w:.1f} {cx:.1f},{cy - r:.1f} Z"
    )


def _droplet_path(cx: float, cy: float, r: float) -> str:
    """A teardrop (water broke)."""
    return (
        f"M {cx:.1f},{cy - r:.1f} "
        f"C {cx + r * 0.55:.1f},{cy - r * 0.25:.1f} {cx + r * 0.78:.1f},{cy + r * 0.05:.1f} "
        f"{cx + r * 0.78:.1f},{cy + r * 0.3:.1f} "
        f"A {r * 0.78:.1f},{r * 0.78:.1f} 0 1 1 {cx - r * 0.78:.1f},{cy + r * 0.3:.1f} "
        f"C {cx - r * 0.78:.1f},{cy + r * 0.05:.1f} {cx - r * 0.55:.1f},{cy - r * 0.25:.1f} "
        f"{cx:.1f},{cy - r:.1f} Z"
    )


def _heart_path(cx: float, cy: float, r: float) -> str:
    """A small heart (first hold / first feed)."""
    return (
        f"M {cx:.1f},{cy + r * 0.65:.1f} "
        f"C {cx - r * 1.15:.1f},{cy - r * 0.15:.1f} {cx - r * 0.6:.1f},{cy - r * 0.95:.1f} "
        f"{cx:.1f},{cy - r * 0.35:.1f} "
        f"C {cx + r * 0.6:.1f},{cy - r * 0.95:.1f} {cx + r * 1.15:.1f},{cy - r * 0.15:.1f} "
        f"{cx:.1f},{cy + r * 0.65:.1f} Z"
    )


def _house_path(cx: float, cy: float, r: float) -> str:
    """A tiny house silhouette (arrived / going home)."""
    return (
        f"M {cx - r * 0.8:.1f},{cy + r * 0.8:.1f} L {cx - r * 0.8:.1f},{cy - r * 0.1:.1f} "
        f"L {cx:.1f},{cy - r * 0.9:.1f} L {cx + r * 0.8:.1f},{cy - r * 0.1:.1f} "
        f"L {cx + r * 0.8:.1f},{cy + r * 0.8:.1f} Z"
    )


def _diamond_path(cx: float, cy: float, r: float) -> str:
    """A small diamond (any other milestone)."""
    return (
        f"M {cx:.1f},{cy - r:.1f} L {cx + r * 0.7:.1f},{cy:.1f} "
        f"L {cx:.1f},{cy + r:.1f} L {cx - r * 0.7:.1f},{cy:.1f} Z"
    )


# milestone kind → icon path builder (mirrors the app's MILESTONES registry;
# 'born' is never drawn here — the sparkle star already marks it)
_MILESTONE_ICONS = {
    "water_broke": _droplet_path,
    "arrived": _house_path,
    "going_home": _house_path,
    "first_hold": _heart_path,
    "first_feed": _heart_path,
}


_TWELVE_HOURS = 12 * 3600


def _clock_angle(dt: datetime) -> float:
    """Angle (radians) of a moment on a 12-hour clock face, 12 at the top."""
    seconds = (dt.hour % 12) * 3600 + dt.minute * 60 + dt.second
    return (seconds / _TWELVE_HOURS) * 2 * math.pi - math.pi / 2


def _angle_mapper(offsets_seconds: list[int], first_contraction_at: datetime | None):
    """offset-seconds → clock-face angle (radians). Real clock time when the
    labor fits one lap of the face; otherwise a linear sweep (overlapping
    strokes would lie about the shape). Shared by every clock-family scene so
    strokes, the star, and orbiting photos all agree on where a moment sits."""
    total = offsets_seconds[-1] if offsets_seconds else 0
    clock_true = first_contraction_at is not None and total <= _TWELVE_HOURS * 0.96

    def angle_at(offset: int) -> float:
        if clock_true:
            base = _clock_angle(first_contraction_at)
            return base + (offset / _TWELVE_HOURS) * 2 * math.pi
        sweep = 2 * math.pi * 0.93
        return -math.pi / 2 + (offset / (total or 1)) * sweep

    return angle_at, clock_true, total


# Clock face sizes per scene. `hours_photo` pulls the strokes outward to make
# room for the hero photo in the center; `orbit` shrinks the whole face so the
# photo thumbnails orbiting outside still clear the card edges.
CLOCK_PRESETS: dict[str, dict] = {
    "hours": {"r_ring": 460.0, "r_in": 205.0, "len_lo": 80.0, "len_hi": 225.0},
    "hours_photo": {"r_ring": 470.0, "r_in": 245.0, "len_lo": 70.0, "len_hi": 200.0},
    "orbit": {"r_ring": 420.0, "r_in": 190.0, "len_lo": 70.0, "len_hi": 190.0},
}
# Hero-photo radius inside the hours_photo face (hairline ring sits just out).
CLOCK_PHOTO_R = 195.0


def build_hours_clock(
    *,
    durations: list[int],
    offsets_seconds: list[int],
    first_contraction_at: datetime | None,
    born_at: datetime | None,
    cx: float,
    cy: float,
    r_ring: float = 460.0,
    r_in: float = 205.0,
    len_lo: float = 80.0,
    len_hi: float = 225.0,
    milestones: list[dict] | None = None,
    canvas_w: float | None = None,
) -> dict:
    """Geometry for the radial labor clock: every contraction is a fine
    stroke radiating at the clock angle of the moment it happened, its length
    the contraction's duration. A sparkle star sits on the ring at the minute
    of birth. Pure function of the data — no DB — so previews and tests can
    drive it directly.

    Labors longer than a lap of the clock fall back to a linear sweep (the
    strokes would otherwise overlap themselves); the ring loses its clock
    semantics but the shape stays honest.
    """
    angle_at, _clock_true, total = _angle_mapper(
        offsets_seconds, first_contraction_at
    )
    clock_true = _clock_true

    lo = min(durations) if durations else 0
    hi = max(durations) if durations else 1
    span = (hi - lo) or 1

    strokes = []
    for offset, duration in zip(offsets_seconds, durations):
        a = angle_at(offset)
        length = len_lo + ((duration - lo) / span) * (len_hi - len_lo)
        progress = offset / (total or 1)
        strokes.append(
            {
                "x1": round(cx + r_in * math.cos(a), 1),
                "y1": round(cy + r_in * math.sin(a), 1),
                "x2": round(cx + (r_in + length) * math.cos(a), 1),
                "y2": round(cy + (r_in + length) * math.sin(a), 1),
                # the burst deepens as labor builds toward the star — capped
                # well under 1.0 so overlapping strokes in a dense cluster
                # stay soft instead of fusing into a solid saturated mass
                "o": round(0.28 + 0.38 * progress, 2),
            }
        )

    # The birth minute on the ring — where the star sits. The tick ring
    # leaves a gap around it so the star reads as part of the clock.
    star_angle = None
    if born_at is not None:
        if clock_true:
            star_angle = _clock_angle(born_at)
        elif offsets_seconds:
            star_angle = angle_at(offsets_seconds[-1])

    ticks = []
    for i in range(60):
        a = (i / 60) * 2 * math.pi - math.pi / 2
        if star_angle is not None:
            gap = abs((a - star_angle + math.pi) % (2 * math.pi) - math.pi)
            if gap < 0.10:  # leave room for the star
                continue
        is_hour = i % 5 == 0
        r0 = r_ring - (22 if is_hour else 10)
        ticks.append(
            {
                "x1": round(cx + r0 * math.cos(a), 1),
                "y1": round(cy + r0 * math.sin(a), 1),
                "x2": round(cx + r_ring * math.cos(a), 1),
                "y2": round(cy + r_ring * math.sin(a), 1),
                "hour": is_hour,
            }
        )

    star = None
    star_label = None
    if star_angle is not None:
        sx = cx + (r_ring - 6) * math.cos(star_angle)
        sy = cy + (r_ring - 6) * math.sin(star_angle)
        star = _sparkle_path(sx, sy, 40)
        lx = cx + (r_ring + 78) * math.cos(star_angle)
        ly = cy + (r_ring + 78) * math.sin(star_angle)
        star_label = {"x": round(lx, 1), "y": round(ly + 10, 1)}

    start_dot = None
    start_label = None
    if offsets_seconds:
        a0 = angle_at(offsets_seconds[0])
        start_dot = {
            "x": round(cx + (r_ring - 6) * math.cos(a0), 1),
            "y": round(cy + (r_ring - 6) * math.sin(a0), 1),
        }
        # closer in than the star's label — the dot is a small mark
        lx = cx + (r_ring + 52) * math.cos(a0)
        ly = cy + (r_ring + 52) * math.sin(a0)
        start_label = {"x": round(lx, 1), "y": round(ly + 10, 1)}

    # the milestones of the birth, anchored at their true clock angles —
    # each an icon just outside the ring with a quiet label beyond it
    clock_milestones = []
    placed_angles: list[float] = []

    def _gap(a: float, b: float) -> float:
        return abs((a - b + math.pi) % (2 * math.pi) - math.pi)

    for m in milestones or []:
        a = angle_at(int(m["offset_seconds"]))
        if star_angle is not None and _gap(a, star_angle) < 0.18:
            continue  # the star owns the birth minute
        # milestones minutes apart share an angle; their labels would garble
        # each other, so the first one placed wins the spot
        if any(_gap(a, b) < 0.35 for b in placed_angles):
            continue
        placed_angles.append(a)
        icon = _MILESTONE_ICONS.get(m.get("kind"), _diamond_path)
        ix = cx + (r_ring + 42) * math.cos(a)
        iy = cy + (r_ring + 42) * math.sin(a)
        # labels grow away from the face so they never run back over their
        # icon: outward horizontally on the sides, stacked above/below at
        # the top and bottom — and clamped to the canvas so a side label
        # near an edge stacks instead of clipping (the mug's clock sits far
        # off-center, so both edges are real)
        cos_a, sin_a = math.cos(a), math.sin(a)
        w = canvas_w if canvas_w is not None else cx * 2
        est = len(m["label"]) * 17  # generous per-glyph advance at label size
        anchor = None
        if cos_a > 0.35 and ix + 36 + est <= w - 24:
            anchor, lx, ly = "start", ix + 36, iy + 9
        elif cos_a < -0.35 and ix - 36 - est >= 24:
            anchor, lx, ly = "end", ix - 36, iy + 9
        if anchor is None:
            anchor = "middle"
            lx = min(max(ix, est / 2 + 24), w - est / 2 - 24)
            ly = iy - 40 if sin_a < 0 else iy + 58
        clock_milestones.append(
            {
                "d": icon(ix, iy, 17),
                "lx": round(lx, 1),
                "ly": round(ly, 1),
                "anchor": anchor,
                "label": m["label"],
            }
        )

    return {
        "clock_strokes": strokes,
        "clock_ticks": ticks,
        "clock_star": star,
        "clock_star_label": star_label,
        "clock_start_dot": start_dot,
        "clock_start_label": start_label,
        "clock_milestones": clock_milestones,
    }


# ── moments in orbit: photos around the clock at the time they happened ──

_ORBIT_R = 545.0
_ORBIT_THUMB_R = 95.0


def build_orbit_scene(
    photos: list[dict],
    *,
    durations: list[int],
    offsets_seconds: list[int],
    first_contraction_at: datetime | None,
    born_at: datetime | None,
    cx: float,
    cy: float,
) -> dict:
    """The labor clock with the timeline's photos as small circles orbiting
    outside the tick ring, each at the clock angle of the moment it was
    taken — placed by the data, not arranged in a grid. Each photo gets a dot
    on the ring and a hairline connector. `photos` need an `occurred_at`;
    ones without are spread evenly (previews, degraded data)."""
    preset = CLOCK_PRESETS["orbit"]
    scene = build_hours_clock(
        durations=durations,
        offsets_seconds=offsets_seconds,
        first_contraction_at=first_contraction_at,
        born_at=born_at,
        cx=cx,
        cy=cy,
        **preset,
    )
    angle_at, _, total = _angle_mapper(offsets_seconds, first_contraction_at)

    angles = []
    for i, ph in enumerate(photos):
        when = ph.get("occurred_at")
        if when is not None and first_contraction_at is not None:
            offset = (when - first_contraction_at).total_seconds()
            angles.append(angle_at(int(max(0, min(offset, total)))))
        else:
            angles.append(angle_at(int(total * (i + 0.5) / max(len(photos), 1))))

    # keep thumbnails from overlapping: enforce a minimum angular gap,
    # nudging later moments forward (order stays chronological)
    min_gap = 2 * math.asin((_ORBIT_THUMB_R + 10) / _ORBIT_R)
    order = sorted(range(len(angles)), key=lambda i: angles[i])
    for prev, curr in zip(order, order[1:]):
        if angles[curr] < angles[prev] + min_gap:
            angles[curr] = angles[prev] + min_gap

    r_ring = preset["r_ring"]
    thumbs = []
    for ph, a in zip(photos, angles):
        tx = cx + _ORBIT_R * math.cos(a)
        ty = cy + _ORBIT_R * math.sin(a)
        thumbs.append(
            {
                "cx": round(tx, 1),
                "cy": round(ty, 1),
                "r": _ORBIT_THUMB_R,
                "href": ph["uri"],
                "dot_x": round(cx + r_ring * math.cos(a), 1),
                "dot_y": round(cy + r_ring * math.sin(a), 1),
                "lx": round(cx + (_ORBIT_R - _ORBIT_THUMB_R) * math.cos(a), 1),
                "ly": round(cy + (_ORBIT_R - _ORBIT_THUMB_R) * math.sin(a), 1),
            }
        )
    scene["orbit_thumbs"] = thumbs
    return scene


def _build_orbit_scene(
    db: Session, birth: Birth, template: GiftTemplate, stats
) -> dict:
    photos = _gather_photos(db, birth, limit=5)
    return build_orbit_scene(
        photos,
        durations=stats.durations,
        offsets_seconds=stats.offsets_seconds,
        first_contraction_at=_localize(stats.first_contraction_at),
        born_at=_localize(birth.child_dob or birth.birth_completed_at),
        cx=template.clock_cx or template.width / 2,
        cy=template.clock_cy or template.height / 2,
    )


# ── the reel: the day as a filmstrip of photos ────────────────────────────
# Photo-first: full-bleed chronological panels (rotating the mug plays the
# day; the card reads downward), each stamped with its time and caption on a
# scrim. The data stays delicate — one continuous labor thread in a quiet
# band beneath the strip, ending in the star at the minute of birth.

_REEL_GUTTER = 8
_REEL_BAND_H = 185
_REEL_TITLE_W = 540  # mug title panel (the "opening card")
_REEL_HEADER_H = 430  # card title block


def build_reel_scene(photos: list[dict], *, width: float, height: float, layout: str) -> dict:
    """Panel geometry for the filmstrip. `layout` is "mug" (title panel +
    horizontal strip) or "card" (title block + stacked rows). Assumes at
    least one photo — the DB wrapper raises before calling otherwise."""
    band_y = height - _REEL_BAND_H
    panels = []
    if layout == "mug":
        photos = _sample_spaced(photos, 4)
        n = len(photos)
        region_w = width - _REEL_TITLE_W
        panel_w = (region_w - _REEL_GUTTER * (n - 1)) / n
        for i, ph in enumerate(photos):
            panels.append(
                {
                    "x": round(_REEL_TITLE_W + i * (panel_w + _REEL_GUTTER), 1),
                    "y": 0,
                    "w": round(panel_w, 1),
                    "h": round(band_y - _REEL_GUTTER, 1),
                    "href": ph["uri"],
                    "caption": ph.get("caption") or "",
                    "time": _fmt_time(ph.get("occurred_at")),
                }
            )
    else:
        photos = _sample_spaced(photos, 3)
        n = len(photos)
        region_h = band_y - _REEL_GUTTER - _REEL_HEADER_H
        row_h = (region_h - _REEL_GUTTER * (n - 1)) / n
        for i, ph in enumerate(photos):
            panels.append(
                {
                    "x": 0,
                    "y": round(_REEL_HEADER_H + i * (row_h + _REEL_GUTTER), 1),
                    "w": width,
                    "h": round(row_h, 1),
                    "href": ph["uri"],
                    "caption": ph.get("caption") or "",
                    "time": _fmt_time(ph.get("occurred_at")),
                }
            )
    return {
        "reel_panels": panels,
        "reel_band_y": round(band_y, 1),
        "reel_title_w": _REEL_TITLE_W,
        "reel_header_h": _REEL_HEADER_H,
    }


def _build_reel_scene(db: Session, birth: Birth, template: GiftTemplate) -> dict:
    layout = "mug" if template.product_kind == "mug" else "card"
    photos = _gather_photos(db, birth, limit=4 if layout == "mug" else 3)
    if not photos:
        raise ArtworkError("missing-photo")
    return build_reel_scene(
        photos, width=template.width, height=template.height, layout=layout
    )


# ── the pool: the family's predictions vs. the actuals ───────────────────
# The leaderboard as a keepsake: everyone guessed before they met her; the
# card settles it. Scoring mirrors frontend/src/components/Predictions.jsx —
# |weight diff in lbs| + 0.5 × |length diff in inches|, closest wins.

_POOL_LAYOUTS = {
    "card": {
        "rank_x": 205, "name_x": 250, "guess_x": 1295,
        "y0": 660, "step": 76, "max_rows": 11,
        "ruler_x1": 250, "ruler_x2": 1250, "ruler_y": 1790,
    },
    "mug": {
        "rank_x": 1300, "name_x": 1340, "guess_x": 2380,
        "y0": 190, "step": 58, "max_rows": 11,
        "ruler_x1": 1340, "ruler_x2": 2380, "ruler_y": 1035,
    },
}
# rough per-glyph advances for the leader-dot gaps (generous on purpose —
# a leader that stops early is fine, one that runs into text is not)
_POOL_NAME_ADV = 0.74
_POOL_GUESS_ADV = 0.68
_POOL_ROW_FONT = 36


def _fmt_lbs_oz(lbs: float | None) -> str:
    if not lbs:
        return ""
    pounds = int(lbs)
    oz = round((lbs - pounds) * 16)
    if oz == 16:
        pounds, oz = pounds + 1, 0
    return f"{pounds} lbs {oz} oz" if oz else f"{pounds} lbs"


def _fmt_guess(weight_lbs: float | None, length_in: float | None) -> str:
    parts = []
    if weight_lbs:
        parts.append(_fmt_lbs_oz(weight_lbs))
    if length_in:
        parts.append(f"{length_in:g} in")
    return " · ".join(parts) or "—"


def _pool_score(prediction: dict, actual_weight: float) -> float | None:
    """Thin wrapper over the one true ranking fn (repositories/guesses.py) so
    the pool card and the leaderboard can't drift apart. Weight only: it's the
    gold medal and the board's ordering, and the card has no room to explain a
    combined score anyway."""
    from repositories import guesses as guesses_repo

    return guesses_repo.weight_delta(
        prediction.get("weight_lbs"), actual_weight_lbs=actual_weight
    )


def build_pool_scene(
    predictions: list[dict],
    *,
    actual_weight_lbs: float,
    actual_length_in: float | None,
    child_name: str,
    layout: str,
) -> dict:
    """The ranked pool. Returns row/ruler geometry so the template stays a
    thin loop: rows with leader-dot spans, the actual row set apart, and a
    weight ruler with every guess as a dot and the actual as the star."""
    lay = _POOL_LAYOUTS[layout]

    scored = []
    for p in predictions:
        name = _truncate(_clean_text(p.get("name")), 20)
        if not name:
            continue
        scored.append(
            {
                "name": name,
                "weight_lbs": p.get("weight_lbs"),
                "length_in": p.get("length_in"),
                "score": _pool_score(p, actual_weight_lbs),
            }
        )
    scored.sort(key=lambda r: (r["score"] is None, r["score"]))

    shown = scored[: lay["max_rows"]]
    rows = []
    for i, r in enumerate(shown):
        y = lay["y0"] + i * lay["step"]
        guess = _fmt_guess(r["weight_lbs"], r["length_in"])
        adv = _POOL_ROW_FONT
        lx1 = lay["name_x"] + len(r["name"]) * adv * _POOL_NAME_ADV + 28
        lx2 = lay["guess_x"] - len(guess) * adv * _POOL_GUESS_ADV - 28
        rows.append(
            {
                "y": round(y),
                "rank": i + 1,
                "winner": i == 0 and r["score"] is not None,
                "name": r["name"],
                "guess": guess,
                "leader_x1": round(lx1) if lx2 - lx1 > 50 else None,
                "leader_x2": round(lx2),
            }
        )

    # the weight ruler: every guess a dot, the actual the star
    weights = [r["weight_lbs"] for r in scored if r["weight_lbs"]]
    ruler = None
    if weights:
        lo = min(weights + [actual_weight_lbs]) - 0.35
        hi = max(weights + [actual_weight_lbs]) + 0.35
        span = (hi - lo) or 1

        def rx(w: float) -> float:
            return lay["ruler_x1"] + (w - lo) / span * (lay["ruler_x2"] - lay["ruler_x1"])

        ruler = {
            "y": lay["ruler_y"],
            "x1": lay["ruler_x1"],
            "x2": lay["ruler_x2"],
            "dots": [{"x": round(rx(w), 1)} for w in weights],
            "star_x": round(rx(actual_weight_lbs), 1),
            "ticks": [
                {"x": round(rx(lb), 1), "label": f"{lb} LB"}
                for lb in range(math.ceil(lo), math.floor(hi) + 1)
            ],
        }

    actual_y = lay["y0"] + len(rows) * lay["step"] + 42
    return {
        "pool_layout": {
            "rank_x": lay["rank_x"],
            "name_x": lay["name_x"],
            "guess_x": lay["guess_x"],
        },
        "pool_rows": rows,
        "pool_actual": {
            "y": round(actual_y),
            "name": child_name,
            "guess": _fmt_guess(actual_weight_lbs, actual_length_in),
        },
        "pool_ruler": ruler,
        "pool_count": len(scored),
        "pool_winner": rows[0]["name"] if rows and rows[0]["winner"] else None,
        "pool_extra": max(0, len(scored) - len(rows)),
    }


def _build_pool_scene(db: Session, birth: Birth, template: GiftTemplate) -> dict:
    from repositories import guesses as guesses_repo

    predictions = [
        {
            "name": g.display_name,
            "weight_lbs": g.weight_lbs,
            "length_in": g.length_in,
        }
        for g in guesses_repo.list_guesses(db, birth_id=birth.id)
    ]
    if not predictions:
        raise ArtworkError("no-predictions")
    if not birth.child_weight_lbs:
        raise ArtworkError("missing-measurements")
    return build_pool_scene(
        predictions,
        actual_weight_lbs=birth.child_weight_lbs,
        actual_length_in=birth.child_length_in,
        child_name=(birth.child_name or "").strip() or "Baby",
        layout="mug" if template.product_kind == "mug" else "card",
    )


# ── the words: the family's comments as the artwork ──────────────────────


def _wrap(text: str, max_chars: int, max_lines: int = 2) -> list[str]:
    """Greedy word wrap; if the text overflows max_lines the last line is
    truncated with an ellipsis."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        if len(last) >= max_chars:
            last = last[: max_chars - 1].rstrip()
        lines[-1] = last + "…"
    return lines


def build_words_scene(
    quotes: list[dict], *, width: float, height: float, reactions_total: int
) -> dict:
    """Typography-first: up to three of the family's own comments, wrapped
    and vertically centered, each attributed with a first name and time,
    separated by small sparkles. `quotes` are {body, who, when}."""
    quote_size = 62
    line_h = 84
    who_gap = 66
    quote_gap = 118

    blocks = []
    total_h = 0.0
    for q in quotes:
        lines = _wrap(q["body"], max_chars=42)
        h = len(lines) * line_h + who_gap
        blocks.append({"lines": lines, "who": q["who"], "when": q["when"], "h": h})
        total_h += h
    if blocks:
        total_h += quote_gap * (len(blocks) - 1)

    mid = (720 + 1700) / 2  # the band between the title block and the footer
    y = mid - total_h / 2 + quote_size * 0.8

    words_lines: list[dict] = []
    words_dividers: list[float] = []
    for i, b in enumerate(blocks):
        for line in b["lines"]:
            words_lines.append({"t": f"{line}", "y": round(y), "kind": "quote"})
            y += line_h
        who = f"— {b['who']} · {b['when']}" if b["when"] else f"— {b['who']}"
        words_lines.append({"t": who, "y": round(y - line_h + who_gap), "kind": "who"})
        y += who_gap
        if i < len(blocks) - 1:
            words_dividers.append(round(y + quote_gap / 2 - 46))
            y += quote_gap

    return {
        "words_lines": words_lines,
        "words_dividers": words_dividers,
        "reactions_total": reactions_total,
    }


def _gather_quotes(db: Session, birth: Birth, *, limit: int, max_len: int) -> list[dict]:
    """Viewer comments with author first name + time, cleaned for the fonts,
    evenly sampled across the day."""
    rows = db.execute(
        select(
            TimelineEventComment.body,
            TimelineEventComment.created_at,
            User.display_name,
        )
        .join(TimelineEvent, TimelineEvent.id == TimelineEventComment.event_id)
        .join(User, User.id == TimelineEventComment.user_id)
        .where(
            TimelineEvent.birth_id == birth.id,
            TimelineEventComment.deleted_at.is_(None),
        )
        .order_by(TimelineEventComment.created_at.asc())
    ).all()

    cleaned = []
    for body, created_at, display_name in rows:
        text = _clean_text(body)
        if not text:
            continue
        who = _clean_text((display_name or "").split()[0] if display_name else "")
        cleaned.append(
            {
                "body": text,
                "who": who or "family",
                "when": _fmt_time(_localize(created_at)),
            }
        )
    short = [q for q in cleaned if len(q["body"]) <= max_len]
    pool = short or [
        {**q, "body": _truncate(q["body"], max_len)} for q in cleaned
    ]
    return _sample_spaced(pool, limit)


def _build_words_scene(db: Session, birth: Birth, template: GiftTemplate) -> dict:
    quotes = _gather_quotes(db, birth, limit=3, max_len=110)
    if not quotes:
        raise ArtworkError("no-comments")
    counts = _reaction_counts(db, birth)
    return build_words_scene(
        quotes,
        width=template.width,
        height=template.height,
        reactions_total=sum(counts.values()),
    )


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
    ampm = "am" if dt.hour < 12 else "pm"
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
