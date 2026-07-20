"""lifetime storage tier + catalog ordering

Two additions from the pricing thesis (2026-07-19):

- `births.storage_lifetime` — the "I'll handle this forever" gift, kept as
  a real flag instead of a far-future sentinel date so display copy can say
  "forever" honestly. `storage_paid_until` stays as-is for year grants.
- `gift_catalog_items.sort_order` — the shelf leads with the tangible
  thing (mug, cards) and storage follows; previously order fell back to
  created_at, which tied for all seed rows and floated storage to the top.

Also seeds the Lifetime Storage item ($59, storage_years_granted NULL =
forever). Lifetime is the headline storage option; the $15/5yr row stays
as the ladder rung that makes $59 read reasonable.

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-19 21:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "births",
        sa.Column(
            "storage_lifetime",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "gift_catalog_items",
        sa.Column(
            "sort_order",
            sa.Integer,
            nullable=False,
            server_default=sa.text("100"),
        ),
    )
    for product_kind, order in (
        ("mug", 10),
        ("birth_announcement_cards", 20),
        ("storage_lifetime", 30),
        ("storage_5yr", 40),
    ):
        op.execute(
            sa.text(
                "UPDATE gift_catalog_items SET sort_order = :o WHERE product_kind = :pk"
            ).bindparams(o=order, pk=product_kind)
        )

    catalog = sa.table(
        "gift_catalog_items",
        sa.column("kind", postgresql.ENUM(name="gift_kind", create_type=False)),
        sa.column("product_kind", sa.Text),
        sa.column("display_name", sa.Text),
        sa.column("base_price_cents", sa.Integer),
        sa.column("fulfillment_partner", sa.Text),
        sa.column("template_metadata", postgresql.JSONB),
        sa.column("storage_years_granted", sa.Integer),
        sa.column("surfaces_in", postgresql.JSONB),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        catalog,
        [
            {
                "kind": "storage_gift",
                "product_kind": "storage_lifetime",
                "display_name": "Lifetime Storage",
                "base_price_cents": 5900,
                "fulfillment_partner": None,
                "template_metadata": {},
                "storage_years_granted": None,
                "surfaces_in": ["day_two_prompt", "parent_dashboard_post_birth"],
                "sort_order": 30,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM gift_catalog_items WHERE product_kind = 'storage_lifetime'"
    )
    op.drop_column("gift_catalog_items", "sort_order")
    op.drop_column("births", "storage_lifetime")
