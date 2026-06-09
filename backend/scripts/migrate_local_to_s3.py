"""Upload legacy `local:` media files to S3 and rewrite keys in the DB.

Run once after enabling MinIO / real S3:

    docker compose exec backend python scripts/migrate_local_to_s3.py

Skips rows whose `original_s3_key` does not start with `local:`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from db import SessionLocal
from models import MediaAsset
from repositories import media as media_repo
import storage


BACKEND_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    storage.ensure_bucket()
    db = SessionLocal()
    migrated = 0
    skipped = 0
    errors: list[str] = []
    try:
        assets = db.scalars(
            select(MediaAsset).where(
                MediaAsset.original_s3_key.like(f"{media_repo.LOCAL_KEY_PREFIX}%")
            )
        ).all()
        for asset in assets:
            rel = media_repo.local_path(asset.original_s3_key)
            path = (BACKEND_ROOT / rel).resolve()
            if not path.is_file():
                errors.append(f"{asset.id}: file missing at {path}")
                skipped += 1
                continue
            filename = path.name
            key = media_repo.media_object_key(
                family_id=asset.family_id,
                birth_id=asset.birth_id,
                filename=filename,
            )
            body = path.read_bytes()
            storage.put_object(
                key=key,
                body=body,
                content_type=asset.mime_type,
            )
            asset.original_s3_key = key
            migrated += 1
        db.commit()
    finally:
        db.close()

    print(f"Migrated {migrated} assets to S3.")
    if skipped:
        print(f"Skipped {skipped} (missing files).")
    for err in errors:
        print(f"  {err}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
