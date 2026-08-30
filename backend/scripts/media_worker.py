"""Make the smaller copies of uploaded photos, out of the request's way.

An upload writes the original and returns. This picks the photo up a moment
later and writes a 1600px display copy and a 320px thumbnail beside it, so
the browser stops downloading a 4000px photo to draw a 57px tile.

    docker compose exec backend python scripts/media_worker.py
    docker compose up -d worker                       # dev, as a service
    systemctl status lily-worker                      # prod

It claims one photo at a time with SKIP LOCKED, so a second copy can be
started alongside without the two colliding. Nothing here is urgent: if the
worker is stopped, every reader keeps serving the original, and the backlog
is picked up whenever it comes back.
"""
from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import image_variants  # noqa: E402
from db import SessionLocal  # noqa: E402
from repositories import media as media_repo  # noqa: E402

IDLE_SLEEP_SECONDS = 5.0
# A photo that fails for a reason that isn't the file itself — S3 down, say —
# shouldn't be retired. The claim is simply left to go stale and be retried.
logger = logging.getLogger("media_worker")

_stop = False


def _handle_stop(signum, _frame) -> None:
    """Finish the photo in hand, then stop. A deploy restart shouldn't leave
    a half-written set of variants behind."""
    global _stop
    _stop = True
    logger.info("signal %s — finishing the current photo, then stopping", signum)


def process_one(db) -> bool:
    """One photo, if there is one waiting. True if work was done."""
    asset = media_repo.claim_for_variants(db)
    if asset is None:
        return False
    try:
        stored = media_repo.build_variants(db, asset)
    except image_variants.UnreadableImage as exc:
        # the file itself is the problem; trying again would fail the same way
        db.rollback()
        media_repo.record_variant_failure(db, asset, f"unreadable: {exc}")
        logger.warning("media %s is not a readable image: %s", asset.id, exc)
        return True
    except Exception as exc:  # noqa: BLE001 - the loop must outlive any photo
        # something transient (S3, the network). Leave the claim to go stale
        # and be picked up again rather than retiring the row.
        db.rollback()
        logger.exception("media %s failed: %s", asset.id, exc)
        return True
    logger.info("media %s -> %s", asset.id, ", ".join(sorted(stored)))
    return True


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    logger.info("media worker started")
    db = SessionLocal()
    try:
        while not _stop:
            try:
                did_work = process_one(db)
            except Exception:  # noqa: BLE001 - a broken session must not end the loop
                logger.exception("worker loop error")
                db.rollback()
                did_work = False
            if not did_work:
                # sleep in slices so a stop signal doesn't wait out the idle
                for _ in range(int(IDLE_SLEEP_SECONDS * 10)):
                    if _stop:
                        break
                    time.sleep(0.1)
    finally:
        db.close()
        logger.info("media worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
