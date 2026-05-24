"""Flip `is_unlocked` to true on a birth so comments can be posted.

In production this happens when someone pays $12 via Stripe (lands in
PR 5). For dev/test it's useful to set the flag manually so the comment
experience can be exercised end-to-end before payments are wired up.

Usage:

    docker compose exec backend python scripts/unlock_birth.py <slug>

The flag is global to the birth — once set, every family member and
every authed viewer can comment on it. Matches the spec model: "anyone
in the family can unlock the comments for everyone — $12, one time."
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal  # noqa: E402
from repositories import births as births_repo  # noqa: E402


def main(slug: str) -> int:
    db = SessionLocal()
    try:
        birth = births_repo.get_birth_by_slug(db, slug)
        if birth is None:
            print(f"No birth found with slug={slug!r}", file=sys.stderr)
            return 1
        if birth.is_unlocked:
            print(f"Birth {slug!r} is already unlocked.")
            return 0
        birth.is_unlocked = True
        birth.unlocked_at = datetime.now(timezone.utc)
        db.commit()
        print(f"Unlocked birth {slug!r} ({birth.id}).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
