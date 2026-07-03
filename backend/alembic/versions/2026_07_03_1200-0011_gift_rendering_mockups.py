"""gift rendering mockups

Adds `gift_rendering_mockups` — one cached product mockup per
(gift_rendering, shortlist product) for the "see this design on another
product" picker. The shortlist of products lives in code
(backend/fulfillment/products.py); `product_key` references an entry there.

The existing `mockup_s3_key` / `mockup_status` columns on `gift_renderings`
remain the auto-generated hero mockup; this table holds the on-demand
alternates.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-03 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gift_rendering_mockups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "gift_rendering_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gift_renderings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_key", sa.Text, nullable=False),
        sa.Column(
            "status", sa.Text, nullable=False, server_default="pending"
        ),
        sa.Column("mockup_s3_key", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_gift_rendering_mockups_rendering",
        "gift_rendering_mockups",
        ["gift_rendering_id"],
    )
    op.create_unique_constraint(
        "uq_gift_rendering_mockups_rendering_product",
        "gift_rendering_mockups",
        ["gift_rendering_id", "product_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_gift_rendering_mockups_rendering_product",
        "gift_rendering_mockups",
        type_="unique",
    )
    op.drop_index(
        "ix_gift_rendering_mockups_rendering", table_name="gift_rendering_mockups"
    )
    op.drop_table("gift_rendering_mockups")
