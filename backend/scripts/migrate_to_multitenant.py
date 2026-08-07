"""Move the legacy `contractions` + `updates` tables into the new
multi-tenant model.

Runs AFTER alembic 0002 (which created the new tables) and BEFORE
alembic 0003 (which drops the legacy tables).

Usage:

    docker compose exec backend python scripts/migrate_to_multitenant.py

Behaviour:
- Refuses to run if any `families` row already exists (idempotency guard).
- Dumps every legacy row to /tmp/lily_legacy_backup_<timestamp>.json
  before writing anything.
- Seeds the Brady family + a `births` row for Lily Wren.
- Converts contractions and updates into `timeline_events` (and
  `media_assets` for photo/audio rows).
- Best-effort: any row that can't be mapped is skipped and logged.
- All inside one transaction; partial failure rolls back cleanly.

Env vars (optional):
    SEED_OWNER_EMAIL, SEED_OWNER_PHONE, SEED_OWNER_NAME
    SEED_COPARENT_EMAIL, SEED_COPARENT_PHONE, SEED_COPARENT_NAME
    BIRTH_SLUG (default "lily-wren")
    CHILD_NAME (default "Lily Wren")
    FAMILY_DISPLAY_NAME (default "The Brady Family")
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import session_scope  # noqa: E402
from models import (  # noqa: E402
    AudienceScope,
    AuthIdentifierKind,
    Birth,
    BirthStatus,
    Family,
    FamilyRole,
    MediaKind,
    TimelineEvent,
    TimelineEventType,
    User,
)
from repositories import births as births_repo  # noqa: E402
from repositories import families as families_repo  # noqa: E402
from repositories import media as media_repo  # noqa: E402
from repositories import timeline as timeline_repo  # noqa: E402


SEED_OWNER_EMAIL = os.environ.get("SEED_OWNER_EMAIL") or "nick@example.com"
SEED_OWNER_PHONE = os.environ.get("SEED_OWNER_PHONE")
SEED_OWNER_NAME = os.environ.get("SEED_OWNER_NAME") or "Nick"

SEED_COPARENT_EMAIL = os.environ.get("SEED_COPARENT_EMAIL") or "alexis@example.com"
SEED_COPARENT_PHONE = os.environ.get("SEED_COPARENT_PHONE")
SEED_COPARENT_NAME = os.environ.get("SEED_COPARENT_NAME") or "Alexis"

FAMILY_DISPLAY_NAME = os.environ.get("FAMILY_DISPLAY_NAME") or "The Brady Family"
BIRTH_SLUG = os.environ.get("BIRTH_SLUG") or "lily-wren"
CHILD_NAME = os.environ.get("CHILD_NAME") or "Lily Wren"

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
BACKUP_DIR = Path("/tmp")


@dataclass
class Summary:
    contractions_migrated: int = 0
    updates_migrated: int = 0
    media_assets_created: int = 0
    skipped: list[str] = field(default_factory=list)


def _parse_ts(value: str | None) -> datetime | None:
    if value is None:
        return None
    raw = value.rstrip("Z")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _backup_legacy(conn) -> Path:
    contractions = [
        dict(row._mapping)
        for row in conn.execute(text("SELECT * FROM contractions ORDER BY id"))
    ]
    updates = [
        dict(row._mapping)
        for row in conn.execute(text("SELECT * FROM updates ORDER BY id"))
    ]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"lily_legacy_backup_{timestamp}.json"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "contractions": contractions,
        "updates": updates,
    }
    path.write_text(json.dumps(payload, default=str, indent=2))
    print(f"Wrote legacy backup to {path}")
    return path


def _refuse_if_already_migrated(db) -> None:
    existing = db.scalar(select(func.count()).select_from(Family))
    if existing:
        print(
            f"Refusing to run: {existing} family row(s) already present. "
            f"The new model is initialized — running this script again would "
            f"duplicate data.",
            file=sys.stderr,
        )
        sys.exit(2)


def _legacy_tables_present(conn) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name IN ('contractions','updates')"
        )
    ).scalar()
    return int(row or 0) == 2


def _seed_user(db, *, email: str | None, phone: str | None, name: str) -> User:
    if email:
        existing = db.scalars(select(User).where(User.email == email)).first()
    elif phone:
        existing = db.scalars(select(User).where(User.phone == phone)).first()
    else:
        existing = None
    if existing:
        if not existing.display_name:
            existing.display_name = name
        return existing
    user = User(email=email, phone=phone, display_name=name)
    db.add(user)
    db.flush()
    return user


def _milestone_kind_signals_birth_complete(milestone: str) -> bool:
    """The Lily Wren data uses `born` as the canonical 'baby arrived'
    milestone. We deliberately accept anything containing 'born' but not
    'water_broke' — `water_broke` doesn't contain the substring 'born'.
    """
    return "born" in milestone.lower() and "broke" not in milestone.lower()


def _migrate_contractions(db, conn, birth: Birth, owner: User, summary: Summary) -> None:
    rows = list(
        conn.execute(
            text(
                "SELECT id, start_time, end_time, duration_seconds, "
                "       COALESCE(ignore_interval_before, false) AS ignore_interval_before "
                "FROM contractions ORDER BY start_time, id"
            )
        )
    )
    previous_occurred_at: datetime | None = None
    sequence = 0
    for row in rows:
        start_time = _parse_ts(row.start_time)
        if start_time is None:
            summary.skipped.append(
                f"contraction id={row.id} (could not parse start_time={row.start_time!r})"
            )
            continue

        end_time = _parse_ts(row.end_time) if row.end_time else None
        duration_seconds = row.duration_seconds
        gap = (
            int((start_time - previous_occurred_at).total_seconds())
            if previous_occurred_at is not None
            else None
        )

        sequence += 1
        timeline_repo.append_event(
            db,
            birth_id=birth.id,
            event_type=TimelineEventType.contraction,
            payload={
                "type": "contraction",
                "duration_seconds": duration_seconds,
                "end_time": end_time.isoformat() if end_time else None,
                "gap_before_seconds": gap,
                "ignore_interval_before": bool(row.ignore_interval_before),
            },
            posted_by_user_id=owner.id,
            occurred_at=start_time,
            audience_scope=AudienceScope.group_targeted,
            sequence_id=sequence,
        )
        summary.contractions_migrated += 1
        previous_occurred_at = start_time


def _migrate_updates(db, conn, birth: Birth, owner: User, summary: Summary) -> None:
    rows = list(
        conn.execute(
            text(
                "SELECT id, timestamp, type, content, photo_filename, "
                "       audio_filename, milestone "
                "FROM updates ORDER BY timestamp, id"
            )
        )
    )
    starting_sequence = db.scalar(
        select(func.coalesce(func.max(TimelineEvent.sequence_id), 0)).where(
            TimelineEvent.birth_id == birth.id
        )
    )
    sequence = int(starting_sequence)

    for row in rows:
        occurred_at = _parse_ts(row.timestamp)
        if occurred_at is None:
            summary.skipped.append(
                f"update id={row.id} (could not parse timestamp={row.timestamp!r})"
            )
            continue

        kind = (row.type or "").strip().lower()
        if kind == "note":
            if not row.content:
                summary.skipped.append(f"update id={row.id} (note with empty content)")
                continue
            sequence += 1
            timeline_repo.append_event(
                db,
                birth_id=birth.id,
                event_type=TimelineEventType.text_note,
                payload={"type": "text_note", "body": row.content},
                posted_by_user_id=owner.id,
                occurred_at=occurred_at,
                audience_scope=AudienceScope.group_targeted,
                sequence_id=sequence,
            )
            summary.updates_migrated += 1

        elif kind == "milestone":
            milestone_kind = (row.milestone or "").strip() or "unknown"
            sequence += 1
            timeline_repo.append_event(
                db,
                birth_id=birth.id,
                event_type=TimelineEventType.milestone,
                payload={
                    "type": "milestone",
                    "kind": milestone_kind,
                    "title": None,
                    "body": row.content,
                },
                posted_by_user_id=owner.id,
                occurred_at=occurred_at,
                audience_scope=AudienceScope.group_targeted,
                sequence_id=sequence,
            )
            summary.updates_migrated += 1

        elif kind in ("photo", "audio"):
            filename = row.photo_filename if kind == "photo" else row.audio_filename
            if not filename:
                summary.skipped.append(
                    f"update id={row.id} ({kind} with null filename)"
                )
                continue
            if not (UPLOAD_DIR / filename).exists():
                summary.skipped.append(
                    f"update id={row.id} ({kind} file not found: {filename})"
                )
                continue

            media_kind = MediaKind.photo if kind == "photo" else MediaKind.voice_memo
            event_type = (
                TimelineEventType.photo
                if kind == "photo"
                else TimelineEventType.voice_memo
            )
            asset = media_repo.create_media_asset(
                db,
                family_id=birth.family_id,
                birth_id=birth.id,
                uploaded_by_user_id=owner.id,
                kind=media_kind,
                original_s3_key=media_repo.local_key(filename),
                bytes_=(UPLOAD_DIR / filename).stat().st_size,
            )
            summary.media_assets_created += 1

            sequence += 1
            payload: dict = {
                "type": event_type.value,
                "media_id": str(asset.id),
                "caption": row.content,
            }
            timeline_repo.append_event(
                db,
                birth_id=birth.id,
                event_type=event_type,
                payload=payload,
                posted_by_user_id=owner.id,
                occurred_at=occurred_at,
                audience_scope=AudienceScope.group_targeted,
                sequence_id=sequence,
            )
            summary.updates_migrated += 1

        else:
            summary.skipped.append(f"update id={row.id} (unknown type={row.type!r})")


def _determine_birth_endpoints(conn) -> tuple[datetime | None, datetime | None]:
    started_at_row = conn.execute(
        text("SELECT MIN(start_time) FROM contractions")
    ).scalar()
    birth_started_at = _parse_ts(started_at_row) if started_at_row else None

    completed_rows = conn.execute(
        text(
            "SELECT timestamp, milestone FROM updates "
            "WHERE type = 'milestone' AND milestone IS NOT NULL "
            "ORDER BY timestamp ASC"
        )
    ).fetchall()
    birth_completed_at: datetime | None = None
    for row in completed_rows:
        if _milestone_kind_signals_birth_complete(row.milestone):
            birth_completed_at = _parse_ts(row.timestamp)
            break

    return birth_started_at, birth_completed_at


def main() -> int:
    with session_scope() as db:
        conn = db.connection()

        if not _legacy_tables_present(conn):
            print(
                "Legacy `contractions`/`updates` tables not present. Nothing to migrate.",
                file=sys.stderr,
            )
            return 1

        _refuse_if_already_migrated(db)
        _backup_legacy(conn)

        owner = _seed_user(
            db, email=SEED_OWNER_EMAIL, phone=SEED_OWNER_PHONE, name=SEED_OWNER_NAME
        )
        coparent = _seed_user(
            db,
            email=SEED_COPARENT_EMAIL,
            phone=SEED_COPARENT_PHONE,
            name=SEED_COPARENT_NAME,
        )

        family = families_repo.create_family(
            db,
            display_name=FAMILY_DISPLAY_NAME,
            primary_owner_user_id=owner.id,
        )
        families_repo.add_member(
            db, family_id=family.id, user_id=owner.id, role=FamilyRole.owner
        )
        families_repo.add_member(
            db,
            family_id=family.id,
            user_id=coparent.id,
            role=FamilyRole.co_parent,
        )

        birth_started_at, birth_completed_at = _determine_birth_endpoints(conn)
        status = BirthStatus.born if birth_completed_at else BirthStatus.in_labor
        if birth_started_at is None:
            status = BirthStatus.preparing

        birth = births_repo.create_birth(
            db,
            family_id=family.id,
            child_name=CHILD_NAME,
            slug=BIRTH_SLUG,
            status=status,
            birth_started_at=birth_started_at,
            birth_completed_at=birth_completed_at,
        )

        summary = Summary()
        _migrate_contractions(db, conn, birth, owner, summary)
        _migrate_updates(db, conn, birth, owner, summary)

        print()
        print("=" * 60)
        print(f"Family:       {family.display_name} ({family.id})")
        print(f"Owner:        {owner.email or owner.phone} ({owner.id})")
        print(f"Co-parent:    {coparent.email or coparent.phone} ({coparent.id})")
        print(f"Birth:        {birth.child_name} slug={birth.slug} status={birth.status.value}")
        print(f"  Started:    {birth.birth_started_at}")
        print(f"  Completed:  {birth.birth_completed_at}")
        print(
            f"Migrated:     {summary.contractions_migrated} contractions, "
            f"{summary.updates_migrated} updates, "
            f"{summary.media_assets_created} media assets"
        )
        if summary.skipped:
            print(f"Skipped:      {len(summary.skipped)} rows")
            for line in summary.skipped:
                print(f"  - {line}")
        else:
            print("Skipped:      0 rows")
        print("=" * 60)
        print()
        print("Now run `alembic upgrade head` to drop the legacy tables.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
