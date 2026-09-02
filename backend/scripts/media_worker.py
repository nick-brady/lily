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

Being the one long-running process, it also does the housekeeping: a
heartbeat row every thirty seconds so `/health` can say it's alive, and an
hourly sweep of `app_logs` past its thirty-day retention.
"""
from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import image_variants  # noqa: E402
import observability  # noqa: E402
from db import SessionLocal  # noqa: E402
from repositories import app_logs as app_logs_repo  # noqa: E402
from repositories import media as media_repo  # noqa: E402

IDLE_SLEEP_SECONDS = 5.0
HEARTBEAT_SECONDS = 30.0
SWEEP_SECONDS = 3600.0
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


class Housekeeping:
    """The heartbeat and the sweep, each on its own clock. Neither may end
    the loop: a failure is logged, the session rolled back, and the next
    tick tries again."""

    def __init__(self) -> None:
        self.last_beat = 0.0
        self.last_sweep = 0.0

    def tick(self, db, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if now - self.last_beat >= HEARTBEAT_SECONDS:
            self.last_beat = now
            self._safely(db, lambda: app_logs_repo.beat(db, observability.WORKER))
        if now - self.last_sweep >= SWEEP_SECONDS:
            self.last_sweep = now
            self._safely(db, lambda: self._sweep(db))

    @staticmethod
    def _sweep(db) -> None:
        removed = app_logs_repo.sweep(db)
        if removed:
            logger.info("swept %d log rows older than %d days", removed, app_logs_repo.RETENTION_DAYS)

    @staticmethod
    def _safely(db, action) -> None:
        try:
            action()
        except Exception:  # noqa: BLE001 - housekeeping must not end the loop
            logger.exception("housekeeping failed")
            db.rollback()


def main() -> int:
    observability.configure_logging(observability.WORKER)
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    logger.info("media worker started")
    housekeeping = Housekeeping()
    db = SessionLocal()
    try:
        while not _stop:
            housekeeping.tick(db)
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
        observability.shutdown_logging()
    return 0


if __name__ == "__main__":
    sys.exit(main())
