"""gift orders + shipments + family shipping address

The purchase path for physical gifts. `gift_orders` records who bought which
design for whom; the partial unique index is the registry claim — one
family-bound *paid* purchase per catalog item per birth (self copies don't
count, pending checkouts don't block anyone). `gift_shipments` is separate
from orders even though this phase is one shipment per order, because the
spec's "and one for me / Both" mechanic (one payment, two shipments) is a
near-term follow-up.

`births.shipping_address` is the parent-saved destination for family-bound
gifts (never exposed on the public birth payload); when unset, Stripe
Checkout collects an address from the buyer instead.

Also fixes the seeded fulfillment partner for physical items: the live
adapter is Printful, not Gelato.

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-03 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0015"
down_revision: Union[str, Sequence[str], None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gift_orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "birth_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("births.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "gift_catalog_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gift_catalog_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "gift_rendering_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gift_renderings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "purchased_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("recipient_kind", sa.Text, nullable=False),
        sa.Column("gift_message", sa.Text, nullable=True),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.Text, nullable=False, server_default="usd"),
        sa.Column(
            "stripe_checkout_session_id", sa.Text, nullable=True, unique=True
        ),
        sa.Column(
            "stripe_payment_intent_id", sa.Text, nullable=True, unique=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_gift_orders_birth", "gift_orders", ["birth_id"])
    # The registry claim: one family-bound PAID purchase per item per birth.
    op.create_index(
        "uq_gift_orders_family_claim",
        "gift_orders",
        ["birth_id", "gift_catalog_item_id"],
        unique=True,
        postgresql_where=sa.text("status = 'paid' AND recipient_kind = 'family'"),
    )

    op.create_table(
        "gift_shipments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "gift_order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gift_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recipient_kind", sa.Text, nullable=False),
        sa.Column("address", postgresql.JSONB(), nullable=True),
        sa.Column("printful_order_id", sa.Text, nullable=True),
        sa.Column(
            "fulfillment_status", sa.Text, nullable=False, server_default="none"
        ),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_gift_shipments_order", "gift_shipments", ["gift_order_id"]
    )

    op.add_column(
        "births", sa.Column("shipping_address", postgresql.JSONB(), nullable=True)
    )

    op.execute(
        "UPDATE gift_catalog_items SET fulfillment_partner = 'printful' "
        "WHERE kind = 'physical'"
    )


def downgrade() -> None:
    op.drop_column("births", "shipping_address")
    op.drop_index("ix_gift_shipments_order", table_name="gift_shipments")
    op.drop_table("gift_shipments")
    op.drop_index("uq_gift_orders_family_claim", table_name="gift_orders")
    op.drop_index("ix_gift_orders_birth", table_name="gift_orders")
    op.drop_table("gift_orders")
