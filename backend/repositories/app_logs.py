"""Reads and writes for `app_logs` and `service_heartbeats`.

`insert_many` is the sink behind the logging queue: it opens its own short
transaction on the engine, never a request's session, so a batch of log
rows borrows a pooled connection for milliseconds and hands it back. The
reads are what the admin Logs page asks for; the sweep and the heartbeat
belong to the worker's idle loop.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from db import engine
from models import AppLog, ServiceHeartbeat

LEVELS = ("INFO", "WARNING", "ERROR", "CRITICAL")
RETENTION_DAYS = 30
MAX_LIMIT = 500
# The worker beats every 30s; twice that plus slack before /health calls it stale.
WORKER_STALE_AFTER = timedelta(seconds=120)


def insert_many(rows: list[dict]) -> None:
    if not rows:
        return
    with engine.begin() as conn:
        conn.execute(sa.insert(AppLog), rows)


def _where(*, since: datetime | None, services: list[str] | None, q: str | None):
    clauses = []
    if since is not None:
        clauses.append(AppLog.logged_at >= since)
    if services:
        clauses.append(AppLog.service.in_(services))
    if q:
        clauses.append(AppLog.message.ilike(f"%{q}%"))
    return clauses


def recent(
    db: Session,
    *,
    levels: list[str] | None,
    services: list[str] | None,
    since: datetime | None,
    q: str | None,
    before: datetime | None,
    limit: int,
) -> list[AppLog]:
    """Newest first. `before` is the `logged_at` of the oldest row already
    shown, for paging further back."""
    stmt = sa.select(AppLog).where(*_where(since=since, services=services, q=q))
    if levels:
        stmt = stmt.where(AppLog.level.in_(levels))
    if before is not None:
        stmt = stmt.where(AppLog.logged_at < before)
    stmt = stmt.order_by(AppLog.logged_at.desc()).limit(min(max(limit, 1), MAX_LIMIT))
    return list(db.scalars(stmt))


def counts_by_level(
    db: Session, *, since: datetime | None, services: list[str] | None, q: str | None
) -> dict[str, int]:
    stmt = (
        sa.select(AppLog.level, sa.func.count())
        .where(*_where(since=since, services=services, q=q))
        .group_by(AppLog.level)
    )
    counts = {level: 0 for level in LEVELS}
    for level, n in db.execute(stmt):
        counts[level] = counts.get(level, 0) + n
    return counts


def counts_by_service(
    db: Session, *, since: datetime | None, levels: list[str] | None, q: str | None
) -> dict[str, int]:
    stmt = (
        sa.select(AppLog.service, sa.func.count())
        .where(*_where(since=since, services=None, q=q))
        .group_by(AppLog.service)
    )
    if levels:
        stmt = stmt.where(AppLog.level.in_(levels))
    return {service: n for service, n in db.execute(stmt)}


def sweep(db: Session, *, older_than_days: int = RETENTION_DAYS) -> int:
    """Delete rows past retention. Returns how many went."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    result = db.execute(sa.delete(AppLog).where(AppLog.logged_at < cutoff))
    db.commit()
    return result.rowcount or 0


def beat(db: Session, service: str, detail: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    stmt = pg_insert(ServiceHeartbeat).values(service=service, seen_at=now, detail=detail)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ServiceHeartbeat.service],
        set_={"seen_at": now, "detail": detail},
    )
    db.execute(stmt)
    db.commit()


def last_seen(db: Session, service: str) -> datetime | None:
    row = db.get(ServiceHeartbeat, service)
    return row.seen_at if row else None


def is_fresh(seen_at: datetime | None, now: datetime | None = None) -> bool:
    if seen_at is None:
        return False
    return (now or datetime.now(timezone.utc)) - seen_at <= WORKER_STALE_AFTER
