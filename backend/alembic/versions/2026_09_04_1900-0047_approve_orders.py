"""approving and cancelling drafts from our own admin page

Every Printful order is created as a draft; until now the only way to send
it to print was Printful's dashboard. The admin site can now confirm a draft
(money moves, production starts) or cancel it and refund the buyer, and the
shipment records which happened, when, and by whom.

Revision ID: 0047
Revises: 0046
Create Date: 2026-09-04 19:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0047"
down_revision: Union[str, Sequence[str], None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gift_shipments", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gift_shipments", sa.Column("confirmed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("gift_shipments", sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for col in ("canceled_at", "confirmed_by_user_id", "confirmed_at"):
        op.drop_column("gift_shipments", col)
