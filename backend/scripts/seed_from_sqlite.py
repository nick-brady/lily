"""One-shot seed from the legacy SQLite file into Postgres.

Usage (inside the running compose stack):

    docker compose cp backend/contractions-prod.db backend:/tmp/seed.db
    docker compose exec -e SQLITE_PATH=/tmp/seed.db backend python scripts/seed_from_sqlite.py

Idempotent: refuses to run if the target tables already have rows.
Preserves original IDs and resets the Postgres sequences to MAX(id).
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# Make the parent (backend) importable when run as `python scripts/seed_from_sqlite.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, text

from db import SessionLocal
from models import Contraction, Update


SQLITE_PATH = os.environ.get("SQLITE_PATH", "contractions-prod.db")


def main() -> int:
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite file not found: {SQLITE_PATH}", file=sys.stderr)
        return 1

    src = sqlite3.connect(SQLITE_PATH)
    src.row_factory = sqlite3.Row

    with SessionLocal() as session:
        existing_contractions = session.scalar(select(func.count()).select_from(Contraction))
        existing_updates = session.scalar(select(func.count()).select_from(Update))
        if existing_contractions or existing_updates:
            print(
                f"Refusing to seed: target already has "
                f"{existing_contractions} contractions and {existing_updates} updates.",
                file=sys.stderr,
            )
            return 2

        contractions = src.execute(
            "SELECT id, start_time, end_time, duration_seconds, "
            "COALESCE(ignore_interval_before, 0) AS ignore_interval_before "
            "FROM contractions ORDER BY id"
        ).fetchall()
        for row in contractions:
            session.add(Contraction(
                id=row["id"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                duration_seconds=row["duration_seconds"],
                ignore_interval_before=bool(row["ignore_interval_before"]),
            ))

        updates = src.execute(
            "SELECT id, timestamp, type, content, photo_filename, "
            "audio_filename, milestone FROM updates ORDER BY id"
        ).fetchall()
        for row in updates:
            session.add(Update(
                id=row["id"],
                timestamp=row["timestamp"],
                type=row["type"],
                content=row["content"],
                photo_filename=row["photo_filename"],
                audio_filename=row["audio_filename"],
                milestone=row["milestone"],
            ))

        session.flush()

        # Reset SERIAL sequences so future inserts don't collide with seeded IDs.
        session.execute(text(
            "SELECT setval(pg_get_serial_sequence('contractions', 'id'), "
            "COALESCE(MAX(id), 1)) FROM contractions"
        ))
        session.execute(text(
            "SELECT setval(pg_get_serial_sequence('updates', 'id'), "
            "COALESCE(MAX(id), 1)) FROM updates"
        ))

        session.commit()

    src.close()
    print(f"Seeded {len(contractions)} contractions and {len(updates)} updates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
