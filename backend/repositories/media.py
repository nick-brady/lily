"""Media asset creates + reads.

`original_s3_key` is overloaded in PR 1: until PR 5 wires S3 it holds a
local filesystem path (prefixed with `local:` so the source is unambiguous).
The column name stays — that's where the key actually goes.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from models import MediaAsset, MediaKind, MediaStorageTier


LOCAL_KEY_PREFIX = "local:"


def local_key(filename: str) -> str:
    return f"{LOCAL_KEY_PREFIX}uploads/{filename}"


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
