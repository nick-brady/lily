"""what the printer tells us after the draft: shipped, and how to follow it

Printful's webhooks say when a parcel ships (carrier, tracking number, URL)
and when an order fails, is canceled or put on hold. Until now none of that
reached us — a shipped mug looked exactly like one still on the press, and a
failure sat only in Printful's dashboard.

Revision ID: 0046
Revises: 0045
Create Date: 2026-09-04 17:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0046"
down_revision: Union[str, Sequence[str], None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gift_shipments", sa.Column("carrier", sa.Text(), nullable=True))
    op.add_column("gift_shipments", sa.Column("tracking_number", sa.Text(), nullable=True))
    op.add_column("gift_shipments", sa.Column("tracking_url", sa.Text(), nullable=True))
    op.add_column("gift_shipments", sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gift_shipments", sa.Column("shipped_emailed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for col in ("shipped_emailed_at", "shipped_at", "tracking_url", "tracking_number", "carrier"):
        op.drop_column("gift_shipments", col)
