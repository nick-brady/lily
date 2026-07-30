"""Media upload/serving, public marketing assets, and the full-page export."""
from __future__ import annotations

import mimetypes
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from time import monotonic

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

import export as export_mod
from auth import get_current_user, get_optional_current_user
from db import get_db
from events import publish_event_change
from models import (
    AudienceScope,
    FamilyMembership,
    FamilyRole,
    MediaAsset,
    MediaKind,
    TimelineEvent,
    TimelineEventType,
    User,
)
from repositories import births as births_repo
from repositories import media as media_repo
from repositories import timeline as timeline_repo
from routes.deps import (
    BirthAccess,
    require_parent_access,
    require_parent_access_stream,
)
from routes.serializers import serialize_event_out
from schemas import TimelineEventOut
from storage import presigned_get_url, put_object

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _default_extension(kind: MediaKind) -> str:
    return {
        MediaKind.photo: ".jpg",
        MediaKind.video: ".mp4",
        MediaKind.voice_memo: ".webm",
    }[kind]


@router.post("/birth/{birth_id}/media", response_model=TimelineEventOut)
async def upload_media(
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    kind: MediaKind = Form(...),
    audience_scope: AudienceScope = Form(AudienceScope.public),
    # photos especially get uploaded well after the moment they capture
    occurred_at: datetime | None = Form(None),
    access: BirthAccess = Depends(require_parent_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineEventOut:
    extension = Path(file.filename or "").suffix or _default_extension(kind)
    filename = f"{uuid.uuid4()}{extension}"
    content = await file.read()
    key = media_repo.media_object_key(
        family_id=access.birth.family_id,
        birth_id=access.birth.id,
        filename=filename,
    )
    put_object(
        key=key,
        body=content,
        content_type=file.content_type,
    )

    asset = media_repo.create_media_asset(
        db,
        family_id=access.birth.family_id,
        birth_id=access.birth.id,
        uploaded_by_user_id=current_user.id,
        kind=kind,
        original_s3_key=key,
        mime_type=file.content_type,
        bytes_=len(content),
    )

    event_type = {
        MediaKind.photo: TimelineEventType.photo,
        MediaKind.video: TimelineEventType.video,
        MediaKind.voice_memo: TimelineEventType.voice_memo,
    }[kind]
    event_payload = {
        "type": event_type.value,
        "media_id": str(asset.id),
        "caption": caption,
    }
    event = timeline_repo.append_event(
        db,
        birth_id=access.birth.id,
        event_type=event_type,
        payload=event_payload,
        posted_by_user_id=current_user.id,
        occurred_at=occurred_at,
        audience_scope=audience_scope,
    )
    db.commit()
    db.refresh(event)
    await publish_event_change(access.birth.id, "appended", event)
    return serialize_event_out(event)


def _media_visible_to(
    db: Session, asset: MediaAsset, user: User | None
) -> bool:
    """Resolve the audience scopes of every event referencing this asset
    and check whether the requester is allowed to see any of them.

    Anonymous requesters get the public scope only. Authenticated users
    inherit their role on the asset's family (or anonymous-equivalent if
    they have no membership there).
    """
    role: FamilyRole | None = None
    if user is not None:
        membership = db.scalars(
            select(FamilyMembership).where(
                FamilyMembership.family_id == asset.family_id,
                FamilyMembership.user_id == user.id,
            )
        ).first()
        if membership is not None:
            role = membership.role
    visible = births_repo.visible_scopes_for_role(role)

    referencing_scopes = set(
        db.scalars(
            select(TimelineEvent.audience_scope)
            .where(
                TimelineEvent.birth_id == asset.birth_id,
                TimelineEvent.deleted_at.is_(None),
                TimelineEvent.payload["media_id"].astext == str(asset.id),
            )
        ).all()
    )
    if not referencing_scopes:
        # Orphan asset with no event — treat as parent-only, since only
        # the original uploader could possibly need it.
        return role in births_repo.PARENT_ROLES
    return bool(visible & referencing_scopes)


@router.get("/media/{media_id}", response_model=None)
def get_media(
    media_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> FileResponse | RedirectResponse:
    # Viewing is auth-gated: family photos never serve to anonymous
    # requests, whatever their audience scope. `<img>` tags send the
    # same-origin session cookie, so signed-in viewers are unaffected.
    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    asset = media_repo.get_media_asset(db, media_id)
    if asset is None or not asset.is_visible_to_viewers:
        raise HTTPException(status_code=404, detail="Media not found")
    if not _media_visible_to(db, asset, current_user):
        raise HTTPException(status_code=404, detail="Media not found")

    if media_repo.is_local_key(asset.original_s3_key):
        rel = media_repo.local_path(asset.original_s3_key)
        path = (UPLOAD_DIR.parent / rel).resolve()
        upload_root = UPLOAD_DIR.resolve()
        if not path.is_file() or upload_root not in path.parents:
            raise HTTPException(status_code=404, detail="Media file missing")
        media_type = (
            asset.mime_type
            or mimetypes.guess_type(str(path))[0]
            or "application/octet-stream"
        )
        return FileResponse(path, media_type=media_type)

    url = presigned_get_url(asset.original_s3_key)
    return RedirectResponse(url, status_code=307)


# Public marketing assets (landing-page hero video) live in S3 under
# assets/hero-section/ — too heavy for the git repo, no auth required (they
# render on the public landing page). Same presigned-redirect pattern as
# /media. Presigned URLs are cached until shortly before expiry so repeat
# visitors get the same URL and the browser cache can actually hold.
_HERO_ASSET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_hero_asset_url_cache: dict[str, tuple[str, float]] = {}


@router.get("/assets/hero-section/{filename}", response_model=None)
def get_hero_section_asset(filename: str) -> RedirectResponse:
    if not _HERO_ASSET_RE.match(filename):
        raise HTTPException(status_code=404, detail="Asset not found")
    key = f"assets/hero-section/{filename}"
    now = monotonic()
    cached = _hero_asset_url_cache.get(key)
    if cached and cached[1] > now:
        return RedirectResponse(cached[0], status_code=307)
    ttl = int(os.getenv("S3_PRESIGN_TTL_SECONDS", "3600"))
    url = presigned_get_url(key, expires_in=ttl)
    _hero_asset_url_cache[key] = (url, now + max(ttl - 600, 60))
    return RedirectResponse(url, status_code=307)


@router.get("/birth/{birth_id}/export")
def export_birth_data(
    access: BirthAccess = Depends(require_parent_access_stream),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Everything on the page, as one ZIP. Always free — never behind
    any paywall; the data is the family's, full stop.

    Sync `def` on purpose: boto3 and zip-writing block, so FastAPI runs
    this in its threadpool off the event loop. The zip lands in an
    anonymous temp file first (disk cost ≈ media set size), then streams
    out in 1 MiB chunks with a real Content-Length.
    """
    tmp, filename = export_mod.build_export_zip(db, access.birth)
    size = os.fstat(tmp.fileno()).st_size

    def _iter():
        try:
            while chunk := tmp.read(export_mod.EXPORT_CHUNK):
                yield chunk
        finally:
            tmp.close()

    return StreamingResponse(
        _iter(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(size),
            "Cache-Control": "no-store",
        },
    )
