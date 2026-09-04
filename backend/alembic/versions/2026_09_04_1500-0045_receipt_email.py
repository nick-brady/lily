"""the buyer's email and whether their receipt has gone

Arrival Story sends its own order confirmation now, once per order, keyed
here so the webhook and the browser's confirm call can't both send it. The
buyer's address comes from Stripe's checkout session (a phone-only account
has none of its own) and is kept on the order for this purpose only.

Revision ID: 0045
Revises: 0044
Create Date: 2026-09-04 15:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0045"
down_revision: Union[str, Sequence[str], None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gift_orders", sa.Column("buyer_email", sa.Text(), nullable=True))
    op.add_column(
        "gift_orders",
        sa.Column("receipt_emailed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gift_orders", "receipt_emailed_at")
    op.drop_column("gift_orders", "buyer_email")
