"""Media asset creates + reads.

`original_s3_key` holds the S3 object key (e.g. `f/{family_id}/b/{birth_id}/…`).
Legacy rows migrated from PR 1 may still use the `local:` prefix until
`scripts/migrate_local_to_s3.py` has been run.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

import image_variants
from models import MediaAsset, MediaKind, MediaStorageTier
from storage import get_object_bytes, object_key as s3_object_key, put_object


logger = logging.getLogger(__name__)

LOCAL_KEY_PREFIX = "local:"

# A claim older than this is treated as abandoned — the worker was killed
# mid-photo — and the row goes back in the queue.
VARIANT_CLAIM_STALE = "10 minutes"

# Which column holds each variant. "raw" is deliberately absent: the original
# is the fallback for everything, so it is never looked up by name.
VARIANT_COLUMNS = {
    "display": "display_s3_key",
    "thumbnail": "thumbnail_s3_key",
}


def local_key(filename: str) -> str:
    """Legacy PR 1 filesystem key — only used by migrate_local_to_s3."""
    return f"{LOCAL_KEY_PREFIX}uploads/{filename}"


def media_object_key(*, family_id: uuid.UUID, birth_id: uuid.UUID, filename: str) -> str:
    return s3_object_key(family_id=family_id, birth_id=birth_id, filename=filename)


def is_local_key(key: str) -> bool:
    return key.startswith(LOCAL_KEY_PREFIX)


def local_path(key: str) -> str:
    """Strip the `local:` prefix and return the on-disk relative path."""
    if not is_local_key(key):
        raise ValueError(f"Not a local key: {key}")
    return key[len(LOCAL_KEY_PREFIX) :]


def create_media_asset(
    db: Session,
    *,
    family_id: uuid.UUID,
    birth_id: uuid.UUID,
    uploaded_by_user_id: uuid.UUID,
    kind: MediaKind,
    original_s3_key: str,
    mime_type: str | None = None,
    bytes_: int | None = None,
    width: int | None = None,
    height: int | None = None,
    duration_seconds: int | None = None,
) -> MediaAsset:
    asset = MediaAsset(
        family_id=family_id,
        birth_id=birth_id,
        uploaded_by_user_id=uploaded_by_user_id,
        kind=kind,
        original_s3_key=original_s3_key,
        mime_type=mime_type,
        bytes=bytes_,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        storage_tier=MediaStorageTier.hot,
    )
    db.add(asset)
    db.flush()
    return asset


def get_media_asset(db: Session, media_id: uuid.UUID) -> MediaAsset | None:
    return db.get(MediaAsset, media_id)


def variant_key(asset: MediaAsset, variant: str | None) -> str:
    """The object to serve for one variant of one asset.

    Falls back to the original whenever the variant hasn't been made yet, or
    isn't made for this kind of media at all. That fallback is the whole
    reason this is safe to ship ahead of the worker: every reader keeps
    working, and simply gets lighter as the copies appear.
    """
    column = VARIANT_COLUMNS.get(variant or "raw")
    if column is None:
        return asset.original_s3_key
    return getattr(asset, column, None) or asset.original_s3_key


def claim_for_variants(db: Session) -> MediaAsset | None:
    """Take the oldest photo still waiting for its smaller copies, or None.

    One statement, then commit: the work that follows is S3 I/O, and holding
    a row lock across a network round trip is how you end up with an
    idle-in-transaction session blocking a migration. `SKIP LOCKED` is what
    lets a second worker be started without either of them doing the same
    photo twice.
    """
    row = db.execute(
        text(
            f"""
            UPDATE media_assets SET variants_attempted_at = now()
            WHERE id = (
                SELECT id FROM media_assets
                WHERE kind = 'photo' AND archived_at IS NULL
                  AND display_s3_key IS NULL AND variants_error IS NULL
                  AND (variants_attempted_at IS NULL
                       OR variants_attempted_at < now() - interval '{VARIANT_CLAIM_STALE}')
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id
            """
        )
    ).first()
    db.commit()
    if row is None:
        return None
    return db.get(MediaAsset, row[0])


def build_variants(db: Session, asset: MediaAsset) -> dict[str, str]:
    """Make and store one photo's smaller copies, and record them.

    Also fills `width`/`height`, which nothing has ever populated — the
    dimensions are free while the image is open, and anything laying the
    photo out would otherwise have to decode the original to learn them.
    """
    raw = get_object_bytes(asset.original_s3_key)
    variants, (width, height) = image_variants.build(raw)
    stored: dict[str, str] = {}
    for name, body in variants.items():
        key = s3_object_key(
            family_id=asset.family_id,
            birth_id=asset.birth_id,
            filename=f"variants/{asset.id}-{name}.webp",
        )
        put_object(key=key, body=body, content_type=image_variants.CONTENT_TYPE)
        stored[name] = key
    for name, column in VARIANT_COLUMNS.items():
        if name in stored:
            setattr(asset, column, stored[name])
    asset.width, asset.height = width, height
    asset.variants_error = None
    db.commit()
    return stored


def record_variant_failure(db: Session, asset: MediaAsset, reason: str) -> None:
    """Retire a photo whose bytes we can't read, rather than retrying it
    forever. Clearing `variants_error` puts it back in the queue."""
    asset.variants_error = reason[:500]
    db.commit()
