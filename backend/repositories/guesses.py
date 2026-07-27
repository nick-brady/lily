"""The family pool: guesses at the baby's weight/length.

Free-tier engagement (like reactions, unlike comments): any signed-in
viewer can guess, one guess per user per birth, editable until the baby is
born. Name-only rows (user_id NULL) come from imports or parent-entered
guesses for relatives without accounts.

This module also owns the ONE scoring implementation — the leaderboard
routes and the pool gift artwork both call `score()`, so the ranking on the
card and the ranking on the page can't drift apart.
"""
from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models import Birth, BirthGuess, User


def score(
    weight_lbs: float | None,
    length_in: float | None,
    *,
    actual_weight_lbs: float,
    actual_length_in: float | None,
) -> float | None:
    """Closeness score — lower wins. Mirrors the original Predictions.jsx:
    |weight diff in lbs| + 0.5 × |length diff in inches|. A guess that named
    nothing scores None (sinks to the bottom, never disappears)."""
    total = 0.0
    scored = False
    if weight_lbs:
        total += abs(weight_lbs - actual_weight_lbs)
        scored = True
    if length_in and actual_length_in:
        total += abs(length_in - actual_length_in) * 0.5
        scored = True
    return total if scored else None


def list_guesses(db: Session, *, birth_id: uuid.UUID) -> list[BirthGuess]:
    return list(
        db.scalars(
            select(BirthGuess)
            .where(BirthGuess.birth_id == birth_id)
            .order_by(BirthGuess.created_at.asc())
        ).all()
    )


def get_own_guess(
    db: Session, *, birth_id: uuid.UUID, user_id: uuid.UUID
) -> BirthGuess | None:
    return db.scalar(
        select(BirthGuess).where(
            BirthGuess.birth_id == birth_id, BirthGuess.user_id == user_id
        )
    )


# Sentinel for "the caller didn't send this field": distinct from None so a
# mid-labor resubmit that omits date_guess (the form hides the closed field)
# preserves the date already on record instead of nulling it.
UNSET: object = object()


def upsert_guess(
    db: Session,
    *,
    birth: Birth,
    user: User,
    weight_lbs: float | None,
    length_in: float | None,
    sex_guess: str | None | object = UNSET,
    date_guess: dt.date | None | object = UNSET,
) -> BirthGuess:
    """Create or update the user's guess for this birth. The partial unique
    index on (birth_id, user_id) WHERE user_id IS NOT NULL makes concurrent
    submits safe; display_name is re-snapshotted on every write. Fields left
    UNSET keep whatever the row already holds."""
    values = {
        "birth_id": birth.id,
        "user_id": user.id,
        "display_name": user.display_name,
        "weight_lbs": weight_lbs,
        "length_in": length_in,
    }
    updates = {
        "display_name": user.display_name,
        "weight_lbs": weight_lbs,
        "length_in": length_in,
        "updated_at": sa.func.now(),
    }
    if sex_guess is not UNSET:
        values["sex_guess"] = sex_guess
        updates["sex_guess"] = sex_guess
    if date_guess is not UNSET:
        values["date_guess"] = date_guess
        updates["date_guess"] = date_guess

    stmt = (
        pg_insert(BirthGuess)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["birth_id", "user_id"],
            index_where=BirthGuess.user_id.isnot(None),
            set_=updates,
        )
    )
    db.execute(stmt)
    db.commit()
    return get_own_guess(db, birth_id=birth.id, user_id=user.id)
