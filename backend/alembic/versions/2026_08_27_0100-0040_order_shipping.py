"""postage, charged and recorded on the order

Printful bills us shipping on every parcel and until now nobody paid it — the
prices carried one parcel's worth, and a purchase to two addresses lost the
second. Each order now records the postage quoted for its own address, and
whether that was the partner's live rate or our flat stand-in. Old orders read
zero: they were never charged it.

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-27 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0040"
down_revision: Union[str, Sequence[str], None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gift_orders", sa.Column("shipping_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("gift_orders", sa.Column("shipping_estimated", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("gift_orders", "shipping_estimated")
    op.drop_column("gift_orders", "shipping_cents")
