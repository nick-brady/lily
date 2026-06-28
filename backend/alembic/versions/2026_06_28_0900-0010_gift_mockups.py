"""gift mockups

Adds `mockup_s3_key` and `mockup_status` to `gift_renderings` for the
fulfillment-partner (Printful) product mockup that renders the artwork onto
the real product.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-28 09:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_renderings",
        sa.Column("mockup_s3_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "gift_renderings",
        sa.Column(
            "mockup_status",
            sa.Text(),
            nullable=False,
            server_default="none",
        ),
    )


def downgrade() -> None:
    op.drop_column("gift_renderings", "mockup_status")
    op.drop_column("gift_renderings", "mockup_s3_key")
