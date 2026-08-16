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
from datetime import datetime, timedelta
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


def _chevrons_path(cx: float, cy: float, r: float) -> str:
    """Two chevrons driving outward (pushing). Open polylines rather than
    filled arrowheads — stroked they carry the same weight as the rest of the
    set, where filled they were the heaviest mark on the dial."""
    def one(dy: float) -> str:
        return (
            f"M {cx - r * 0.84:.1f},{cy + dy + r * 0.30:.1f} "
            f"L {cx:.1f},{cy + dy - r * 0.34:.1f} "
            f"L {cx + r * 0.84:.1f},{cy + dy + r * 0.30:.1f}"
        )
    return f"{one(-r * 0.34)} {one(r * 0.44)}"


def _wave_path(cx: float, cy: float, r: float) -> str:
    """Two swells (transition). Open S-curves rather than filled ribbons —
    the last mark to stop being a silhouette, so the set is one language.
    One swell alone read as a tilde; the pair reads as water, the way ≈ does."""
    def swell(dy: float) -> str:
        return (
            f"M {cx - r * 0.92:.1f},{cy + dy:.1f} "
            f"Q {cx - r * 0.46:.1f},{cy + dy - r * 0.62:.1f} {cx:.1f},{cy + dy:.1f} "
            f"Q {cx + r * 0.46:.1f},{cy + dy + r * 0.62:.1f} "
            f"{cx + r * 0.92:.1f},{cy + dy:.1f}"
        )
    return f"{swell(-r * 0.38)} {swell(r * 0.42)}"


def _bottle_path(cx: float, cy: float, r: float) -> str:
    """A baby bottle — teat, collar, body (first feed)."""
    return (
        f"M {cx - r * 0.11:.1f},{cy - r * 0.98:.1f} "
        f"Q {cx:.1f},{cy - r * 1.30:.1f} {cx + r * 0.11:.1f},{cy - r * 0.98:.1f} "
        f"L {cx + r * 0.11:.1f},{cy - r * 0.80:.1f} "
        f"L {cx + r * 0.32:.1f},{cy - r * 0.80:.1f} "
        f"L {cx + r * 0.32:.1f},{cy - r * 0.58:.1f} "
        f"Q {cx + r * 0.60:.1f},{cy - r * 0.44:.1f} {cx + r * 0.60:.1f},{cy - r * 0.14:.1f} "
        f"L {cx + r * 0.60:.1f},{cy + r * 0.82:.1f} "
        f"Q {cx + r * 0.60:.1f},{cy + r * 1.04:.1f} {cx + r * 0.38:.1f},{cy + r * 1.04:.1f} "
        f"L {cx - r * 0.38:.1f},{cy + r * 1.04:.1f} "
        f"Q {cx - r * 0.60:.1f},{cy + r * 1.04:.1f} {cx - r * 0.60:.1f},{cy + r * 0.82:.1f} "
        f"L {cx - r * 0.60:.1f},{cy - r * 0.14:.1f} "
        f"Q {cx - r * 0.60:.1f},{cy - r * 0.44:.1f} {cx - r * 0.32:.1f},{cy - r * 0.58:.1f} "
        f"L {cx - r * 0.32:.1f},{cy - r * 0.80:.1f} "
        f"L {cx - r * 0.11:.1f},{cy - r * 0.80:.1f} Z"
    )


_CAR_D = (
    "M 84.99 37.498 l -16.835 -2.571 c -0.428 -0.065 -0.824 -0.277 -1.115 -0.597 l -8.952 -9.805 c -1.115 -1.222 -2.703 -1.922 -4.357 -1.922 H 25.005 c -1.991 0 -3.833 0.993 -4.928 2.656 l -5.862 8.905 c -0.234 0.356 -0.586 0.625 -0.992 0.759 l -9.169 3.022 C 1.629 38.744 0 40.996 0 43.548 v 9.404 c 0 3.254 2.647 5.9 5.9 5.9 h 3.451 c 0.969 4.866 5.269 8.545 10.416 8.545 s 9.447 -3.679 10.416 -8.545 h 30.139 c 0.969 4.866 5.27 8.545 10.416 8.545 s 9.446 -3.679 10.415 -8.545 H 84.1 c 3.254 0 5.9 -2.646 5.9 -5.9 v -9.622 C 90 40.394 87.893 37.941 84.99 37.498 z M 19.767 63.397 c -3.652 0 -6.623 -2.971 -6.623 -6.622 c 0 -3.652 2.971 -6.623 6.623 -6.623 s 6.623 2.971 6.623 6.623 C 26.39 60.427 23.419 63.397 19.767 63.397 z M 70.738 63.397 c -3.652 0 -6.623 -2.971 -6.623 -6.622 c 0 -3.652 2.971 -6.623 6.623 -6.623 c 3.651 0 6.622 2.971 6.622 6.623 C 77.36 60.427 74.39 63.397 70.738 63.397 z M 86 52.952 c 0 1.048 -0.853 1.9 -1.9 1.9 h -2.922 c -0.908 -4.941 -5.239 -8.7 -10.439 -8.7 s -9.531 3.759 -10.44 8.7 H 30.207 c -0.909 -4.941 -5.24 -8.7 -10.44 -8.7 s -9.531 3.759 -10.439 8.7 H 5.9 c -1.048 0 -1.9 -0.853 -1.9 -1.9 v -9.404 c 0 -0.822 0.524 -1.547 1.306 -1.805 l 9.168 -3.021 c 1.26 -0.415 2.354 -1.253 3.083 -2.36 l 5.861 -8.905 c 0.353 -0.536 0.946 -0.855 1.587 -0.855 H 53.73 c 0.532 0 1.044 0.226 1.403 0.62 l 8.952 9.805 c 0.907 0.993 2.139 1.652 3.467 1.854 l 16.834 2.571 C 85.321 41.595 86 42.385 86 43.331 V 52.952 z"
)


_HOSPITAL_D = (
    "M 51.948 73.273 H 38.052 c -1.104 0 -2 -0.896 -2 -2 v -9.621 h -9.621 c -1.104 0 -2 -0.896 -2 -2 V 45.757 c 0 -1.104 0.896 -2 2 -2 h 9.621 v -9.62 c 0 -1.104 0.896 -2 2 -2 h 13.896 c 1.104 0 2 0.896 2 2 v 9.62 h 9.62 c 1.104 0 2 0.896 2 2 v 13.895 c 0 1.104 -0.896 2 -2 2 h -9.62 v 9.621 C 53.948 72.378 53.053 73.273 51.948 73.273 z M 40.052 69.273 h 9.896 v -9.621 c 0 -1.104 0.896 -2 2 -2 h 9.62 v -9.895 h -9.62 c -1.104 0 -2 -0.896 -2 -2 v -9.62 h -9.896 v 9.62 c 0 1.104 -0.896 2 -2 2 h -9.621 v 9.895 h 9.621 c 1.104 0 2 0.896 2 2 V 69.273 z M 78.113 84.056 H 11.887 c -1.104 0 -2 -0.896 -2 -2 V 30.312 c 0 -1.104 0.896 -2 2 -2 s 2 0.896 2 2 v 49.745 h 62.226 V 30.067 c 0 -1.104 0.896 -2 2 -2 s 2 0.896 2 2 v 51.989 C 80.113 83.161 79.218 84.056 78.113 84.056 z M 2.002 38.835 c -0.65 0 -1.287 -0.316 -1.671 -0.898 c -0.608 -0.922 -0.354 -2.163 0.568 -2.771 L 44.687 6.274 c 0.679 -0.449 1.561 -0.439 2.231 0.019 L 89.13 35.184 c 0.911 0.624 1.145 1.869 0.521 2.78 c -0.624 0.912 -1.867 1.146 -2.78 0.521 L 45.768 10.353 L 3.102 38.504 C 2.762 38.728 2.38 38.835 2.002 38.835 z"
)


_FLAME_D = (
    "M 15.514 31.528 c -6.405 0 -11.615 -5.211 -11.615 -11.615 c 0 -0.043 0.004 -0.085 0.011 -0.126 c 0.03 -1.599 0.633 -3.133 1.27 -4.754 c 1 -2.545 2.034 -5.177 0.899 -8.325 C 5.987 6.452 6.048 6.167 6.237 5.972 c 0.189 -0.195 0.472 -0.266 0.731 -0.183 c 2.041 0.66 3.475 1.832 4.752 3.94 c 2.009 -3.238 2.519 -5.743 2.015 -9.421 c -0.039 -0.287 0.099 -0.569 0.35 -0.713 c 0.251 -0.144 0.565 -0.123 0.793 0.055 c 3.044 2.37 4.743 5.412 5.073 9.07 c 0.95 -1.127 2.133 -1.852 3.254 -2.425 c 0.253 -0.129 0.557 -0.096 0.777 0.084 c 0.219 0.18 0.31 0.473 0.232 0.746 c -0.999 3.48 0.22 5.882 1.399 8.205 c 0.755 1.488 1.47 2.896 1.506 4.458 c 0.007 0.041 0.011 0.082 0.011 0.125 C 27.129 26.317 21.918 31.528 15.514 31.528 z M 5.322 20.028 c 0.062 5.567 4.61 10.077 10.191 10.077 c 5.582 0 10.13 -4.51 10.191 -10.078 c -0.006 -0.037 -0.009 -0.075 -0.009 -0.114 c 0 -1.271 -0.627 -2.507 -1.354 -3.938 c -1.017 -2.005 -2.249 -4.431 -1.834 -7.633 c -1.098 0.741 -2.065 1.739 -2.595 3.328 c -0.114 0.342 -0.464 0.546 -0.819 0.472 c -0.353 -0.073 -0.596 -0.399 -0.565 -0.758 c 0.331 -3.849 -0.722 -6.958 -3.21 -9.452 c 0.169 3.453 -0.721 6.132 -3.057 9.574 c -0.141 0.208 -0.383 0.325 -0.632 0.311 c -0.251 -0.015 -0.475 -0.161 -0.59 -0.385 c -0.961 -1.866 -1.926 -3.008 -3.213 -3.73 c 0.583 3.001 -0.422 5.558 -1.323 7.851 c -0.603 1.535 -1.173 2.985 -1.173 4.359 C 5.332 19.952 5.329 19.99 5.322 20.028 z"
)


# ── the milestone marks ──────────────────────────────────────────────────
# Every mark is an outline, so nothing on the dial is heavier than the ticks
# and rays it sits among. Two kinds: hand-drawn paths, which are open or
# unthickened and get stroked; and imported icons, which carry their own
# outline as a filled shape and need their own transform.
#
# `born` is a heart, drawn larger — it's the one mark on the artwork that is a
# person. `first_hold` is deliberately absent: hands need fingers to read and
# fingers turn to mush at this size, and it's the same moment as the arrival
# half an hour later, so the heart already says it.

_STROKE_GLYPHS = {
    "water_broke": _droplet_path,
    "first_feed": _bottle_path,
    "pushing": _chevrons_path,
    "transition": _wave_path,
}

# kind → (path, size in multiples of r, fill-rule, ink bounding box). Several
# are crops out of a larger artboard, so centring on the artboard would hang
# them off the ring — hence the box.
_ICON_GLYPHS = {
    "arrived": (_HOSPITAL_D, 2.0, "evenodd", (0.0, 0.0, 90.0, 90.0)),
    "going_home": (_CAR_D, 2.4, "nonzero", (0.0, 22.6, 90.0, 67.4)),
    "active_labor": (_FLAME_D, 2.2, "evenodd", (3.90, 0.0, 27.15, 31.65)),
}

def has_mark(kind: str | None) -> bool:
    """Whether a milestone kind has a mark of its own to draw.

    Only kinds we can actually say something with get drawn. `born` is handled
    separately (the heart, larger, on the outermost ring). `first_hold` has no
    mark on purpose: hands need fingers, fingers don't survive at this size,
    and the heart half an hour earlier already says it. `name_announced` is
    redundant — the name is set in 175pt italic on the same artwork.
    `other` is unnameable by definition, and a generic diamond meaning
    "something happened, we won't say what" is noise on a keepsake.

    Anything new falls here too, and draws nothing until someone gives it a
    mark — better a gap than a shape that means nothing.
    """
    return kind in _STROKE_GLYPHS or kind in _ICON_GLYPHS

MARK_R = 13.0          # the marks, as drawn on the dial
MARK_HALO_R = 21.0     # page-coloured ground so they clear the rays
BORN_MARK_R = 18.0
BORN_HALO_R = 26.0
MARK_STROKE = 2.6
BORN_STROKE = 3.0


def _icon_transform(kind: str, mx: float, my: float, r: float) -> tuple[str, str, str]:
    """(d, transform, fill-rule) placing an imported icon centred on (mx, my)."""
    d, size, rule, (x0, y0, x1, y1) = _ICON_GLYPHS[kind]
    span = max(x1 - x0, y1 - y0)
    scale = (r * size) / span
    bcx, bcy = (x0 + x1) / 2, (y0 + y1) / 2
    transform = (
        f"translate({mx - bcx * scale:.2f},{my - bcy * scale:.2f}) "
        f"scale({scale:.4f})"
    )
    return d, transform, rule


def _mark_at(kind: str, mx: float, my: float) -> dict:
    """One milestone mark, ready for the template: either a stroked path or an
    imported icon with its own transform."""
    if kind in _ICON_GLYPHS:
        d, transform, rule = _icon_transform(kind, mx, my, MARK_R)
        return {
            "x": round(mx, 1), "y": round(my, 1), "d": d,
            "transform": transform, "rule": rule,
            "stroke": None, "halo": MARK_HALO_R,
        }
    draw = _STROKE_GLYPHS[kind]
    return {
        "x": round(mx, 1), "y": round(my, 1), "d": draw(mx, my, MARK_R),
        "transform": None, "rule": "nonzero",
        "stroke": MARK_STROKE, "halo": MARK_HALO_R,
    }


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
    # The photo left the middle of the face for a spot beside the name, so
    # this variant no longer has to hold its inner radius open and can take
    # the same geometry as the plain clock — which it needs, since the day
    # rings are built inward from r_in.
    "hours_photo": {"r_ring": 460.0, "r_in": 205.0, "len_lo": 80.0, "len_hi": 225.0},
    "orbit": {"r_ring": 420.0, "r_in": 190.0, "len_lo": 70.0, "len_hi": 190.0},
}
# Hero-photo radius inside the hours_photo face (hairline ring sits just out).
CLOCK_PHOTO_R = 195.0


RING_GAP = 14.0        # keeps adjacent day rings from touching
MAX_RINGS = 3
AM_ALPHA, PM_ALPHA = 0.34, 0.74
AM_WIDTH, PM_WIDTH = 2.6, 4.2
BUILD_ALPHA = 0.16     # late labor deepens, on top of the AM/PM tone


def _ring_layout(n: int, r_in: float, r_out: float) -> tuple[float, float, float]:
    """(innermost radius, band width, usable band) for `n` day rings sharing
    the space a single ring used to have to itself. One ring keeps the old
    geometry exactly; only multi-day artwork pays for the compression."""
    inner = r_in / (n ** 0.75)
    band = (r_out - inner) / n
    return inner, band, band - (RING_GAP if n > 1 else 0.0)


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
    """Geometry for the radial labor clock: one 12-hour dial, and a concentric
    ring for every day of labor. Each contraction is a stroke at the clock
    angle of the moment it happened, its length that contraction's duration
    and its tone whether it fell before or after noon.

    One day is one ring and looks the way this artwork always has. Two days is
    two rings, three is three, and the band divides between them — so only
    multi-day labor pays for the extra. Past three days the oldest fold into
    the innermost ring rather than being dropped.

    This replaces a fallback that silently stopped meaning clock time past
    11h31m and swept the strokes linearly instead, which made a long labor's
    artwork incomparable to a short one with nothing saying so. A day that
    runs past twelve hours now wraps onto its own ring and the overlap layers,
    which is honest and happens to look better.

    `len_lo`/`len_hi` are accepted for call compatibility; ray length is
    derived from whatever band its ring actually gets.
    """
    r_out = r_ring - 30.0
    marks: list[dict] = []

    # ── which day each contraction belongs to ────────────────────────────
    # Rolling 24h windows from the first contraction, not calendar dates: an
    # evening labor that crosses midnight is one night, not two days.
    if offsets_seconds:
        day_of = [o // 86400 for o in offsets_seconds]
        total_days = max(day_of) + 1
    else:
        day_of, total_days = [], 1
    n = max(1, min(total_days, MAX_RINGS))
    shift = total_days - n

    inner, band, usable = _ring_layout(n, r_in, r_out)
    rings = [
        {
            "base": round(inner + k * band, 1),
            "label": (
                "EARLIER" if (total_days > MAX_RINGS and k == 0)
                else f"DAY {k + 1 + shift}"
            ),
            "strokes": [],
        }
        for k in range(n)
    ]

    def ring_index(offset: int) -> int:
        return max(0, min(n - 1, offset // 86400 - shift))

    def at(offset: int) -> datetime | None:
        if first_contraction_at is None:
            return None
        return first_contraction_at + timedelta(seconds=offset)

    lo = min(durations) if durations else 0
    hi = max(durations) if durations else 1
    span = (hi - lo) or 1
    total = offsets_seconds[-1] if offsets_seconds else 0

    for offset, duration in zip(offsets_seconds, durations):
        when = at(offset)
        # Without a real start time there are no clock angles to be had; fall
        # back to sweeping the strokes evenly so the shape is still honest.
        a = (
            _clock_angle(when) if when is not None
            else -math.pi / 2 + (offset / (total or 1)) * 2 * math.pi * 0.93
        )
        ring = rings[ring_index(offset)]
        length = 0.36 * usable + ((duration - lo) / span) * (usable - 0.36 * usable)
        r0 = ring["base"]
        r1 = r0 + length
        am = when is not None and when.hour < 12
        progress = offset / (total or 1)
        ring["strokes"].append(
            {
                "x1": round(cx + r0 * math.cos(a), 1),
                "y1": round(cy + r0 * math.sin(a), 1),
                "x2": round(cx + r1 * math.cos(a), 1),
                "y2": round(cy + r1 * math.sin(a), 1),
                "am": am,
                "w": AM_WIDTH if am else PM_WIDTH,
                "o": round((AM_ALPHA if am else PM_ALPHA) + BUILD_ALPHA * progress, 3),
            }
        )

    # ── the dial ─────────────────────────────────────────────────────────
    ticks = []
    for i in range(60):
        a = (i / 60) * 2 * math.pi - math.pi / 2
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

    # It wasn't obvious this was a clock at all, which made every angle on it
    # decoration. Four numerals is enough to declare the face.
    numerals = []
    for text, a in (("12", -math.pi / 2), ("3", 0.0), ("6", math.pi / 2), ("9", math.pi)):
        numerals.append(
            {
                "x": round(cx + (r_ring + 46) * math.cos(a), 1),
                "y": round(cy + (r_ring + 46) * math.sin(a) + 13, 1),
                "t": text,
            }
        )

    # ── the marks ────────────────────────────────────────────────────────
    # Each rides the grey circle of the day it happened on, inside the dial.
    # They used to float outside it with nothing anchoring them, which is how
    # a milestone label ended up crossing the text block beside the clock.
    placed: list[tuple[int, float]] = []

    def crowded(k: int, a: float) -> bool:
        return any(
            k == pk and abs((a - pa + math.pi) % (2 * math.pi) - math.pi) < 0.22
            for pk, pa in placed
        )

    for m in milestones or []:
        kind = m.get("kind")
        if not has_mark(kind):
            continue
        offset = int(m["offset_seconds"])
        when = at(offset)
        if when is None:
            continue
        a = _clock_angle(when)
        k = ring_index(offset)
        if crowded(k, a):
            continue
        placed.append((k, a))
        r = rings[k]["base"]
        marks.append(_mark_at(kind, cx + r * math.cos(a), cy + r * math.sin(a)))

    # the arrival, on the outermost ring — the last mark of the story, and the
    # only one that is a person rather than an event
    born_mark = None
    if born_at is not None:
        a = _clock_angle(born_at)
        r = rings[-1]["base"]
        bx, by = cx + r * math.cos(a), cy + r * math.sin(a)
        born_mark = {
            "x": round(bx, 1), "y": round(by, 1),
            "d": _heart_path(bx, by, BORN_MARK_R),
            "transform": None, "rule": "nonzero",
            "stroke": BORN_STROKE, "halo": BORN_HALO_R,
        }

    return {
        "clock_rings": rings,
        "clock_ticks": ticks,
        "clock_numerals": numerals,
        "clock_marks": marks,
        "clock_born_mark": born_mark,
        # only worth naming the days when there is more than one
        "clock_day_labels": n > 1,
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
