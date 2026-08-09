"""Full-data export: everything a birth holds, as one ZIP — always free.

The product charges for physical keepsakes and storage, never for the data
itself. This module builds the archive: every media original (full size,
including hidden and orphaned assets — the data is never hostage), plus
CSVs of contractions, guesses, the timeline, comments, reactions, and
family members, a birth.json metadata file, and a README.

Deliberately excluded everywhere: shipping_address, invite tokens,
gift/commerce records, emails and phone numbers, internal user ids.
CSV builders extract named payload keys only — raw payload JSON is never
dumped, so future payload additions can't leak by default.

The zip is written to an anonymous TemporaryFile (unlinked at creation on
POSIX, so it can never orphan) and media bodies are streamed straight from
S3 into the archive — peak memory stays around one chunk regardless of
export size. Temp-disk usage is roughly the media set's total size.
"""
from __future__ import annotations

import csv
import io
import json
import mimetypes
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session

import storage
from models import (
    Birth,
    FamilyMembership,
    MediaAsset,
    TimelineEvent,
    TimelineEventComment,
    TimelineEventReaction,
    TimelineEventType,
    User,
)
from repositories import guesses as guesses_repo
from repositories import media as media_repo
from repositories import timeline as timeline_repo

EXPORT_CHUNK = 1024 * 1024
EXPORT_FORMAT_VERSION = 1
FALLBACK_AUTHOR = "Family member"
UPLOAD_ROOT = Path(__file__).parent / "uploads"

# mimetypes.guess_extension picks oddballs for common types (.jpe, .oga);
# pin the ones we actually store before falling back to it.
_EXT_OVERRIDES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
}


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _csv_text(header: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


def _display_names(db: Session, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {uid for uid in user_ids if uid is not None}
    if not ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {u.id: (u.display_name or FALLBACK_AUTHOR) for u in users}


def _author(names: dict[uuid.UUID, str], user_id: uuid.UUID | None) -> str:
    if user_id is None:
        return FALLBACK_AUTHOR
    return names.get(user_id, FALLBACK_AUTHOR)


def _ext_for(asset: MediaAsset) -> str:
    if asset.mime_type:
        ext = _EXT_OVERRIDES.get(asset.mime_type.lower())
        if ext:
            return ext
        guessed = mimetypes.guess_extension(asset.mime_type)
        if guessed:
            return guessed
    suffix = Path(asset.original_s3_key).suffix
    if suffix and len(suffix) <= 8:
        return suffix
    return ".bin"


def _compact_ts(dt: datetime | None) -> str:
    if dt is None:
        return "00000000T000000Z"
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def plan_media_names(
    events: list[TimelineEvent], assets: list[MediaAsset]
) -> dict[uuid.UUID, str]:
    """media_id -> zip-relative arcname ("media/...").

    Assets attached to a live event sort by that event's sequence; everything
    else (orphans, hidden, media whose event was deleted) still exports under
    an `unattached-` name — the data is never hostage.
    """
    event_by_media: dict[str, TimelineEvent] = {}
    for event in events:
        media_id = (event.payload or {}).get("media_id")
        if media_id:
            event_by_media[str(media_id)] = event

    used: set[str] = set()
    names: dict[uuid.UUID, str] = {}
    for asset in assets:
        ext = _ext_for(asset)
        kind = asset.kind.value if hasattr(asset.kind, "value") else str(asset.kind)
        event = event_by_media.get(str(asset.id))
        if event is not None:
            base = f"{event.sequence_id:04d}-{_compact_ts(event.occurred_at)}-{kind}"
        else:
            base = (
                f"unattached-{_compact_ts(asset.created_at)}-{kind}"
                f"-{str(asset.id)[:8]}"
            )
        name = f"{base}{ext}"
        bump = 2
        while name in used:
            name = f"{base}-{bump}{ext}"
            bump += 1
        used.add(name)
        names[asset.id] = f"media/{name}"
    return names


def contractions_csv(
    events: list[TimelineEvent], names: dict[uuid.UUID, str]
) -> str:
    contractions = sorted(
        (e for e in events if e.event_type is TimelineEventType.contraction),
        key=lambda e: e.occurred_at,
    )
    rows = []
    previous_start: datetime | None = None
    for event in contractions:
        payload = event.payload or {}
        interval = ""
        if previous_start is not None:
            interval = str(int((event.occurred_at - previous_start).total_seconds()))
        duration = payload.get("duration_seconds")
        rows.append(
            [
                event.sequence_id,
                _iso(event.occurred_at),
                payload.get("end_time") or "",
                "" if duration is None else duration,
                interval,
                "yes" if payload.get("ignore_interval_before") else "no",
                _author(names, event.posted_by_user_id),
            ]
        )
        previous_start = event.occurred_at
    return _csv_text(
        [
            "sequence_id",
            "start_time_utc",
            "end_time_utc",
            "duration_seconds",
            "interval_from_previous_start_seconds",
            "interval_ignored",
            "recorded_by",
        ],
        rows,
    )


def guesses_csv(guesses: list, birth: Birth) -> str:
    """One row per guess. The three per-dimension distances replace the old
    single `closeness_score`, which combined pounds and inches at a made-up
    exchange rate and so couldn't be interpreted from the file alone."""
    actual_date = (
        birth.birth_completed_at.date()
        if birth.birth_completed_at is not None
        else None
    )

    def _fmt(value, places=2):
        return "" if value is None else f"{value:.{places}f}"

    rows = []
    for guess in guesses:
        rows.append(
            [
                guess.display_name or FALLBACK_AUTHOR,
                "" if guess.weight_lbs is None else guess.weight_lbs,
                "" if guess.length_in is None else guess.length_in,
                "" if guess.date_guess is None else guess.date_guess.isoformat(),
                _iso(guess.created_at),
                _iso(guess.updated_at),
                _fmt(
                    guesses_repo.weight_delta(
                        guess.weight_lbs, actual_weight_lbs=birth.child_weight_lbs
                    )
                ),
                _fmt(
                    guesses_repo.length_delta(
                        guess.length_in, actual_length_in=birth.child_length_in
                    )
                ),
                (
                    ""
                    if (d := guesses_repo.date_delta(
                        guess.date_guess, actual_date=actual_date
                    )) is None
                    else str(d)
                ),
            ]
        )
    return _csv_text(
        [
            "display_name",
            "weight_lbs",
            "length_in",
            "date_guess",
            "guessed_at_utc",
            "updated_at_utc",
            "weight_off_by_lbs",
            "length_off_by_in",
            "date_off_by_days",
        ],
        rows,
    )


def timeline_csv(
    events: list[TimelineEvent],
    names: dict[uuid.UUID, str],
    media_files: dict[uuid.UUID, str],
) -> str:
    """One row per live event. Named payload keys only — never the raw
    payload dict, which is the leak vector for future additions."""
    rows = []
    for event in events:
        payload = event.payload or {}
        media_file = ""
        media_id = payload.get("media_id")
        if media_id:
            try:
                media_file = media_files.get(uuid.UUID(str(media_id)), "")
            except ValueError:
                media_file = ""
        duration = payload.get("duration_seconds")
        rows.append(
            [
                str(event.id),
                event.sequence_id,
                event.event_type.value,
                _iso(event.occurred_at),
                _iso(event.posted_at),
                _author(names, event.posted_by_user_id),
                event.audience_scope.value,
                payload.get("title") or "",
                payload.get("body") or "",
                payload.get("caption") or "",
                "" if duration is None else duration,
                media_file,
            ]
        )
    return _csv_text(
        [
            "event_id",
            "sequence_id",
            "event_type",
            "occurred_at_utc",
            "posted_at_utc",
            "posted_by",
            "audience_scope",
            "title",
            "body",
            "caption",
            "duration_seconds",
            "media_file",
        ],
        rows,
    )


def comments_csv(
    comments: list[TimelineEventComment],
    seq_by_event: dict[uuid.UUID, int],
    names: dict[uuid.UUID, str],
) -> str:
    rows = [
        [
            str(comment.event_id),
            seq_by_event.get(comment.event_id, ""),
            _iso(comment.created_at),
            _author(names, comment.user_id),
            comment.body,
            "yes" if comment.updated_at > comment.created_at else "no",
        ]
        for comment in comments
    ]
    return _csv_text(
        [
            "event_id",
            "event_sequence_id",
            "commented_at_utc",
            "author",
            "body",
            "edited",
        ],
        rows,
    )


def reactions_csv(
    reactions: list[TimelineEventReaction],
    seq_by_event: dict[uuid.UUID, int],
    names: dict[uuid.UUID, str],
) -> str:
    rows = [
        [
            str(reaction.event_id),
            seq_by_event.get(reaction.event_id, ""),
            _iso(reaction.created_at),
            _author(names, reaction.user_id),
            reaction.kind.value,
        ]
        for reaction in reactions
    ]
    return _csv_text(
        ["event_id", "event_sequence_id", "reacted_at_utc", "reactor", "kind"],
        rows,
    )


def family_csv(members: list[tuple[str | None, str, datetime]]) -> str:
    rows = [
        [display_name or FALLBACK_AUTHOR, role, _iso(joined_at)]
        for display_name, role, joined_at in members
    ]
    return _csv_text(["display_name", "role", "joined_at_utc"], rows)


def birth_json(birth: Birth) -> str:
    """Allowlist only. Excluded on purpose: shipping_address,
    storage-tier/billing fields, every internal id."""
    return json.dumps(
        {
            "child_name": birth.child_name,
            "slug": birth.slug,
            "status": birth.status.value,
            "theme": birth.theme,
            "child_dob": _iso(birth.child_dob) or None,
            "child_weight_lbs": birth.child_weight_lbs,
            "child_length_in": birth.child_length_in,
            "birth_started_at": _iso(birth.birth_started_at) or None,
            "birth_completed_at": _iso(birth.birth_completed_at) or None,
            "created_at": _iso(birth.created_at) or None,
            "exported_at": _iso(datetime.now(timezone.utc)),
            "export_format_version": EXPORT_FORMAT_VERSION,
        },
        indent=2,
    )


def readme_text(birth: Birth) -> str:
    name = birth.child_name or birth.slug
    return f"""Arrival Story — full data export for {name}

This export is always free and always available. Your memories are yours.

What's in here (all times are UTC, ISO-8601):

  birth.json        Basic details: name, dates, measurements.
  contractions.csv  Every contraction: start, end, duration, and the
                    interval since the previous one.
  guesses.csv       The guessing jar: everyone's weight/length guesses,
                    scored against the actuals once known (lower wins).
  timeline.csv      Every timeline entry — photos, videos, voice memos,
                    notes, milestones, contractions. The media_file column
                    points at the matching file in media/.
  comments.csv      Every comment, joined to its timeline entry via
                    event_id / event_sequence_id.
  reactions.csv     Every reaction (love / wow / pray), same joins.
  family.csv        Who was in the circle, and their role.
  media/            Every photo, video, and voice memo at full original
                    quality. Files attached to the timeline are named
                    NNNN-<timestamp>-<kind> where NNNN is the timeline
                    sequence; anything else is prefixed "unattached-".
  errors.txt        Only present if a stored file could not be read; the
                    rest of the export is unaffected.
"""


def _zip_date_time(dt: datetime | None) -> tuple[int, int, int, int, int, int]:
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    year = max(dt.year, 1980)  # zip epoch floor
    return (year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def _open_media_source(asset: MediaAsset):
    """File-like for the original bytes: S3 StreamingBody, or the legacy
    `local:` path (same containment guard as the /media route)."""
    if media_repo.is_local_key(asset.original_s3_key):
        rel = media_repo.local_path(asset.original_s3_key)
        path = (Path(__file__).parent / rel).resolve()
        if not path.is_file() or UPLOAD_ROOT.resolve() not in path.parents:
            raise FileNotFoundError(asset.original_s3_key)
        return open(path, "rb")
    return storage.get_object_stream(asset.original_s3_key)


def _add_media(
    zf: zipfile.ZipFile,
    root: str,
    asset: MediaAsset,
    arcname: str,
    errors: list[str],
) -> None:
    source = None
    try:
        source = _open_media_source(asset)
        zinfo = zipfile.ZipInfo(
            f"{root}/{arcname}", date_time=_zip_date_time(asset.created_at)
        )
        # Media formats are already compressed; deflating them burns CPU
        # for ~0% savings on a potentially multi-GB pass.
        zinfo.compress_type = zipfile.ZIP_STORED
        with zf.open(zinfo, "w", force_zip64=True) as dest:
            shutil.copyfileobj(source, dest, EXPORT_CHUNK)
    except (ClientError, BotoCoreError, FileNotFoundError, OSError):
        errors.append(
            f"{arcname}: source file missing or unreadable "
            f"(media_id={asset.id}) — skipped"
        )
    finally:
        if source is not None:
            try:
                source.close()
            except Exception:
                pass


def build_export_zip(db: Session, birth: Birth) -> tuple[BinaryIO, str]:
    """Build the archive; returns (open temp file seeked to 0, filename).

    Caller owns closing the file (dropping the handle also reclaims the
    disk — the temp file is anonymous/unlinked).
    """
    events = timeline_repo.list_events(db, birth_id=birth.id, limit=100_000)
    event_ids = [e.id for e in events]
    seq_by_event = {e.id: e.sequence_id for e in events}

    assets = list(
        db.scalars(
            select(MediaAsset)
            .where(MediaAsset.birth_id == birth.id)
            .order_by(MediaAsset.created_at.asc())
        ).all()
    )
    guesses = guesses_repo.list_guesses(db, birth_id=birth.id)
    comments: list[TimelineEventComment] = []
    reactions: list[TimelineEventReaction] = []
    if event_ids:
        comments = list(
            db.scalars(
                select(TimelineEventComment)
                .where(
                    TimelineEventComment.event_id.in_(event_ids),
                    TimelineEventComment.deleted_at.is_(None),
                )
                .order_by(TimelineEventComment.created_at.asc())
            ).all()
        )
        reactions = list(
            db.scalars(
                select(TimelineEventReaction)
                .where(TimelineEventReaction.event_id.in_(event_ids))
                .order_by(TimelineEventReaction.created_at.asc())
            ).all()
        )
    memberships = db.execute(
        select(User.display_name, FamilyMembership.role, FamilyMembership.joined_at)
        .join(User, User.id == FamilyMembership.user_id)
        .where(FamilyMembership.family_id == birth.family_id)
        .order_by(FamilyMembership.joined_at.asc())
    ).all()
    members = [(row[0], row[1].value, row[2]) for row in memberships]

    names = _display_names(
        db,
        {e.posted_by_user_id for e in events}
        | {c.user_id for c in comments}
        | {r.user_id for r in reactions},
    )
    media_files = plan_media_names(events, assets)

    root = f"{birth.slug}-export-{datetime.now(timezone.utc):%Y%m%d}"
    tmp = tempfile.TemporaryFile()
    errors: list[str] = []
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{root}/README.txt", readme_text(birth))
        zf.writestr(f"{root}/birth.json", birth_json(birth))
        zf.writestr(f"{root}/contractions.csv", contractions_csv(events, names))
        zf.writestr(f"{root}/guesses.csv", guesses_csv(guesses, birth))
        zf.writestr(f"{root}/timeline.csv", timeline_csv(events, names, media_files))
        zf.writestr(
            f"{root}/comments.csv", comments_csv(comments, seq_by_event, names)
        )
        zf.writestr(
            f"{root}/reactions.csv", reactions_csv(reactions, seq_by_event, names)
        )
        zf.writestr(f"{root}/family.csv", family_csv(members))
        for asset in assets:
            _add_media(zf, root, asset, media_files[asset.id], errors)
        if errors:
            zf.writestr(f"{root}/errors.txt", "\n".join(errors) + "\n")
    tmp.seek(0)
    return tmp, f"{root}.zip"
