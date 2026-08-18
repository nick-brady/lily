"""per-design product choice

Which mug a design is destined for. Same shape as the photo and text choices
in 0027/0028: it belongs to one design, not to the whole birth.

This closes a gap rather than only adding a feature. "See this design on
another product" could render your artwork onto a black 15oz mug, but nothing
carried that choice anywhere — `submit_shipment` called
`default_for_product_kind()`, so the order shipped the default whatever you'd
been admiring. The column is what makes the choice real.

NULL means "the default for this product kind", so every existing rendering
keeps behaving exactly as it does now.

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-17 03:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0029"
down_revision: Union[str, Sequence[str], None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_renderings", sa.Column("product_key", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("gift_renderings", "product_key")
