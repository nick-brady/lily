"""what an order cost, beside what it charged

The first real order (test mode) charged $24.69. Printful quoted $13.69 to
make and post it and Stripe kept $1.02 — and neither number was stored, so
the dashboard called the whole $24.69 revenue. Prices split into product and
postage on the order; Printful's costs land on the shipment when the draft is
created; Stripe's fee lands on the order when the payment is confirmed.

Revision ID: 0044
Revises: 0043
Create Date: 2026-09-03 22:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0044"
down_revision: Union[str, Sequence[str], None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gift_orders", sa.Column("product_price_cents", sa.Integer(), nullable=True))
    op.add_column("gift_orders", sa.Column("payment_fee_cents", sa.Integer(), nullable=True))
    # every existing order was priced as item + postage, so the split is exact
    op.execute("UPDATE gift_orders SET product_price_cents = amount_cents - shipping_cents")

    op.add_column("gift_shipments", sa.Column("product_cost_cents", sa.Integer(), nullable=True))
    op.add_column("gift_shipments", sa.Column("shipping_cost_cents", sa.Integer(), nullable=True))
    op.add_column("gift_shipments", sa.Column("tax_cost_cents", sa.Integer(), nullable=True))
    op.add_column("gift_shipments", sa.Column("total_cost_cents", sa.Integer(), nullable=True))
    op.add_column(
        "gift_shipments",
        sa.Column("costs_recorded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for col in ("costs_recorded_at", "total_cost_cents", "tax_cost_cents", "shipping_cost_cents", "product_cost_cents"):
        op.drop_column("gift_shipments", col)
    op.drop_column("gift_orders", "payment_fee_cents")
    op.drop_column("gift_orders", "product_price_cents")
