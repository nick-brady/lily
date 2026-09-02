"""Whether the site is alive, and what it has been saying.

`/health` is public: an uptime monitor can be pointed at it with no further
work, and it says nothing a visitor couldn't infer. It answers 503 when the
database can't be reached or the worker hasn't been heard from, so "up"
means the whole thing, not just the web process.

`/admin/logs` is the admin site's Logs page: the last stretch of `app_logs`,
narrowed by level, service, time, and a word in the message.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

import admin as admin_mod
from db import get_db
from models import User
from repositories import app_logs as app_logs_repo
from schemas import AdminLogsOut, AppLogOut, HealthOut, WorkerStatusOut

router = APIRouter()

DEFAULT_WINDOW = timedelta(hours=24)


def _worker_status(db: Session) -> WorkerStatusOut:
    seen_at = app_logs_repo.last_seen(db, "worker")
    return WorkerStatusOut(seen_at=seen_at, ok=app_logs_repo.is_fresh(seen_at))


@router.get("/health", response_model=HealthOut)
def health(response: Response, db: Session = Depends(get_db)) -> HealthOut:
    revision: str | None = None
    db_ok = True
    worker = WorkerStatusOut(seen_at=None, ok=False)
    try:
        revision = db.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        worker = _worker_status(db)
    except Exception:  # noqa: BLE001 - the whole point is to report this
        db_ok = False
    ok = db_ok and worker.ok
    if not ok:
        response.status_code = 503
    return HealthOut(
        status="ok" if ok else "degraded",
        db="ok" if db_ok else "error",
        revision=revision,
        worker=worker,
    )


def _split(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [v.strip().upper() for v in value.split(",") if v.strip()]
    return items or None


@router.get("/admin/logs", response_model=AdminLogsOut)
def admin_logs(
    levels: str | None = Query(None, description="comma-separated, e.g. WARNING,ERROR"),
    services: str | None = Query(None, description="comma-separated, e.g. web,worker"),
    since: datetime | None = None,
    q: str | None = Query(None, max_length=200),
    before: datetime | None = None,
    limit: int = Query(200, ge=1, le=app_logs_repo.MAX_LIMIT),
    admin_user: User = Depends(admin_mod.get_admin_user),
    db: Session = Depends(get_db),
) -> AdminLogsOut:
    """Newest first, last 24 hours by default. The facet counts ignore their
    own facet (levels don't narrow the level counts, services don't narrow
    the service counts) so the sidebar shows what the other choices hold."""
    if since is None:
        since = datetime.now(timezone.utc) - DEFAULT_WINDOW
    level_list = _split(levels)
    service_list = [s.lower() for s in _split(services) or []] or None
    items = app_logs_repo.recent(
        db,
        levels=level_list,
        services=service_list,
        since=since,
        q=q,
        before=before,
        limit=limit,
    )
    return AdminLogsOut(
        since=since,
        items=[AppLogOut.model_validate(row, from_attributes=True) for row in items],
        level_counts=app_logs_repo.counts_by_level(db, since=since, services=service_list, q=q),
        service_counts=app_logs_repo.counts_by_service(db, since=since, levels=level_list, q=q),
        worker=_worker_status(db),
    )
