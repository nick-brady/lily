"""allow one checkout session to carry two gift orders

"Send to the family" and "get one for myself" stop being either/or: a
"both" purchase creates two order rows (the family copy and the self copy)
sharing one Stripe Checkout session with quantity 2. The session / payment
intent uniques on gift_orders assumed 1:1 — relax them to plain indexes.
Everything else (per-copy shipment, claim race, refunds) already works at
the order level.

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-19 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0021"
down_revision: Union[str, Sequence[str], None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "gift_orders_stripe_checkout_session_id_key", "gift_orders", type_="unique"
    )
    op.drop_constraint(
        "gift_orders_stripe_payment_intent_id_key", "gift_orders", type_="unique"
    )
    op.create_index(
        "ix_gift_orders_stripe_checkout_session_id",
        "gift_orders",
        ["stripe_checkout_session_id"],
    )
    op.create_index(
        "ix_gift_orders_stripe_payment_intent_id",
        "gift_orders",
        ["stripe_payment_intent_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_gift_orders_stripe_payment_intent_id", table_name="gift_orders")
    op.drop_index("ix_gift_orders_stripe_checkout_session_id", table_name="gift_orders")
    op.create_unique_constraint(
        "gift_orders_stripe_payment_intent_id_key",
        "gift_orders",
        ["stripe_payment_intent_id"],
    )
    op.create_unique_constraint(
        "gift_orders_stripe_checkout_session_id_key",
        "gift_orders",
        ["stripe_checkout_session_id"],
    )
