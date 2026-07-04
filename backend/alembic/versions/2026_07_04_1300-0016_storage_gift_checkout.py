"""storage gift checkout

The $15/5-year storage gift was in the catalog but had no working buy
path: `gift_orders.gift_rendering_id` was NOT NULL, yet storage gifts
never get a rendering (there's no artwork to render). Make the column
nullable so a storage-gift order can exist without one.

Also adds `births.storage_paid_until` — the durable record of what a
storage gift actually bought. Extended (never shortened) each time a
storage-gift order is fulfilled, by `storage_years_granted` years from
the later of "now" and the current value, so stacking gifts from
multiple grandparents adds up instead of overwriting.

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-04 13:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0016"
down_revision: Union[str, Sequence[str], None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "gift_orders",
        "gift_rendering_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        "births",
        sa.Column("storage_paid_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("births", "storage_paid_until")
    op.alter_column(
        "gift_orders",
        "gift_rendering_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
