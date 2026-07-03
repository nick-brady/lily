"""unlock purchases

The $12 family unlock, recorded. One successful purchase per birth — the
UNIQUE(birth_id) is the idempotency invariant the spec calls for; a racing
second payment is refunded and never recorded. The unique payment-intent id
is a cheap extra invariant (one payment can never buy two births).

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-03 17:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unlock_purchases",
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
            unique=True,
        ),
        sa.Column(
            "purchased_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.Text, nullable=False, server_default="usd"),
        sa.Column("stripe_payment_intent_id", sa.Text, nullable=False, unique=True),
        sa.Column("stripe_checkout_session_id", sa.Text, nullable=True),
        sa.Column(
            "purchased_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("unlock_purchases")
