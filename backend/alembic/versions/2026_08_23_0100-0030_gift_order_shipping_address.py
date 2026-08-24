"""where this copy of the gift is going

Until now a gift's destination was resolved after payment: the family copy
took `births.shipping_address` if the parents had saved one, and everything
else took whatever address Stripe collected on its hosted page. That worked
for one parcel and only one — Stripe Checkout collects exactly one shipping
address per session — so buying a copy for the family and a copy for yourself
in a single payment was refused unless the parents had already saved theirs.

The address was never Stripe's to hold. Printful needs a destination; Stripe
was only a convenient form to collect one in. So the buyer names the
destination in our own form and it rides on the order.

NULL keeps the old resolution, which is what a checkout session started before
this migration and paid after it needs.

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-23 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0030"
down_revision: Union[str, Sequence[str], None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_orders", sa.Column("shipping_address", JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("gift_orders", "shipping_address")
