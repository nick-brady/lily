"""The $12 family unlock — idempotent fulfillment.

Only the database lives here; the Stripe calls (and the decision to refund
a losing payment) belong to the caller. UNIQUE(birth_id) on
unlock_purchases is the whole race story: under READ COMMITTED a losing
concurrent INSERT blocks on the winner's uncommitted unique-index entry,
then raises IntegrityError once the winner commits — so the post-rollback
re-select always sees the winner's row.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Birth, UnlockPurchase

FulfillOutcome = Literal["unlocked", "already_same_intent", "already_other_intent"]


def fulfill_purchase(
    db: Session,
    *,
    birth_id: uuid.UUID,
    user_id: uuid.UUID | None,
    payment_intent_id: str,
    checkout_session_id: str | None,
    amount_cents: int,
    currency: str,
) -> tuple[FulfillOutcome, Birth]:
    """Record the purchase and flip the birth's unlock flags. Outcomes:

    - "unlocked": this payment won; flags flipped and committed.
    - "already_same_intent": duplicate delivery of the winner (webhook
      redelivery, or webhook + redirect-confirm for the same session) — no-op.
    - "already_other_intent": a different payment already won; nothing is
      recorded (per spec) and the caller refunds this one.
    """
    birth = db.get(Birth, birth_id)
    if birth is None:
        raise LookupError(f"no birth {birth_id}")

    try:
        db.add(
            UnlockPurchase(
                birth_id=birth_id,
                purchased_by_user_id=user_id,
                amount_cents=amount_cents,
                currency=currency,
                stripe_payment_intent_id=payment_intent_id,
                stripe_checkout_session_id=checkout_session_id,
            )
        )
        db.flush()
        if not birth.is_unlocked:  # keep a CLI-set unlocked_at if one exists
            birth.is_unlocked = True
            birth.unlocked_at = datetime.now(timezone.utc)
            birth.unlocked_by_user_id = user_id
        db.commit()
        return "unlocked", birth
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(UnlockPurchase).where(UnlockPurchase.birth_id == birth_id)
        )
        if (
            existing is not None
            and existing.stripe_payment_intent_id == payment_intent_id
        ):
            return "already_same_intent", birth
        return "already_other_intent", birth
